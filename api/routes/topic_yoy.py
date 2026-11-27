"""
Every main topic, last full year against this year (#1343) — the data behind Browse all topics (``/browse-topics/all``).

``GET /api/topics/yoy?state=&city=``
    One row per curated topic (``civicsearch_topic.source = 'curated'``): distinct meetings that discussed it in the
    last full year (``year_a``) and in this year to date (``year_b``), all recorded meetings in the same scope and years
    (``recorded_meeting_year``), and the topic's share of them. ``data-centers`` reads ``data_center_meeting_mention``;
    every other topic reads ``topic_transcript_link`` — the same sources as the topic story's timeline
    (``topic_timeline.py``), so a row here matches the story's Meetings screen for the same scope.

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


class YoyTopic(BaseModel):
    topic_id: int
    slug: str = Field(..., description="civicsearch_topic.query_id; the story lives at /stories/<slug>.")
    name: str
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


def yoy_sql(scope: TimelineScope, ya: int, yb: int) -> tuple[str, list[Any]]:
    """Per curated topic: meetings in each year, the scope's recorded meetings in each year, shares, and the latest
    dated meeting in year_b. One meeting counts once per topic (DISTINCT ON video_id), dated as the timeline dates it;
    dates after today are a wrong source date (#472) and are left out."""
    params: list[Any] = [ya, yb]
    dc = _where(scope, "m.state_code", ("m.jurisdiction_name",), params)
    tl = _where(scope, "l.state_code", ("l.jurisdiction_name",), params)
    rc = _where(scope, "r.state_code", ("r.jurisdiction_name",), params)
    params.append(DATA_CENTERS)
    dc_slug = f"${len(params)}"
    sql = f"""
WITH dc AS (
    SELECT topic_id FROM civicsearch_topic WHERE query_id = {dc_slug} LIMIT 1
), links AS (
    SELECT DISTINCT ON (m.video_id) dc.topic_id, m.video_id, m.meeting_date AS d
    FROM data_center_meeting_mention m CROSS JOIN dc
    WHERE m.meeting_date >= make_date($1, 1, 1) AND m.meeting_date <= least(make_date($2, 12, 31), current_date){_and(dc)}
    UNION ALL
    SELECT DISTINCT ON (l.topic_id, l.video_id) l.topic_id, l.video_id, l.event_date AS d
    FROM topic_transcript_link l
    WHERE l.topic_id IS DISTINCT FROM (SELECT topic_id FROM dc)
      AND l.event_date >= make_date($1, 1, 1) AND l.event_date <= least(make_date($2, 12, 31), current_date){_and(tl)}
), t AS (
    SELECT topic_id,
           count(*) FILTER (WHERE extract(year FROM d)::int = $1)::int AS meetings_a,
           count(*) FILTER (WHERE extract(year FROM d)::int = $2)::int AS meetings_b
    FROM links GROUP BY topic_id
), r AS (
    SELECT coalesce(sum(r.recorded_meetings) FILTER (WHERE r.meeting_year = $1), 0)::int AS recorded_a,
           coalesce(sum(r.recorded_meetings) FILTER (WHERE r.meeting_year = $2), 0)::int AS recorded_b
    FROM recorded_meeting_year r
    WHERE r.meeting_year IN ($1, $2){_and(rc)}
), thru AS (
    SELECT max(d) AS through FROM links WHERE extract(year FROM d)::int = $2
)
SELECT c.topic_id, c.query_id AS slug, c.name,
       coalesce(t.meetings_a, 0) AS meetings_a, coalesce(t.meetings_b, 0) AS meetings_b,
       r.recorded_a, r.recorded_b,
       CASE WHEN r.recorded_a > 0 THEN round(coalesce(t.meetings_a, 0)::numeric / r.recorded_a, 6)::float8 END AS share_a,
       CASE WHEN r.recorded_b > 0 THEN round(coalesce(t.meetings_b, 0)::numeric / r.recorded_b, 6)::float8 END AS share_b,
       thru.through
FROM civicsearch_topic c
CROSS JOIN r CROSS JOIN thru
LEFT JOIN t ON t.topic_id = c.topic_id
WHERE c.source = 'curated'
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
                topic_id=int(r["topic_id"]), slug=r["slug"], name=r["name"], year_a=str(ya), year_b=str(yb),
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
) -> YoyResponse:
    """Every curated topic's meetings and share of recorded meetings, last full year against this year to date.

    Example: ``GET /api/topics/yoy?state=GA``
    """
    scope = build_scope(state, city)
    yb = date.today().year
    ya = yb - 1
    with tracer.start_as_current_span("topics-yoy") as span:
        span.set_attribute("scope.state", scope.state_code or "")
        span.set_attribute("scope.city", scope.city or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                sql, p = yoy_sql(scope, ya, yb)
                rows = [dict(r) for r in await conn.fetch(sql, *p)]
        except Exception as exc:
            logger.exception("topics yoy failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="The topic comparison is unavailable right now.") from exc
        span.set_attribute("topics", len(rows))
    return shape(rows, scope, ya, yb)
