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
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/decision", tags=["decision"])

tracer = trace.get_tracer(__name__)


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
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("decision-detail.query"):
                    row = await conn.fetchrow(_DECISION_SQL, event_decision_id)

            if row is None:
                span.set_attribute("decision.found", False)
                raise HTTPException(
                    status_code=404,
                    detail=f"No decision found for event_decision_id '{event_decision_id}'",
                )
            span.set_attribute("decision.found", True)

            data = dict(row)
            for field in _JSON_FIELDS:
                data[field] = _parse_json(data.get(field))
            extracted = data.get("extracted_at")
            data["extracted_at"] = extracted.isoformat() if extracted is not None else None

            logger.info("⚖️ Decision detail {} -> {}", event_decision_id, data.get("outcome"))
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
