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

Patterns mirror decision_browse.py: asyncpg pool via get_db_pool(), an
OpenTelemetry span around the query work, and the wire-format rule (the meeting
`date` is serialized as an ISO 'YYYY-MM-DD' string or null). meeting_date is TEXT
in the view, so it is coerced to a real date in SQL (``mb.meeting_date::date``,
NULL on a malformed value) and rendered ISO in Python.
"""
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool, normalize_state_input

router = APIRouter(prefix="/meetings", tags=["meetings"])

tracer = trace.get_tracer(__name__)


class MeetingCard(BaseModel):
    """A single meeting browse card — real data only; NULL/0/empty are honest."""
    meeting_id: int
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

# Sort modes. `interesting` keeps meetings without a scored decision last, then
# falls back to recency; `decisions` leads with the busiest meetings.
_ORDER_BY = {
    "recent": "mb.meeting_date DESC NULLS LAST",
    "interesting": (
        "mb.top_interestingness_score DESC NULLS LAST, "
        "mb.meeting_date DESC NULLS LAST"
    ),
    "decisions": (
        "mb.decision_count DESC NULLS LAST, "
        "mb.meeting_date DESC NULLS LAST"
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


def _iso_date(value: Any) -> Optional[str]:
    """Render a date/value as an ISO 'YYYY-MM-DD' string, or None."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_card(row: Any) -> MeetingCard:
    """Shape one public.meeting_browse row into a MeetingCard."""
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

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("meetings-list.query") as qspan:
                    count_sql = (
                        f"SELECT COUNT(*) FROM meeting_browse mb WHERE {where_sql}"
                    )
                    total = int(await conn.fetchval(count_sql, *params) or 0)
                    qspan.set_attribute("meetings.total", total)

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
