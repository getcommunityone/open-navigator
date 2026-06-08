"""
Decision-detail endpoint, backed by public.event_decision (AI-extracted policy
decisions).

Serves a single decision by its unique key (event_decision_id), which the
/search decision results link to (url=/decisions/{event_decision_id}). Mirrors
the people.py person-detail pattern: a single fetchrow on the public serving
table, 404 when absent.

The pool registers no JSON codec, so asyncpg returns JSONB columns as raw JSON
text — we json.loads() them here so vote_tally / competing_views / *_refs
serialize to the client as real objects/arrays instead of double-encoded strings.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/decision", tags=["decision"])

tracer = trace.get_tracer(__name__)


class MeetingDocument(BaseModel):
    """An agenda/minutes PDF attached to the decision's meeting (suiteone)."""
    document_type: str
    url: str
    doc_date: Optional[str] = None  # real DATE -> ISO 'YYYY-MM-DD' string on the wire
    body_name: Optional[str] = None


class MeetingRecord(BaseModel):
    """The PARSED official agenda/minutes content for the decision's meeting
    (public.meeting_document, from the agenda/minutes enrichment). Distinct from
    MeetingDocument, which is just the document link/status."""
    doc_kind: str                       # 'agenda' | 'minutes'
    meeting_body: Optional[str] = None
    agenda_items: Optional[Any] = None
    motions: Optional[Any] = None
    recorded_votes: Optional[Any] = None
    continuances: Optional[Any] = None
    legislation_numbers: Optional[Any] = None
    source_urls: Optional[Any] = None


class DecisionDetail(BaseModel):
    """A single AI-extracted policy decision, keyed by event_decision_id."""
    event_decision_id: str
    headline: Optional[str] = None
    decision_statement: Optional[str] = None
    outcome: Optional[str] = None
    primary_theme: Optional[str] = None
    # JSONB payloads (parsed from text); shapes vary by extraction.
    vote_tally: Optional[Any] = None
    human_element: Optional[Any] = None
    competing_views: Optional[Any] = None
    smart_brevity: Optional[Any] = None
    legislation_refs: Optional[Any] = None
    financial_item_refs: Optional[Any] = None
    place_refs: Optional[Any] = None
    # Location / provenance.
    jurisdiction_name: Optional[str] = None
    jurisdiction_type: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    city: Optional[str] = None
    c1_event_id: Optional[str] = None
    decision_id: Optional[str] = None
    subject_id: Optional[str] = None
    # Meeting context (event_meeting joined on c1_event_id).
    meeting_name: Optional[str] = None
    meeting_date: Optional[str] = None
    meeting_video_id: Optional[str] = None
    source_ai_model: Optional[str] = None
    extracted_at: Optional[str] = None
    # Associated meeting documents (agenda/minutes), joined on analysis_id ->
    # event_meeting_id. Empty list is a meaningful state (e.g. minutes unpublished).
    documents: List[MeetingDocument] = []
    has_agenda: bool = False
    has_minutes: bool = False
    minutes_status: str = "not_published"  # 'published' | 'not_published'
    # When minutes are unpublished: an ESTIMATED post date = meeting date +
    # the jurisdiction's median publish lag (jurisdiction_minutes_publish_lag).
    # Null when we have no reliable lag sample (sample_n < 5) — never fabricated.
    expected_minutes_date: Optional[str] = None  # ISO 'YYYY-MM-DD'
    minutes_typical_lag_days: Optional[int] = None
    minutes_lag_sample_n: Optional[int] = None
    # Parsed official agenda/minutes content (public.meeting_document), joined to
    # the meeting by jurisdiction + date. Empty when none enriched for this meeting.
    meeting_record: List[MeetingRecord] = []


_DECISION_SQL = """
    SELECT
        event_decision_id,
        headline,
        decision_statement,
        outcome,
        primary_theme,
        vote_tally,
        human_element,
        competing_views,
        smart_brevity,
        legislation_refs,
        financial_item_refs,
        place_refs,
        d.jurisdiction_name,
        d.jurisdiction_type,
        d.state,
        d.state_code,
        d.city,
        d.c1_event_id,
        d.analysis_id,
        d.decision_id,
        d.subject_id,
        d.source_ai_model,
        d.extracted_at,
        m.body_name AS meeting_name,
        CASE WHEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
             THEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) END AS meeting_date,
        m.video_id AS meeting_video_id
    FROM event_decision d
    LEFT JOIN event_meeting m ON m.c1_event_id = d.c1_event_id
    WHERE d.event_decision_id = $1
"""

# Parsed agenda/minutes content for a decision's meeting. Keyed by event_meeting_id
# (= the decision's analysis_id) — the same clean join _DOCUMENTS_SQL uses, so it
# aligns with the event_meeting_document link mart instead of a fragile
# jurisdiction+date match.
_MEETING_RECORD_SQL = """
    SELECT md.doc_kind, md.meeting_body, md.agenda_items, md.motions,
           md.recorded_votes, md.continuances, md.legislation_numbers, md.source_urls
    FROM public.meeting_document md
    WHERE md.event_meeting_id = $1
    ORDER BY md.doc_kind
"""

# JSONB columns asyncpg hands back as raw JSON text (no codec on the pool).
_JSON_FIELDS = (
    "vote_tally",
    "human_element",
    "competing_views",
    "smart_brevity",
    "legislation_refs",
    "financial_item_refs",
    "place_refs",
)


def _parse_json(value: Any) -> Any:
    """asyncpg returns JSONB as text without a codec; tolerate already-parsed too."""
    if value is None or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


# Meeting documents (agenda/minutes) for a decision's meeting. Joined on
# event_meeting_id = the decision's analysis_id. Agenda first, then minutes,
# then oldest doc_date first. Read-only fetch on a modeled public table.
_DOCUMENTS_SQL = """
    SELECT
        document_type,
        document_url,
        doc_date,
        body_name,
        census_geoid
    FROM event_meeting_document
    WHERE event_meeting_id = $1
    ORDER BY
        CASE document_type WHEN 'agenda' THEN 0 WHEN 'minutes' THEN 1 ELSE 2 END,
        doc_date NULLS LAST
"""

# Typical minutes-publish lag for a jurisdiction, used to ESTIMATE when pending
# minutes will post. Only jurisdictions with sample_n >= 5 have a row.
_MINUTES_LAG_SQL = """
    SELECT median_lag_days, sample_n
    FROM jurisdiction_minutes_publish_lag
    WHERE census_geoid = $1
"""


# ---------------------------------------------------------------------------
# Map drill-down: geocoded decision pins (nationwide, generic — no hardcoded
# jurisdiction). Joins event_decision -> event_decision_place -> the geocoded
# place view, returning one pin per (decision, plottable place). A decision with
# multiple geocoded places yields multiple pins; we order is_primary places
# first so the primary place leads. Caller can filter by state / bbox / theme.
# ---------------------------------------------------------------------------

_MAP_LIMIT_DEFAULT = 2_000
_MAP_LIMIT_MAX = 5_000


class DecisionMapPin(BaseModel):
    """A single geocoded civic-decision pin for the map."""
    event_decision_id: str
    decision_id: Optional[str] = None
    place_id: str
    latitude: float
    longitude: float
    headline: Optional[str] = None
    primary_theme: Optional[str] = None
    outcome: Optional[str] = None
    # JSONB pass-through (parsed from text; asyncpg pool has no JSON codec).
    vote_tally: Optional[Any] = None
    jurisdiction_name: Optional[str] = None
    state_code: Optional[str] = None
    # ISO date string (from event_meeting on c1_event_id) or None.
    event_date: Optional[str] = None
    normalized_address: Optional[str] = None
    is_primary: bool = False


class DecisionMapResponse(BaseModel):
    """Map payload: filters echoed back plus the plottable pins."""
    state: Optional[str] = None
    theme: Optional[str] = None
    bbox: Optional[List[float]] = None
    total: int
    limit: int
    pins: List[DecisionMapPin]


# Pin query. place_state_code is the place's own state (per spec). event_date is
# pulled from event_meeting (text columns) joined on c1_event_id, matching the
# detail route, and only surfaced when it looks like an ISO date.
_MAP_SQL = """
    SELECT
        d.event_decision_id,
        d.decision_id,
        g.place_id,
        g.latitude::float8  AS latitude,
        g.longitude::float8 AS longitude,
        d.headline,
        d.primary_theme,
        d.outcome,
        d.vote_tally,
        d.jurisdiction_name,
        g.place_state_code  AS state_code,
        CASE
            WHEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, ''))
                 ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
            THEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, ''))
        END AS event_date,
        g.normalized_address,
        COALESCE(edp.is_primary, FALSE) AS is_primary
    FROM event_decision d
    JOIN event_decision_place edp
        ON edp.event_decision_id = d.event_decision_id
    JOIN event_place_geocoded g
        ON g.place_id = edp.place_id
    LEFT JOIN event_meeting m
        ON m.c1_event_id = d.c1_event_id
    WHERE g.latitude IS NOT NULL
      AND g.longitude IS NOT NULL
    __FILTERS__
    ORDER BY edp.is_primary DESC, d.event_decision_id, g.place_id
    LIMIT __LIMIT__
"""


def _parse_bbox(bbox: Optional[str]) -> Optional[List[float]]:
    """Parse 'minLon,minLat,maxLon,maxLat' into 4 floats; 400 on bad input."""
    if not bbox or not bbox.strip():
        return None
    parts = [p.strip() for p in bbox.split(",")]
    if len(parts) != 4:
        raise HTTPException(
            status_code=400,
            detail="bbox must be 'minLon,minLat,maxLon,maxLat' (4 values)",
        )
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="bbox values must be numbers") from exc
    if min_lon > max_lon or min_lat > max_lat:
        raise HTTPException(
            status_code=400,
            detail="bbox min must be <= max (order: minLon,minLat,maxLon,maxLat)",
        )
    return [min_lon, min_lat, max_lon, max_lat]


@router.get("/map", response_model=DecisionMapResponse)
async def get_decision_map(
    state: Optional[str] = Query(
        None, min_length=2, max_length=2,
        description="2-letter state code; filters by the place's state",
    ),
    bbox: Optional[str] = Query(
        None, description="Viewport filter 'minLon,minLat,maxLon,maxLat'",
    ),
    theme: Optional[str] = Query(
        None, description="Filter by primary_theme (exact match)",
    ),
    limit: int = Query(
        _MAP_LIMIT_DEFAULT, ge=1, le=_MAP_LIMIT_MAX,
        description=f"Max pins (default {_MAP_LIMIT_DEFAULT}, cap {_MAP_LIMIT_MAX})",
    ),
) -> DecisionMapResponse:
    """
    Geocoded civic-decision pins for a nationwide drill-down map.

    Joins event_decision -> event_decision_place -> event_place_geocoded and
    returns only plottable rows (latitude IS NOT NULL). One pin per
    (decision, geocoded place); primary places are ordered first. All filters
    are optional, supporting nation -> state -> viewport drill-down.

    Example::

        GET /api/decision/map?state=AL&theme=Housing&limit=2000
    """
    state_code = state.strip().upper() if state else None
    bbox_vals = _parse_bbox(bbox)

    with tracer.start_as_current_span("decision-map") as span:
        span.set_attribute("decision_map.state", state_code or "")
        span.set_attribute("decision_map.theme", theme or "")
        span.set_attribute("decision_map.has_bbox", bbox_vals is not None)
        span.set_attribute("decision_map.limit", limit)

        filters: List[str] = []
        params: List[Any] = []
        idx = 1

        if state_code:
            filters.append(f"AND g.place_state_code = ${idx}")
            params.append(state_code)
            idx += 1

        if theme:
            filters.append(f"AND d.primary_theme = ${idx}")
            params.append(theme)
            idx += 1

        if bbox_vals:
            min_lon, min_lat, max_lon, max_lat = bbox_vals
            filters.append(
                f"AND g.longitude BETWEEN ${idx} AND ${idx + 1} "
                f"AND g.latitude BETWEEN ${idx + 2} AND ${idx + 3}"
            )
            params.extend([min_lon, max_lon, min_lat, max_lat])
            idx += 4

        limit_idx = idx
        params.append(limit)

        sql = _MAP_SQL.replace(
            "__FILTERS__", "\n      ".join(filters)
        ).replace("__LIMIT__", f"${limit_idx}")

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("decision-map.query") as qspan:
                    rows = await conn.fetch(sql, *params)
                    qspan.set_attribute("decision_map.row_count", len(rows))
        except Exception as e:  # noqa: BLE001 — surface a clean 500
            span.record_exception(e)
            logger.error("Decision map query failed: {}", e)
            raise HTTPException(status_code=500, detail="Failed to load decision map")

        pins = [
            DecisionMapPin(
                event_decision_id=r["event_decision_id"],
                decision_id=r["decision_id"],
                place_id=r["place_id"],
                latitude=float(r["latitude"]),
                longitude=float(r["longitude"]),
                headline=r["headline"],
                primary_theme=r["primary_theme"],
                outcome=r["outcome"],
                vote_tally=_parse_json(r["vote_tally"]),
                jurisdiction_name=r["jurisdiction_name"],
                state_code=r["state_code"],
                event_date=r["event_date"],
                normalized_address=r["normalized_address"],
                is_primary=bool(r["is_primary"]),
            )
            for r in rows
        ]

        span.set_attribute("decision_map.pin_count", len(pins))
        logger.info(
            "🗺️ Decision map -> {} pins (state={}, theme={}, bbox={})",
            len(pins), state_code, theme, bbox_vals is not None,
        )

        return DecisionMapResponse(
            state=state_code,
            theme=theme,
            bbox=bbox_vals,
            total=len(pins),
            limit=limit,
            pins=pins,
        )


@router.get("/{event_decision_id}", response_model=DecisionDetail)
async def get_decision(event_decision_id: str) -> DecisionDetail:
    """
    Return a single AI-extracted policy decision by event_decision_id.
    404 if no decision row matches.
    """
    with tracer.start_as_current_span("decision-detail") as span:
        span.set_attribute("decision.event_decision_id", event_decision_id)
        try:
            pool = await get_db_pool()
            doc_rows: list = []
            lag_row = None  # jurisdiction_minutes_publish_lag row (fetched within conn)
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("decision-detail.query"):
                    row = await conn.fetchrow(_DECISION_SQL, event_decision_id)

                if row is None:
                    span.set_attribute("decision.found", False)
                    raise HTTPException(
                        status_code=404,
                        detail=f"No decision found for event_decision_id '{event_decision_id}'",
                    )

                # Associated meeting documents (agenda/minutes). Defensive: a
                # missing/failing table or NULL analysis_id yields no documents,
                # never a 500 on the decision itself.
                analysis_id = row["analysis_id"]
                if analysis_id is not None:
                    with tracer.start_as_current_span("decision-detail.documents") as doc_span:
                        doc_span.set_attribute("decision.analysis_id", analysis_id)
                        try:
                            doc_rows = await conn.fetch(_DOCUMENTS_SQL, analysis_id)
                        except Exception as doc_err:  # noqa: BLE001 — documents are best-effort
                            doc_span.record_exception(doc_err)
                            logger.warning(
                                "Meeting documents lookup failed for decision {} (analysis_id={}): {}",
                                event_decision_id, analysis_id, doc_err,
                            )
                            doc_rows = []
                        doc_span.set_attribute("decision.document_count", len(doc_rows))

                        # If minutes aren't among the docs, prefetch the
                        # jurisdiction's publish-lag (keyed by the meeting's geoid)
                        # so we can estimate when they'll post. Done here so it
                        # runs while the connection is still held.
                        has_minutes_pre = any(dr["document_type"] == "minutes" for dr in doc_rows)
                        geoid_pre = next((dr["census_geoid"] for dr in doc_rows if dr["census_geoid"]), None)
                        if not has_minutes_pre and geoid_pre:
                            try:
                                lag_row = await conn.fetchrow(_MINUTES_LAG_SQL, geoid_pre)
                            except Exception as lag_err:  # noqa: BLE001 — estimate is best-effort
                                doc_span.record_exception(lag_err)
                                logger.warning("Minutes-lag lookup failed (geoid={}): {}", geoid_pre, lag_err)

                # Parsed agenda/minutes content for this decision's meeting
                # (public.meeting_document). Best-effort — never 500 the decision.
                meeting_record_rows: list = []
                if row["analysis_id"] is not None:
                    try:
                        meeting_record_rows = await conn.fetch(_MEETING_RECORD_SQL, row["analysis_id"])
                    except Exception as mr_err:  # noqa: BLE001 — best-effort
                        logger.warning(
                            "meeting_record lookup failed for {}: {}", event_decision_id, mr_err
                        )

            span.set_attribute("decision.found", True)

            data = dict(row)
            data.pop("analysis_id", None)  # internal join key, not part of the response shape
            for field in _JSON_FIELDS:
                data[field] = _parse_json(data.get(field))
            extracted = data.get("extracted_at")
            data["extracted_at"] = extracted.isoformat() if extracted is not None else None

            documents: List[MeetingDocument] = []
            for dr in doc_rows:
                dd = dr["doc_date"]
                documents.append(
                    MeetingDocument(
                        document_type=dr["document_type"],
                        url=dr["document_url"],
                        # Real DATE -> ISO string on the wire; tolerate text too.
                        doc_date=dd.isoformat() if hasattr(dd, "isoformat") else (str(dd) if dd else None),
                        body_name=dr["body_name"],
                    )
                )
            data["documents"] = documents
            data["has_agenda"] = any(d.document_type == "agenda" for d in documents)
            has_minutes = any(d.document_type == "minutes" for d in documents)
            data["has_minutes"] = has_minutes
            data["minutes_status"] = "published" if has_minutes else "not_published"

            # Estimate when pending minutes will post: meeting date + the
            # jurisdiction's median publish lag (lag_row prefetched above). Only
            # when minutes are absent AND we know the meeting date AND the
            # jurisdiction has a reliable lag sample. Never fabricated.
            if not has_minutes and lag_row and lag_row["median_lag_days"] is not None:
                meeting_day = next(
                    (dr["doc_date"] for dr in doc_rows if isinstance(dr["doc_date"], date)),
                    None,
                )
                if meeting_day is not None:
                    median_lag = int(lag_row["median_lag_days"])
                    data["expected_minutes_date"] = (
                        meeting_day + timedelta(days=median_lag)
                    ).isoformat()
                    data["minutes_typical_lag_days"] = median_lag
                    data["minutes_lag_sample_n"] = lag_row["sample_n"]

            data["meeting_record"] = [
                MeetingRecord(
                    doc_kind=r["doc_kind"],
                    meeting_body=r["meeting_body"],
                    agenda_items=_parse_json(r["agenda_items"]),
                    motions=_parse_json(r["motions"]),
                    recorded_votes=_parse_json(r["recorded_votes"]),
                    continuances=_parse_json(r["continuances"]),
                    legislation_numbers=_parse_json(r["legislation_numbers"]),
                    source_urls=_parse_json(r["source_urls"]),
                )
                for r in meeting_record_rows
            ]

            logger.info(
                "⚖️ Decision detail {} -> {} ({} docs, {} records)",
                event_decision_id, data.get("outcome"), len(documents), len(meeting_record_rows),
            )
            return DecisionDetail(**data)

        except HTTPException:
            raise
        except Exception as e:
            span.record_exception(e)
            logger.error("Decision detail error for {}: {}", event_decision_id, e)
            raise HTTPException(status_code=500, detail="Failed to load decision detail")


# ---------------------------------------------------------------------------
# Related decisions — "similar" feed driven by OUR metadata (shared theme + same
# body/jurisdiction), not by any video platform. Powers the decision page's
# "Related decisions" rail.
# ---------------------------------------------------------------------------
class RelatedDecision(BaseModel):
    event_decision_id: str
    headline: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    state_code: Optional[str] = None
    primary_theme: Optional[str] = None
    outcome: Optional[str] = None
    shared_theme: bool = False
    shared_jurisdiction: bool = False


_RELATED_SQL = """
    WITH base AS (
        SELECT primary_theme, state_code, jurisdiction_name
        FROM event_decision WHERE event_decision_id = $1
    )
    SELECT
        e.event_decision_id,
        e.headline,
        e.jurisdiction_name,
        e.state_code,
        e.primary_theme,
        e.outcome,
        (e.primary_theme IS NOT DISTINCT FROM b.primary_theme) AS shared_theme,
        (e.jurisdiction_name IS NOT DISTINCT FROM b.jurisdiction_name) AS shared_jurisdiction,
        (
            (e.primary_theme IS NOT DISTINCT FROM b.primary_theme)::int * 2
            + (e.jurisdiction_name IS NOT DISTINCT FROM b.jurisdiction_name)::int * 2
            + (e.state_code IS NOT DISTINCT FROM b.state_code)::int
        ) AS score
    FROM event_decision e, base b
    WHERE e.event_decision_id <> $1
      AND (
            (b.primary_theme IS NOT NULL AND e.primary_theme = b.primary_theme)
         OR (b.jurisdiction_name IS NOT NULL AND e.jurisdiction_name = b.jurisdiction_name)
      )
    ORDER BY score DESC, e.extracted_at DESC NULLS LAST
    LIMIT $2
"""


@router.get("/{event_decision_id}/related", response_model=List[RelatedDecision])
async def get_related_decisions(
    event_decision_id: str,
    limit: int = Query(6, ge=1, le=20),
) -> List[RelatedDecision]:
    """Decisions sharing this one's theme or body — ranked by overlap. [] if none."""
    with tracer.start_as_current_span("decision-related") as span:
        span.set_attribute("decision.event_decision_id", event_decision_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(_RELATED_SQL, event_decision_id, limit)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("Related decisions error for {}: {}", event_decision_id, e)
            raise HTTPException(status_code=500, detail="Failed to load related decisions")

        return [
            RelatedDecision(
                event_decision_id=r["event_decision_id"],
                headline=r["headline"],
                jurisdiction_name=r["jurisdiction_name"],
                state_code=r["state_code"],
                primary_theme=r["primary_theme"],
                outcome=r["outcome"],
                shared_theme=bool(r["shared_theme"]),
                shared_jurisdiction=bool(r["shared_jurisdiction"]),
            )
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Decision thread — the SAME item tracked ACROSS meetings (its lifecycle), so a
# deferred item that returns later reads as one story instead of disconnected
# rows. Links occurrences by a SPECIFIC place (a street/site place_id, never a
# jurisdiction-wide stub that would falsely merge unrelated items) or by a
# suffix-stripped subject slug (the trailing numeric id varies per meeting).
# Ordered by meeting date; each row carries its outcome (so delays/continuances
# show as steps) and the for/against view labels for an optional positions view.
# ---------------------------------------------------------------------------
class DecisionThreadItem(BaseModel):
    event_decision_id: str
    headline: Optional[str] = None
    outcome: Optional[str] = None
    primary_theme: Optional[str] = None
    meeting_name: Optional[str] = None
    meeting_date: Optional[str] = None
    meeting_video_id: Optional[str] = None
    is_current: bool = False
    # Optional for/against labels (from competing_views) for this occurrence.
    prevailing_label: Optional[str] = None
    counter_labels: List[str] = []


_THREAD_SQL = """
    WITH base AS (
        SELECT
            CASE WHEN starts_with(primary_place_id, 'place_') THEN primary_place_id END AS place_key,
            NULLIF(regexp_replace(COALESCE(subject_id, ''), '_[0-9]+$', ''), '')        AS subj_key
        FROM event_decision WHERE event_decision_id = $1
    )
    SELECT
        d.event_decision_id,
        d.headline,
        d.outcome,
        d.primary_theme,
        d.competing_views,
        m.body_name AS meeting_name,
        CASE WHEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
             THEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) END AS meeting_date,
        m.video_id AS meeting_video_id,
        (d.event_decision_id = $1) AS is_current
    FROM event_decision d
    LEFT JOIN event_meeting m ON m.c1_event_id = d.c1_event_id
    CROSS JOIN base b
    WHERE (b.place_key IS NOT NULL AND d.primary_place_id = b.place_key)
       OR (b.subj_key  IS NOT NULL
           AND NULLIF(regexp_replace(COALESCE(d.subject_id, ''), '_[0-9]+$', ''), '') = b.subj_key)
    ORDER BY meeting_date NULLS LAST, d.extracted_at DESC NULLS LAST
    LIMIT 25
"""


def _view_labels(competing_views: Any) -> tuple[Optional[str], List[str]]:
    """Pull (prevailing_label, [counter_labels]) out of a competing_views value.

    The pool has no JSONB codec, so the value arrives as TEXT — json.loads it.
    """
    cv = competing_views
    if isinstance(cv, str):
        try:
            cv = json.loads(cv)
        except (ValueError, TypeError):
            return None, []
    if not isinstance(cv, dict):
        return None, []
    dom = cv.get("dominant_view")
    prevailing = dom.get("view_label") if isinstance(dom, dict) else None
    labels: List[str] = []
    counters = cv.get("counter_views")
    if isinstance(counters, list):
        for c in counters:
            if isinstance(c, dict) and isinstance(c.get("view_label"), str):
                labels.append(c["view_label"])
    return (prevailing if isinstance(prevailing, str) else None), labels


@router.get("/{event_decision_id}/thread", response_model=List[DecisionThreadItem])
async def get_decision_thread(event_decision_id: str) -> List[DecisionThreadItem]:
    """
    The same item across meetings (lifecycle), oldest → newest by meeting date.

    Returns a single self-row when the item appears in only one analyzed meeting;
    the client renders the cross-meeting timeline only when there are 2+.
    """
    with tracer.start_as_current_span("decision-thread") as span:
        span.set_attribute("decision.event_decision_id", event_decision_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(_THREAD_SQL, event_decision_id)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("Decision thread error for {}: {}", event_decision_id, e)
            raise HTTPException(status_code=500, detail="Failed to load decision thread")

        items: List[DecisionThreadItem] = []
        for r in rows:
            prevailing, counters = _view_labels(r["competing_views"])
            items.append(
                DecisionThreadItem(
                    event_decision_id=r["event_decision_id"],
                    headline=r["headline"],
                    outcome=r["outcome"],
                    primary_theme=r["primary_theme"],
                    meeting_name=r["meeting_name"],
                    meeting_date=r["meeting_date"],
                    meeting_video_id=r["meeting_video_id"],
                    is_current=bool(r["is_current"]),
                    prevailing_label=prevailing,
                    counter_labels=counters,
                )
            )
        span.set_attribute("decision.thread_count", len(items))
        return items
