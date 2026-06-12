"""
Flat, paginated decision-browse endpoint: GET /api/decisions.

Returns a single flat list of decision cards in the EXACT same shape the
homepage "Contested" lens uses (api/routes/lenses.py `LensCard`), so the
frontend reuses one card component for both the lenses feed and this browse /
filter view. NO transformation logic lives here — the scoring (conflict / money
/ interestingness_score) and the per-decision facts (votes, competing views,
dollar impact) are produced upstream in dbt and read straight off the already-
modeled public.item_interestingness serving table. This endpoint only filters,
orders, paginates, and shapes rows.

Card primitives are imported from lenses.py (`stats_contested`, `build_card`),
which are intentionally public so this list view stays byte-for-byte consistent
with the Contested lens card (same stats, same headline/jurisdiction logic, same
`url` = /decisions/{event_decision_id}).

Filters are all query-time (no new dbt models):
- topic_id    -> resolve_topic_tsquery() + JOIN event_decision.search_tsv
- question_id -> EXISTS against public.question_instance (local_decision)
- state       -> normalize_state_input() -> ii.state_code
- city / q    -> ILIKE over the display columns

Patterns mirror lenses.py / decisions.py: asyncpg pool via get_db_pool(), an
OpenTelemetry span around the query work, and the wire-format rule (each stat
`value` is a string, `date` is an ISO date string) handled by the shared
LensCard helpers.
"""
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.lenses import LensCard, build_card, stats_contested, video_id_subquery
from api.routes.search import resolve_topic_tsquery
from api.routes.search_postgres import get_db_pool, normalize_state_input

router = APIRouter(prefix="/decisions", tags=["decisions"])

tracer = trace.get_tracer(__name__)


class DecisionListPagination(BaseModel):
    """Pagination envelope for the flat decision list."""
    total: int
    limit: int
    offset: int


class DecisionListResponse(BaseModel):
    """A flat, paginated page of Contested-shaped decision cards."""
    items: List[LensCard]
    pagination: DecisionListPagination


# Columns the shared card helpers read off each row. stats_contested() touches
# total_votes / votes_yes / votes_no / competing_views_count / net_dollar_impact;
# build_card() (via headline / jurisdiction_label / iso_date) touches title /
# summary / jurisdiction_name / city / state_code / state / occurred_at /
# event_decision_id. interestingness_score is selected for the `interesting` sort.
_CARD_COLS = """
    ii.event_decision_id,
    ii.title,
    ii.summary,
    ii.jurisdiction_name,
    ii.state_code,
    ii.state,
    ii.city,
    ii.occurred_at,
    ii.votes_yes,
    ii.votes_no,
    ii.total_votes,
    ii.competing_views_count,
    ii.net_dollar_impact,
    ii.interestingness_score
"""

# Sort modes. `contested` leads with the most opposing views, then the closest
# vote among rows that actually have a tally (a 5-4 reads as more contested than
# a 9-0), then most recent. `recent` and `interesting` are straight orderings.
_ORDER_BY = {
    "contested": (
        "ii.competing_views_count DESC NULLS LAST, "
        "CASE WHEN COALESCE(ii.total_votes, 0) > 0 "
        "THEN abs(COALESCE(ii.votes_yes, 0) - COALESCE(ii.votes_no, 0)) END ASC NULLS LAST, "
        "ii.occurred_at DESC NULLS LAST"
    ),
    "recent": "ii.occurred_at DESC NULLS LAST",
    "interesting": "ii.interestingness_score DESC NULLS LAST",
}


def _build_filters(
    topic_tsquery: Optional[str],
    question_id: Optional[str],
    state_code: Optional[str],
    city: Optional[str],
    q: Optional[str],
) -> tuple[str, str, List[Any]]:
    """
    Build the shared FROM/JOIN clause + WHERE predicate + ordered params.

    Returns (from_sql, where_sql, params). `from_sql` always starts with
    ``item_interestingness ii`` and only adds the event_decision JOIN when a topic
    filter is active (so the common path stays a single-table scan). `where_sql`
    is a complete predicate ('TRUE' when unfiltered) and `params` are positional
    ($1, $2, ...) in the order the clauses reference them — the caller appends
    LIMIT / OFFSET (list endpoint) or nothing (count).
    """
    from_sql = "item_interestingness ii"
    clauses: List[str] = []
    params: List[Any] = []
    idx = 1

    if topic_tsquery is not None:
        # Narrow to decisions whose searchable text matches the topic's keyword
        # set. search_tsv is the GIN-indexed vector on event_decision; the topic
        # OR-tsquery is built injection-safe by resolve_topic_tsquery().
        from_sql += (
            " JOIN event_decision ed "
            "ON ed.event_decision_id = ii.event_decision_id"
        )
        clauses.append(f"ed.search_tsv @@ to_tsquery('english', ${idx})")
        params.append(topic_tsquery)
        idx += 1

    if question_id:
        clauses.append(
            f"EXISTS (SELECT 1 FROM question_instance qi "
            f"WHERE qi.source_id = ii.event_decision_id "
            f"AND qi.source_type = 'local_decision' "
            f"AND qi.question_id = ${idx})"
        )
        params.append(question_id)
        idx += 1

    if state_code:
        clauses.append(f"ii.state_code = ${idx}")
        params.append(state_code)
        idx += 1

    if city and city.strip():
        clauses.append(
            f"(ii.city ILIKE ${idx} OR ii.jurisdiction_name ILIKE ${idx})"
        )
        params.append(f"%{city.strip()}%")
        idx += 1

    if q and q.strip():
        clauses.append(
            f"(ii.title ILIKE ${idx} OR ii.summary ILIKE ${idx} "
            f"OR ii.primary_theme ILIKE ${idx} OR ii.jurisdiction_name ILIKE ${idx})"
        )
        params.append(f"%{q.strip()}%")
        idx += 1

    where_sql = " AND ".join(clauses) if clauses else "TRUE"
    return from_sql, where_sql, params


@router.get("", response_model=DecisionListResponse)
async def list_decisions(
    topic_id: Optional[int] = Query(
        None, description="Named civic topic (public.civicsearch_topic) — matches "
                          "the topic's keyword set against the decision text.",
    ),
    question_id: Optional[str] = Query(
        None, description="Policy-question id — keep only decisions that "
                          "instantiate it (public.question_instance).",
    ),
    state: Optional[str] = Query(
        None, description="2-letter code or full state name (normalized).",
    ),
    city: Optional[str] = Query(
        None, description="City name (ILIKE on city / jurisdiction_name).",
    ),
    q: Optional[str] = Query(
        None, description="Free-text filter (ILIKE) over title / summary / "
                          "theme / jurisdiction.",
    ),
    sort: str = Query(
        "contested",
        description="contested | recent | interesting (default contested).",
    ),
    limit: int = Query(24, ge=1, le=100, description="Page size (1..100)."),
    offset: int = Query(0, ge=0, description="Pagination offset."),
) -> DecisionListResponse:
    """
    Flat, paginated list of decision cards (same shape as the Contested lens).

    Reads public.item_interestingness and renders each row with the shared
    Contested-lens card helpers, so the frontend can reuse one card component.
    All filters are optional and query-time; `total` is a COUNT over the same
    filtered set (ignoring limit/offset). A `topic_id` that resolves to no usable
    keywords returns an empty page with total 0 (an empty topic must not silently
    fall through to the unfiltered feed).

    Example::

        GET /api/decisions?state=MA&sort=contested&limit=24&offset=0
    """
    sort_key = (sort or "contested").lower()
    if sort_key not in _ORDER_BY:
        raise HTTPException(
            status_code=400,
            detail=f"sort must be one of {sorted(_ORDER_BY)} (got '{sort}')",
        )
    state_code = normalize_state_input(state)
    q = q.strip() if q and q.strip() else None

    with tracer.start_as_current_span("decisions-list") as span:
        span.set_attribute("decisions.sort", sort_key)
        span.set_attribute("decisions.state_code", state_code or "")
        span.set_attribute("decisions.city", city or "")
        span.set_attribute("decisions.q", q or "")
        span.set_attribute("decisions.topic_id", topic_id or 0)
        span.set_attribute("decisions.question_id", question_id or "")
        span.set_attribute("decisions.limit", limit)
        span.set_attribute("decisions.offset", offset)

        # Resolve the topic to an OR-tsquery first. A supplied-but-empty topic
        # (unknown id / no usable keywords) means "this topic has no matches" —
        # return an honest empty page rather than the whole unfiltered feed.
        topic_tsquery: Optional[str] = None
        if topic_id is not None:
            topic_tsquery = await resolve_topic_tsquery(topic_id)
            span.set_attribute("decisions.topic_resolved", topic_tsquery is not None)
            if topic_tsquery is None:
                return DecisionListResponse(
                    items=[],
                    pagination=DecisionListPagination(
                        total=0, limit=limit, offset=offset
                    ),
                )

        from_sql, where_sql, params = _build_filters(
            topic_tsquery, question_id, state_code, city, q
        )

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("decisions-list.query") as qspan:
                    count_sql = f"SELECT COUNT(*) FROM {from_sql} WHERE {where_sql}"
                    total = int(await conn.fetchval(count_sql, *params) or 0)
                    qspan.set_attribute("decisions.total", total)

                    limit_idx = len(params) + 1
                    offset_idx = len(params) + 2
                    list_sql = f"""
                        SELECT {_CARD_COLS}, {video_id_subquery('ii')}
                        FROM {from_sql}
                        WHERE {where_sql}
                        ORDER BY {_ORDER_BY[sort_key]}, ii.event_decision_id DESC
                        LIMIT ${limit_idx} OFFSET ${offset_idx}
                    """
                    rows = await conn.fetch(list_sql, *params, limit, offset)
                    qspan.set_attribute("decisions.row_count", len(rows))
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 — surface a clean 500
            span.record_exception(e)
            logger.error("Decisions list query failed: {}", e)
            raise HTTPException(status_code=500, detail="Failed to load decisions")

        items = [build_card(r, "Contested", stats_contested(r)) for r in rows]
        span.set_attribute("decisions.card_count", len(items))
        logger.info(
            "🗂️ Decisions list -> {}/{} cards (sort={}, state={}, city={})",
            len(items), total, sort_key, state_code, city,
        )

        return DecisionListResponse(
            items=items,
            pagination=DecisionListPagination(
                total=total, limit=limit, offset=offset
            ),
        )
