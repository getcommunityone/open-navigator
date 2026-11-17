"""
Flat, paginated meeting-browse endpoint: GET /api/meetings.

The meeting-grain analogue of the flat decision-browse list
(api/routes/decision_browse.py). Returns a single flat page of meeting cards —
one row per meeting — read straight off the already-modeled public.meeting_browse
serving view. NO transformation logic lives here: the per-meeting rollups
(decision_count / question_count / topic_link_count / top_interestingness_score)
are produced upstream in dbt; this endpoint only filters, orders, paginates, and
shapes rows for the wire.

Filters are all query-time (no new dbt models):
- topic_id    -> EXISTS over public.meeting_topic_link (link_type='civicsearch_topic')
- theme       -> EXISTS over public.meeting_topic_link (link_type='canonical_theme')
- question_id -> EXISTS over public.meeting_question_link
- state       -> normalize_state_input() -> mb.state_code
- city / q    -> ILIKE over the display columns

Recent, not-yet-analyzed meetings (#509): with sort=recent and no content filter
(topic_id / theme / question_id), the page also includes rows from
public.recent_transcribed_meeting: meetings transcribed in the last 180 days that
have no AI analysis yet (meeting_browse only holds analyzed meetings, so the
homepage "What's New" rail otherwise stopped where analysis stopped). They come back
with ``analyzed: false``, ``meeting_id: null``, no decision/question counts, their
``video_url``, and, when the transcript matched a curated topic or question, the
stored verbatim ``evidence`` passage (<mark>ed in dbt; no transcript text is read
here, #496) plus its ``jump_url``. A video meeting_browse already serves is never
repeated, so a meeting switches to its analyzed card as soon as it is analyzed. In
recent mode, dates later than today are left out (#472).

Patterns mirror decision_browse.py: asyncpg pool via get_db_pool(), an
OpenTelemetry span around the query work, and the wire-format rule (the meeting
`date` is serialized as an ISO 'YYYY-MM-DD' string or null). meeting_date is TEXT
in the view, so it is coerced to a real date in SQL (``mb.meeting_date::date``,
NULL on a malformed value) and rendered ISO in Python.
"""
from __future__ import annotations

from typing import Any, List, Optional

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.data_centers import jump_url
from api.routes.search_postgres import get_db_pool, normalize_state_input

router = APIRouter(prefix="/meetings", tags=["meetings"])

tracer = trace.get_tracer(__name__)


class MeetingCard(BaseModel):
    """A single meeting browse card — real data only; NULL/0/empty are honest.

    ``analyzed`` is False for a transcribed meeting with no AI analysis yet
    (public.recent_transcribed_meeting): it has no meeting page (``meeting_id`` is
    null), no decision/question counts, and links to its ``video_url``.
    """
    meeting_id: Optional[int] = None
    title: Optional[str] = None
    jurisdiction: Optional[str] = None
    city: Optional[str] = None
    state_code: Optional[str] = None
    state: Optional[str] = None
    date: Optional[str] = None              # meeting_date coerced to ISO yyyy-mm-dd
    decision_count: int = 0
    question_count: int = 0
    has_decisions: bool = False
    video_id: Optional[str] = None
    analyzed: bool = True
    video_url: Optional[str] = None
    # Verbatim transcript passage, matched words in <mark>…</mark>, from the
    # meeting's curated topic/question link; null when there is none.
    evidence: Optional[str] = None
    # What the passage matched: a curated topic name or a policy question.
    evidence_label: Optional[str] = None
    # The recording at the passage's moment (YouTube t=); null when untimed.
    jump_url: Optional[str] = None


class MeetingListPagination(BaseModel):
    """Pagination envelope for the flat meeting list."""
    total: int
    limit: int
    offset: int


class MeetingListResponse(BaseModel):
    """A flat, paginated page of meeting cards."""
    items: List[MeetingCard]
    pagination: MeetingListPagination


# Columns selected for each card. meeting_date is TEXT in the view; coerce it to a
# real date so the driver hands back a date object (NULL on a malformed string).
_CARD_COLS = """
    mb.event_meeting_id,
    mb.meeting_title,
    mb.jurisdiction_name,
    mb.city,
    mb.state_code,
    mb.state,
    CASE WHEN mb.meeting_date ~ '^\\d{4}-\\d{2}-\\d{2}'
         THEN substring(mb.meeting_date FROM 1 FOR 10)::date END AS meeting_date,
    mb.decision_count,
    mb.question_count,
    mb.video_id
"""

# Parsed meeting_date for ORDER BY. meeting_date is TEXT in the view and can hold
# 'unknown' / '' / other non-ISO values — sorting the raw column lexicographically
# puts 'unknown' *first* on DESC ('u' > '2'). Coerce to date and NULL the junk.
_MEETING_DATE_SORT = (
    "CASE WHEN mb.meeting_date ~ '^\\d{4}-\\d{2}-\\d{2}' "
    "THEN substring(mb.meeting_date FROM 1 FOR 10)::date END"
)

# Sort modes. `interesting` keeps meetings without a scored decision last, then
# falls back to recency; `decisions` leads with the busiest meetings.
_ORDER_BY = {
    "recent": f"{_MEETING_DATE_SORT} DESC NULLS LAST",
    "interesting": (
        "mb.top_interestingness_score DESC NULLS LAST, "
        f"{_MEETING_DATE_SORT} DESC NULLS LAST"
    ),
    "decisions": (
        "mb.decision_count DESC NULLS LAST, "
        f"{_MEETING_DATE_SORT} DESC NULLS LAST"
    ),
}


def _build_filters(
    topic_id: Optional[int],
    theme: Optional[str],
    question_id: Optional[str],
    state_code: Optional[str],
    city: Optional[str],
    q: Optional[str],
) -> tuple[str, List[Any]]:
    """
    Build the WHERE predicate + ordered params over ``meeting_browse mb``.

    Returns (where_sql, params). `where_sql` is a complete predicate ('TRUE' when
    unfiltered) and `params` are positional ($1, $2, ...) in clause order — the
    caller appends LIMIT / OFFSET (list endpoint) or nothing (count).
    """
    clauses: List[str] = []
    params: List[Any] = []
    idx = 1

    if topic_id is not None:
        # CivicSearch topic vocabulary — link_id is the topic_id stored as text.
        clauses.append(
            f"EXISTS (SELECT 1 FROM meeting_topic_link mtl "
            f"WHERE mtl.event_meeting_id = mb.event_meeting_id "
            f"AND mtl.link_type = 'civicsearch_topic' "
            f"AND mtl.link_id = ${idx}::text)"
        )
        params.append(str(topic_id))
        idx += 1

    if theme and theme.strip():
        # Fallback axis — canonical-theme slug stored verbatim in link_id.
        clauses.append(
            f"EXISTS (SELECT 1 FROM meeting_topic_link mtl "
            f"WHERE mtl.event_meeting_id = mb.event_meeting_id "
            f"AND mtl.link_type = 'canonical_theme' "
            f"AND mtl.link_id = ${idx})"
        )
        params.append(theme.strip())
        idx += 1

    if question_id and question_id.strip():
        clauses.append(
            f"EXISTS (SELECT 1 FROM meeting_question_link mql "
            f"WHERE mql.event_meeting_id = mb.event_meeting_id "
            f"AND mql.question_id = ${idx})"
        )
        params.append(question_id.strip())
        idx += 1

    if state_code:
        clauses.append(f"mb.state_code = ${idx}")
        params.append(state_code)
        idx += 1

    if city and city.strip():
        clauses.append(
            f"(mb.city ILIKE ${idx} OR mb.jurisdiction_name ILIKE ${idx})"
        )
        params.append(f"%{city.strip()}%")
        idx += 1

    if q and q.strip():
        clauses.append(
            f"(mb.meeting_title ILIKE ${idx} OR mb.jurisdiction_name ILIKE ${idx})"
        )
        params.append(f"%{q.strip()}%")
        idx += 1

    where_sql = " AND ".join(clauses) if clauses else "TRUE"
    return where_sql, params


def _scope_filters(
    alias: str,
    state_code: Optional[str],
    city: Optional[str],
    q: Optional[str],
    start_idx: int = 1,
) -> tuple[List[str], List[Any]]:
    """
    The scope predicates (state / city / q) over a relation that carries
    meeting_title, jurisdiction_name, city and state_code — meeting_browse or
    recent_transcribed_meeting. Same semantics as _build_filters, so both legs of
    the recent union are filtered to exactly the same scope (the scope label).
    """
    clauses: List[str] = []
    params: List[Any] = []
    idx = start_idx
    if state_code:
        clauses.append(f"{alias}.state_code = ${idx}")
        params.append(state_code)
        idx += 1
    if city and city.strip():
        clauses.append(
            f"({alias}.city ILIKE ${idx} OR {alias}.jurisdiction_name ILIKE ${idx})"
        )
        params.append(f"%{city.strip()}%")
        idx += 1
    if q and q.strip():
        clauses.append(
            f"({alias}.meeting_title ILIKE ${idx} OR {alias}.jurisdiction_name ILIKE ${idx})"
        )
        params.append(f"%{q.strip()}%")
        idx += 1
    return clauses, params


def _recent_union_sql(
    state_code: Optional[str], city: Optional[str], q: Optional[str]
) -> tuple[str, str, List[Any]]:
    """
    (count_sql, list_sql, params) for sort=recent with no content filter: analyzed
    meetings (meeting_browse) UNION recent transcribed-but-unanalyzed meetings
    (recent_transcribed_meeting), newest first. The list SQL takes LIMIT / OFFSET as
    the next two positional params. Both legs drop dates later than today (#472);
    the unanalyzed leg drops any video meeting_browse already serves.
    """
    mb_clauses, params = _scope_filters("mb", state_code, city, q)
    r_clauses, _ = _scope_filters("r", state_code, city, q)
    mb_where = " AND ".join(
        mb_clauses + [f"({_MEETING_DATE_SORT} IS NULL OR {_MEETING_DATE_SORT} <= current_date)"]
    )
    r_where = " AND ".join(
        r_clauses
        + [
            "r.meeting_date <= current_date",
            "NOT EXISTS (SELECT 1 FROM meeting_browse mb2 WHERE mb2.video_id = r.video_id)",
        ]
    )
    union = f"""
        SELECT
            TRUE AS analyzed,
            {_CARD_COLS},
            NULL::text AS video_url,
            NULL::text AS evidence,
            NULL::text AS evidence_label,
            NULL::numeric AS evidence_start_seconds
        FROM meeting_browse mb
        WHERE {mb_where}
        UNION ALL
        SELECT
            FALSE AS analyzed,
            NULL::bigint AS event_meeting_id,
            r.meeting_title,
            r.jurisdiction_name,
            r.city,
            r.state_code,
            r.state,
            r.meeting_date,
            0 AS decision_count,
            0 AS question_count,
            r.video_id,
            r.video_url,
            r.evidence,
            r.evidence_label,
            r.evidence_start_seconds
        FROM recent_transcribed_meeting r
        WHERE {r_where}
    """
    count_sql = f"SELECT COUNT(*) FROM ({union}) cards"
    n = len(params)
    list_sql = f"""
        SELECT * FROM ({union}) cards
        ORDER BY cards.meeting_date DESC NULLS LAST, cards.analyzed DESC,
                 cards.event_meeting_id DESC NULLS LAST, cards.video_id
        LIMIT ${n + 1} OFFSET ${n + 2}
    """
    return count_sql, list_sql, params


def _iso_date(value: Any) -> Optional[str]:
    """Render a date/value as an ISO 'YYYY-MM-DD' string, or None."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_card(row: Any) -> MeetingCard:
    """Shape one meeting_browse row (or a recent-union row) into a MeetingCard."""
    keys = set(row.keys())
    analyzed = bool(row["analyzed"]) if "analyzed" in keys else True
    if not analyzed:
        # Not yet analyzed: no meeting page and no counts exist — never invent them.
        video_url = row["video_url"]
        start = row["evidence_start_seconds"]
        evidence = row["evidence"]
        return MeetingCard(
            meeting_id=None,
            title=row["meeting_title"],
            jurisdiction=row["jurisdiction_name"],
            city=row["city"],
            state_code=row["state_code"],
            state=row["state"],
            date=_iso_date(row["meeting_date"]),
            decision_count=0,
            question_count=0,
            has_decisions=False,
            video_id=row["video_id"],
            analyzed=False,
            video_url=video_url,
            evidence=evidence,
            evidence_label=row["evidence_label"] if evidence else None,
            jump_url=(
                jump_url(video_url or "", float(start))
                if evidence and start is not None
                else None
            ),
        )
    decision_count = int(row["decision_count"] or 0)
    return MeetingCard(
        meeting_id=int(row["event_meeting_id"]),
        title=row["meeting_title"],
        jurisdiction=row["jurisdiction_name"],
        city=row["city"],
        state_code=row["state_code"],
        state=row["state"],
        date=_iso_date(row["meeting_date"]),
        decision_count=decision_count,
        question_count=int(row["question_count"] or 0),
        has_decisions=decision_count > 0,
        video_id=row["video_id"],
        analyzed=True,
    )


@router.get("", response_model=MeetingListResponse)
async def list_meetings(
    topic_id: Optional[int] = Query(
        None, description="CivicSearch topic id — keep only meetings linked to it "
                          "(public.meeting_topic_link, link_type=civicsearch_topic).",
    ),
    theme: Optional[str] = Query(
        None, description="Canonical-theme slug — fallback axis "
                          "(public.meeting_topic_link, link_type=canonical_theme).",
    ),
    question_id: Optional[str] = Query(
        None, description="Policy-question id — keep only meetings that "
                          "instantiate it (public.meeting_question_link).",
    ),
    state: Optional[str] = Query(
        None, description="2-letter code or full state name (normalized).",
    ),
    city: Optional[str] = Query(
        None, description="City name (ILIKE on city / jurisdiction_name).",
    ),
    q: Optional[str] = Query(
        None, description="Free-text filter (ILIKE) over meeting title / jurisdiction.",
    ),
    sort: str = Query(
        "recent",
        description="recent | interesting | decisions (default recent).",
    ),
    limit: int = Query(24, ge=1, le=100, description="Page size (1..100)."),
    offset: int = Query(0, ge=0, description="Pagination offset."),
) -> MeetingListResponse:
    """
    Flat, paginated list of meeting cards (the meeting-grain browse list).

    Reads public.meeting_browse and renders each row as a MeetingCard. All filters
    are optional and query-time; `total` is a COUNT over the same filtered set
    (ignoring limit/offset).

    Example::

        GET /api/meetings?topic_id=51&state=MA&sort=recent&limit=24&offset=0
    """
    sort_key = (sort or "recent").lower()
    if sort_key not in _ORDER_BY:
        raise HTTPException(
            status_code=400,
            detail=f"sort must be one of {sorted(_ORDER_BY)} (got '{sort}')",
        )
    state_code = normalize_state_input(state)
    q = q.strip() if q and q.strip() else None

    with tracer.start_as_current_span("meetings-list") as span:
        span.set_attribute("meetings.sort", sort_key)
        span.set_attribute("meetings.state_code", state_code or "")
        span.set_attribute("meetings.city", city or "")
        span.set_attribute("meetings.q", q or "")
        span.set_attribute("meetings.topic_id", topic_id or 0)
        span.set_attribute("meetings.theme", theme or "")
        span.set_attribute("meetings.question_id", question_id or "")
        span.set_attribute("meetings.limit", limit)
        span.set_attribute("meetings.offset", offset)

        where_sql, params = _build_filters(
            topic_id, theme, question_id, state_code, city, q
        )
        # Recent, unfiltered-by-content pages also carry not-yet-analyzed meetings.
        include_unanalyzed = (
            sort_key == "recent"
            and topic_id is None
            and not (theme and theme.strip())
            and not (question_id and question_id.strip())
        )
        span.set_attribute("meetings.include_unanalyzed", include_unanalyzed)

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("meetings-list.query") as qspan:
                    rows = None
                    if include_unanalyzed:
                        u_count, u_list, u_params = _recent_union_sql(
                            state_code, city, q
                        )
                        try:
                            total = int(await conn.fetchval(u_count, *u_params) or 0)
                            rows = await conn.fetch(u_list, *u_params, limit, offset)
                        except asyncpg.exceptions.UndefinedTableError as e:
                            # recent_transcribed_meeting not deployed here yet:
                            # serve the analyzed meetings alone, as before.
                            logger.warning(
                                "recent_transcribed_meeting unavailable ({}); "
                                "serving analyzed meetings only", e,
                            )
                            rows = None
                    if rows is None:
                        if sort_key == "recent":
                            # Dates later than today are bad data (#472).
                            where_sql = (
                                f"({where_sql}) AND ({_MEETING_DATE_SORT} IS NULL "
                                f"OR {_MEETING_DATE_SORT} <= current_date)"
                            )
                        count_sql = (
                            f"SELECT COUNT(*) FROM meeting_browse mb WHERE {where_sql}"
                        )
                        total = int(await conn.fetchval(count_sql, *params) or 0)

                        limit_idx = len(params) + 1
                        offset_idx = len(params) + 2
                        list_sql = f"""
                            SELECT {_CARD_COLS}
                            FROM meeting_browse mb
                            WHERE {where_sql}
                            ORDER BY {_ORDER_BY[sort_key]}, mb.event_meeting_id DESC
                            LIMIT ${limit_idx} OFFSET ${offset_idx}
                        """
                        rows = await conn.fetch(list_sql, *params, limit, offset)
                    qspan.set_attribute("meetings.total", total)
                    qspan.set_attribute("meetings.row_count", len(rows))
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 — surface a clean 500
            span.record_exception(e)
            logger.error("Meetings list query failed: {}", e)
            raise HTTPException(status_code=500, detail="Failed to load meetings")

        items = [_build_card(r) for r in rows]
        span.set_attribute("meetings.card_count", len(items))
        logger.info(
            "🗂️ Meetings list -> {}/{} cards (sort={}, topic={}, state={}, city={})",
            len(items), total, sort_key, topic_id, state_code, city,
        )

        return MeetingListResponse(
            items=items,
            pagination=MeetingListPagination(
                total=total, limit=limit, offset=offset
            ),
        )
