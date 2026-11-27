"""
Every major meeting topic, last full year against this year (#1343, #1361) — the data behind Browse all topics
(``/browse-topics/all``).

``GET /api/topics/yoy?state=&city=&source=``
    One row per topic in ``civicsearch_topic`` (all 95 curated + CivicSearch topics by default, or filtered by
    ``source=curated|civicsearch``): distinct meetings that discussed it in the last full year (``year_a``) and in
    this year to date (``year_b``) from ``topic_meeting_year``, all recorded meetings in the same scope and years
    (``recorded_meeting_year``), and the topic's share of them. Each row also carries ``source`` and ``has_story``
    (whether a live story exists at ``/stories/<slug>``) so the page can surface rising or high-volume topics that
    don't have a story yet.

Everything is counted in one SQL statement; Python only shapes the rows. Nothing is defaulted:

* A topic with fewer than ``MIN_MEETINGS`` topic meetings in either year, or a scope with fewer than
  ``MIN_RECORDED_MEETINGS`` recorded meetings in either year, is ``comparable = false``: the page lists it under
  "Too few meetings to compare" and draws no change.
* ``share_*`` is null when the scope recorded no meetings that year.
* ``year_b_through`` is the latest dated topic meeting this year in the scope (the partial year's label, e.g.
  "Jan–Nov 2026"); null when the scope has none.
* ``thin_year`` names a year whose recorded meetings are under ``THIN_RATIO`` of the other year's, so its count
  (not its share) would read as a real drop. Same ratio as the story timeline's thin-year rule (#1207).

Years go on the wire as strings (CLAUDE.md, calendar years).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.search_postgres import get_db_pool
from api.routes.topic_timeline import (
    DATA_CENTERS,
    MIN_RECORDED_MEETINGS,
    TimelineScope,
    _where,
    build_scope,
)

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)

#: A topic needs at least this many meetings in EACH year to be compared (the shared minimum, ``MIN_SCOPE_MEETINGS``
#: in ``web_app/src/utils/resolveStoryScope.ts``): one or two meetings can't carry a change.
MIN_MEETINGS = 5
#: A year is thin when it recorded under this share of the other year's meetings (``THIN_RATIO``, storyTimeline.ts).
THIN_RATIO = 0.25
VALID_SOURCES = frozenset({"curated", "civicsearch"})


class YoyTopic(BaseModel):
    topic_id: int
    slug: str = Field(..., description="civicsearch_topic.query_id; live stories live at /stories/<slug>.")
    name: str
    source: str = Field(..., description="civicsearch_topic.source: 'curated' or 'civicsearch'.")
    has_story: bool = Field(..., description="True when the topic already has a live story at /stories/<slug>.")
    year_a: str
    year_b: str
    meetings_a: int = Field(..., description="Distinct meetings in the scope in year_a whose transcript discussed the topic.")
    meetings_b: int = Field(..., description="…in year_b, to date.")
    recorded_a: int = Field(..., description="All recorded (transcribed) meetings in the scope in year_a.")
    recorded_b: int
    share_a: float | None = Field(None, description="meetings_a / recorded_a (0–1); null when recorded_a is 0.")
    share_b: float | None = None
    comparable: bool = Field(..., description="False when either year has too few topic or recorded meetings.")


class YoyResponse(BaseModel):
    scope: TimelineScope
    year_a: str
    year_b: str
    year_b_through: str | None = Field(None, description="ISO date of the latest topic meeting in year_b in the scope.")
    year_b_partial: bool = Field(..., description="True unless year_b_through is 31 December.")
    recorded_a: int
    recorded_b: int
    thin_year: str | None = Field(None, description="A year with thin recording coverage in this scope, if any.")
    min_meetings: int = MIN_MEETINGS
    min_recorded_meetings: int = MIN_RECORDED_MEETINGS
    topics: list[YoyTopic]


def _and(w: list[str]) -> str:
    return "".join(f" AND {x}" for x in w)


def yoy_sql(scope: TimelineScope, ya: int, yb: int, source: str | None = None) -> tuple[str, list[Any]]:
    """Per topic in civicsearch_topic: meetings in each year from ``topic_meeting_year``, the scope's recorded
    meetings in each year from ``recorded_meeting_year``, shares, ``has_story``, and the latest dated meeting in
    year_b."""
    params: list[Any] = [ya, yb]
    mw = _where(scope, "m.state_code", ("m.jurisdiction_name",), params)
    rw = _where(scope, "r.state_code", ("r.jurisdiction_name",), params)
    params.append(DATA_CENTERS)
    dc_slug = f"${len(params)}"
    source_where = ""
    if source is not None:
        params.append(source)
        source_where = f"WHERE c.source = ${len(params)}"
    sql = f"""
WITH live_ids AS (
    SELECT DISTINCT topic_id FROM topic_transcript_link
    UNION
    SELECT topic_id FROM civicsearch_topic WHERE query_id = {dc_slug}
), m_scoped AS (
    SELECT m.topic_id, m.meeting_year, m.meetings, m.latest_meeting_date
    FROM topic_meeting_year m
    WHERE m.meeting_year IN ($1, $2){_and(mw)}
), t AS (
    SELECT topic_id,
           coalesce(sum(meetings) FILTER (WHERE meeting_year = $1), 0)::int AS meetings_a,
           coalesce(sum(meetings) FILTER (WHERE meeting_year = $2), 0)::int AS meetings_b
    FROM m_scoped
    GROUP BY topic_id
), r AS (
    SELECT coalesce(sum(r.recorded_meetings) FILTER (WHERE r.meeting_year = $1), 0)::int AS recorded_a,
           coalesce(sum(r.recorded_meetings) FILTER (WHERE r.meeting_year = $2), 0)::int AS recorded_b
    FROM recorded_meeting_year r
    WHERE r.meeting_year IN ($1, $2){_and(rw)}
), thru AS (
    SELECT max(latest_meeting_date) FILTER (WHERE meeting_year = $2) AS through
    FROM m_scoped
)
SELECT c.topic_id, c.query_id AS slug, c.name, c.source,
       (c.source = 'curated' AND live_ids.topic_id IS NOT NULL) AS has_story,
       coalesce(t.meetings_a, 0) AS meetings_a, coalesce(t.meetings_b, 0) AS meetings_b,
       r.recorded_a, r.recorded_b,
       CASE WHEN r.recorded_a > 0 THEN round(coalesce(t.meetings_a, 0)::numeric / r.recorded_a, 6)::float8 END AS share_a,
       CASE WHEN r.recorded_b > 0 THEN round(coalesce(t.meetings_b, 0)::numeric / r.recorded_b, 6)::float8 END AS share_b,
       thru.through
FROM civicsearch_topic c
CROSS JOIN r CROSS JOIN thru
LEFT JOIN t ON t.topic_id = c.topic_id
LEFT JOIN live_ids ON live_ids.topic_id = c.topic_id
{source_where}
ORDER BY c.topic_id
"""
    return sql, params


def thin_year(ya: int, yb: int, ra: int, rb: int) -> str | None:
    """The year that recorded under THIN_RATIO of the other's meetings, if either did."""
    if ra > 0 and rb < THIN_RATIO * ra:
        return str(yb)
    if rb > 0 and ra < THIN_RATIO * rb:
        return str(ya)
    return None


def shape(rows: list[dict[str, Any]], scope: TimelineScope, ya: int, yb: int) -> YoyResponse:
    ra = int(rows[0]["recorded_a"]) if rows else 0
    rb = int(rows[0]["recorded_b"]) if rows else 0
    through = rows[0]["through"] if rows else None
    topics: list[YoyTopic] = []
    for r in rows:
        ma, mb = int(r["meetings_a"]), int(r["meetings_b"])
        ok = (
            ma >= MIN_MEETINGS and mb >= MIN_MEETINGS
            and ra >= MIN_RECORDED_MEETINGS and rb >= MIN_RECORDED_MEETINGS
            and ma <= ra and mb <= rb  # a share over 100% is a broken join, never a value to draw
            and r["share_a"] is not None and r["share_b"] is not None
        )
        topics.append(
            YoyTopic(
                topic_id=int(r["topic_id"]), slug=r["slug"], name=r["name"],
                source=r.get("source") or "curated",
                has_story=bool(r.get("has_story")),
                year_a=str(ya), year_b=str(yb),
                meetings_a=ma, meetings_b=mb, recorded_a=ra, recorded_b=rb,
                share_a=r["share_a"], share_b=r["share_b"], comparable=ok,
            )
        )
    thru = through.isoformat() if isinstance(through, date) else (str(through) if through else None)
    return YoyResponse(
        scope=scope, year_a=str(ya), year_b=str(yb), year_b_through=thru,
        year_b_partial=not (thru and thru.endswith("-12-31")),
        recorded_a=ra, recorded_b=rb, thin_year=thin_year(ya, yb, ra, rb), topics=topics,
    )


@router.get("/yoy", response_model=YoyResponse)
async def topics_yoy(
    state: str | None = Query(None, description="2-letter state code (or full name)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the government's name. Needs state."),
    source: str | None = Query(None, description="Optional filter: 'curated' or 'civicsearch'. Omit for all topics."),
) -> YoyResponse:
    """Every major topic's meetings and share of recorded meetings, last full year against this year to date.

    Example: ``GET /api/topics/yoy?state=GA``
    """
    norm_source = source.strip().lower() if source is not None and source.strip() else None
    if norm_source is not None and norm_source not in VALID_SOURCES:
        raise HTTPException(status_code=422, detail="source must be 'curated' or 'civicsearch'.")

    scope = build_scope(state, city)
    yb = date.today().year
    ya = yb - 1
    with tracer.start_as_current_span("topics-yoy") as span:
        span.set_attribute("scope.state", scope.state_code or "")
        span.set_attribute("scope.city", scope.city or "")
        span.set_attribute("source", norm_source or "all")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                sql, p = yoy_sql(scope, ya, yb, norm_source)
                rows = [dict(r) for r in await conn.fetch(sql, *p)]
        except Exception as exc:
            logger.exception("topics yoy failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="The topic comparison is unavailable right now.") from exc
        span.set_attribute("topics", len(rows))
    return shape(rows, scope, ya, yb)
