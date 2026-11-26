"""
Topic timeline and period comparison (#1140) — the data behind a story's Meetings screen.

``GET /api/topics/{topic}/timeline?state=&city=``
    Meetings per year that discussed the topic in the scope, the passages behind them (data centers only), all recorded
    meetings per year in the same scope (``recorded_meeting_year``) and the topic's share of them; plus a milestone
    track of dated events: meetings where officials approved, denied, tabled or adopted a moratorium (an AI reading,
    ``data_center_meeting_lean.dc_outcome`` / ``topic_meeting_lean.outcome_group``), and state bills enacted
    (``topic_legislation_bill``, read only when the relation exists).

``GET /api/topics/{topic}/period-compare?state=&from=&to=``
    The topic's share of recorded meetings in two years, per state (national scope) or per government (state scope).
    Rows with too few recorded meetings in either year, or too few topic meetings across both, are hidden; the
    thresholds are returned with the rows (``min_recorded_meetings``, ``min_topic_meetings``).

Topic slugs are ``civicsearch_topic.query_id`` (``data-centers``, ``water-fluoridation``, …). ``data-centers`` reads
``data_center_meeting_mention``; every other curated topic reads ``topic_transcript_link``.

Years go on the wire as strings (CLAUDE.md, calendar years). Nothing is defaulted: a year with no recorded meetings in
the scope is absent (the chart draws a gap), ``share`` is null when it can't be computed, and a missing relation
(``recorded_meeting_year`` or ``topic_legislation_bill`` before its mart lands) returns what can be read instead of a 500.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.search_postgres import (
    STATE_NAME_TO_CODE,
    get_db_pool,
    normalize_state_input,
)

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)

DATA_CENTERS = "data-centers"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_CODE_TO_STATE = {code: name for name, code in STATE_NAME_TO_CODE.items()}

#: Period dumbbell: a row needs at least this many recorded meetings in EACH year, so one meeting can't swing a share
#: from 0% to 100%.
MIN_RECORDED_MEETINGS = 20
#: …and at least this many topic meetings across the two years, so a row shows the topic, not noise.
MIN_TOPIC_MEETINGS = 3

MilestoneKind = Literal["approved", "denied", "tabled", "moratorium", "bill_enacted"]

#: dc_outcome → milestone kind (data centers). Other outcomes (discussed, no item) are not milestones.
DC_OUTCOME_KIND: dict[str, MilestoneKind] = {
    "approved": "approved",
    "denied": "denied",
    "tabled_or_deferred": "tabled",
    "moratorium": "moratorium",
}
#: topic_meeting_lean.outcome_group → milestone kind (other topics).
TOPIC_OUTCOME_KIND: dict[str, MilestoneKind] = {
    "advanced": "approved",
    "blocked": "denied",
    "tabled_or_deferred": "tabled",
    "moratorium": "moratorium",
}


class TimelineScope(BaseModel):
    level: Literal["national", "state", "city"]
    state_code: str | None = None
    state: str | None = None
    city: str | None = None


class TimelineYear(BaseModel):
    year: str = Field(..., description="Calendar year, as a string.")
    meetings: int = Field(..., description="Distinct meetings in the scope that year whose transcript discussed the topic.")
    passages: int | None = Field(
        None, description="Quoted passages behind those meetings (data centers only; null for other topics)."
    )
    all_recorded_meetings: int | None = Field(
        None, description="All recorded (transcribed) meetings in the scope that year; null when not known."
    )
    share: float | None = Field(
        None, description="meetings / all_recorded_meetings (0–1), or null when it can't be computed."
    )


class TimelineMilestone(BaseModel):
    date: str = Field(..., description="ISO date of the meeting or the bill's latest action.")
    kind: MilestoneKind
    place: str | None = None
    state_code: str | None = None
    title: str | None = None
    url: str | None = None
    video_id: str | None = None
    source: Literal["ai_reading", "record"] = Field(
        ..., description="ai_reading: a classifier's reading of the meeting transcript; record: an official record (a bill)."
    )


class TopicTimelineResponse(BaseModel):
    topic: str
    topic_name: str | None = None
    scope: TimelineScope
    years: list[TimelineYear]
    undated_meetings: int = Field(0, description="Topic meetings in the scope with no usable date (not on the line).")
    total_meetings: int = Field(0, description="Distinct topic meetings in the scope, dated or not.")
    total_passages: int | None = None
    milestones: list[TimelineMilestone]
    coverage_available: bool = Field(..., description="False when recorded_meeting_year can't be read (no share series).")
    bills_available: bool = Field(..., description="False when topic_legislation_bill is not in the database yet.")


class PeriodRow(BaseModel):
    key: str
    label: str
    earlier_share: float
    later_share: float
    earlier_meetings: int
    later_meetings: int
    earlier_recorded: int
    later_recorded: int


class PeriodCompareResponse(BaseModel):
    topic: str
    scope: TimelineScope
    from_year: str
    to_year: str
    grain: Literal["state", "place"]
    min_recorded_meetings: int
    min_topic_meetings: int
    hidden_rows: int = Field(..., description="Rows left out under the thresholds.")
    rows: list[PeriodRow]


# --- scope -----------------------------------------------------------------------------------------------------------


def _clean(v: str | None) -> str | None:
    s = (v or "").strip()
    return s or None


def build_scope(state: str | None, city: str | None) -> TimelineScope:
    code = normalize_state_input(_clean(state))
    c = _clean(city) if code else None  # a city needs its state; a lone city is not a scope we can apply
    return TimelineScope(
        level="city" if c else ("state" if code else "national"),
        state_code=code,
        state=_CODE_TO_STATE.get(code) if code else None,
        city=c,
    )


def _check_slug(topic: str) -> str:
    slug = topic.strip().lower()
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=404, detail="Unknown topic.")
    return slug


def _where(scope: TimelineScope, state_col: str, place_cols: tuple[str, ...], params: list[Any]) -> list[str]:
    out: list[str] = []
    if scope.state_code:
        params.append(scope.state_code)
        out.append(f"{state_col} = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        out.append("(" + " OR ".join(f"{c} ILIKE ${len(params)}" for c in place_cols) + ")")
    return out


# --- SQL builders (pure, unit-tested) --------------------------------------------------------------------------------


def topic_years_sql(slug: str, topic_id: int | None, scope: TimelineScope) -> tuple[str, list[Any]]:
    """Per-year distinct topic meetings (and passages for data centers); year NULL = undated."""
    params: list[Any] = []
    if slug == DATA_CENTERS:
        w = _where(scope, "m.state_code", ("m.jurisdiction_name",), params)
        sql = (
            "SELECT extract(year FROM m.meeting_date)::int AS y, count(DISTINCT m.video_id)::int AS meetings, "
            "count(*)::int AS passages FROM data_center_meeting_mention m "
            f"WHERE {' AND '.join(w) or 'TRUE'} GROUP BY 1 ORDER BY 1"
        )
        return sql, params
    params.append(topic_id)
    w = ["l.topic_id = $1", *_where(scope, "l.state_code", ("l.city", "l.jurisdiction_name"), params)]
    sql = (
        "SELECT extract(year FROM CASE WHEN l.event_date > current_date THEN NULL ELSE l.event_date END)::int AS y, "
        "count(DISTINCT l.video_id)::int AS meetings, NULL::int AS passages FROM topic_transcript_link l "
        f"WHERE {' AND '.join(w)} GROUP BY 1 ORDER BY 1"
    )
    return sql, params


def recorded_years_sql(scope: TimelineScope) -> tuple[str, list[Any]]:
    params: list[Any] = []
    w = _where(scope, "r.state_code", ("r.jurisdiction_name",), params)
    sql = (
        "SELECT r.meeting_year AS y, sum(r.recorded_meetings)::int AS recorded FROM recorded_meeting_year r "
        f"WHERE {' AND '.join(w) or 'TRUE'} GROUP BY 1 ORDER BY 1"
    )
    return sql, params


def milestones_sql(slug: str, scope: TimelineScope) -> tuple[str, list[Any]]:
    """Meetings with an approval, denial, tabling or moratorium (an AI reading), newest last."""
    params: list[Any] = []
    if slug == DATA_CENTERS:
        w = [
            "l.meeting_date IS NOT NULL",
            "NOT coalesce(l.excluded_no_item, false)",
            "l.dc_outcome IN ('approved', 'denied', 'tabled_or_deferred', 'moratorium')",
            *_where(scope, "l.state_code", ("l.jurisdiction_name",), params),
        ]
        sql = (
            "SELECT l.meeting_date, l.dc_outcome AS outcome, l.jurisdiction_name, l.state_code, l.video_id, "
            "t.meeting_title AS title, t.video_url FROM data_center_meeting_lean l "
            "LEFT JOIN LATERAL (SELECT m.meeting_title, m.video_url FROM data_center_meeting_mention m "
            "WHERE m.video_id = l.video_id LIMIT 1) t ON TRUE "
            f"WHERE {' AND '.join(w)} ORDER BY l.meeting_date, l.video_id"
        )
        return sql, params
    params.append(slug)
    w = [
        "l.topic_slug = $1",
        "l.meeting_date IS NOT NULL",
        "NOT coalesce(l.excluded_no_item, false)",
        "l.outcome_group IN ('advanced', 'blocked', 'tabled_or_deferred', 'moratorium')",
        *_where(scope, "l.state_code", ("l.jurisdiction_name",), params),
    ]
    sql = (
        "SELECT l.meeting_date, l.outcome_group AS outcome, l.jurisdiction_name, l.state_code, l.video_id, "
        "t.event_title AS title, t.video_url FROM topic_meeting_lean l "
        "LEFT JOIN LATERAL (SELECT k.event_title, k.video_url FROM topic_transcript_link k "
        "WHERE k.video_id = l.video_id AND k.topic_id = l.topic_id LIMIT 1) t ON TRUE "
        f"WHERE {' AND '.join(w)} ORDER BY l.meeting_date, l.video_id"
    )
    return sql, params


def bills_sql(topic_id: int, scope: TimelineScope) -> tuple[str, list[Any]]:
    params: list[Any] = [topic_id]
    w = ["b.topic_id = $1", "b.status = 'enacted'", "b.latest_action_date IS NOT NULL"]
    if scope.state_code:
        params.append(scope.state_code)
        w.append(f"b.state_code = ${len(params)}")
    sql = (
        "SELECT b.latest_action_date, b.state_code, b.state, b.identifier, b.title, b.url "
        f"FROM topic_legislation_bill b WHERE {' AND '.join(w)} ORDER BY b.latest_action_date, b.bill_id"
    )
    return sql, params


def period_sql(slug: str, topic_id: int | None, scope: TimelineScope, y0: int, y1: int) -> tuple[str, list[Any], str]:
    """Topic meetings and recorded meetings per key for the two years. key = state (national) or government (state)."""
    grain = "place" if scope.state_code else "state"
    params: list[Any] = [y0, y1]
    if slug == DATA_CENTERS:
        tkey = "m.jurisdiction_name" if grain == "place" else "m.state_code"
        tw = ["extract(year FROM m.meeting_date)::int IN ($1, $2)", f"{tkey} IS NOT NULL"]
        if scope.state_code:
            params.append(scope.state_code)
            tw.append(f"m.state_code = ${len(params)}")
        topic_cte = (
            f"SELECT {tkey} AS k, extract(year FROM m.meeting_date)::int AS y, count(DISTINCT m.video_id)::int AS n "
            f"FROM data_center_meeting_mention m WHERE {' AND '.join(tw)} GROUP BY 1, 2"
        )
    else:
        params.append(topic_id)
        tid = len(params)
        tkey = "l.jurisdiction_name" if grain == "place" else "l.state_code"
        tw = [f"l.topic_id = ${tid}", "extract(year FROM l.event_date)::int IN ($1, $2)", f"{tkey} IS NOT NULL"]
        if scope.state_code:
            params.append(scope.state_code)
            tw.append(f"l.state_code = ${len(params)}")
        topic_cte = (
            f"SELECT {tkey} AS k, extract(year FROM l.event_date)::int AS y, count(DISTINCT l.video_id)::int AS n "
            f"FROM topic_transcript_link l WHERE {' AND '.join(tw)} GROUP BY 1, 2"
        )
    rkey = "r.jurisdiction_name" if grain == "place" else "r.state_code"
    rw = ["r.meeting_year IN ($1, $2)", f"{rkey} IS NOT NULL"]
    if scope.state_code:
        params.append(scope.state_code)
        rw.append(f"r.state_code = ${len(params)}")
    sql = (
        f"WITH t AS ({topic_cte}), "
        f"r AS (SELECT {rkey} AS k, r.meeting_year AS y, sum(r.recorded_meetings)::int AS n "
        f"FROM recorded_meeting_year r WHERE {' AND '.join(rw)} GROUP BY 1, 2) "
        "SELECT r.k, "
        "coalesce(max(t.n) FILTER (WHERE r.y = $1), 0)::int AS t0, coalesce(max(t.n) FILTER (WHERE r.y = $2), 0)::int AS t1, "
        "coalesce(max(r.n) FILTER (WHERE r.y = $1), 0)::int AS r0, coalesce(max(r.n) FILTER (WHERE r.y = $2), 0)::int AS r1 "
        "FROM r LEFT JOIN t ON t.k = r.k AND t.y = r.y GROUP BY r.k"
    )
    return sql, params, grain


# --- shaping (pure, unit-tested) -------------------------------------------------------------------------------------


def _share(n: int, d: int | None) -> float | None:
    if d is None or d <= 0 or n > d:
        return None
    return round(n / d, 6)


def shape_years(
    topic_rows: list[dict[str, Any]], recorded: dict[int, int] | None
) -> tuple[list[TimelineYear], int, int, int | None]:
    """Years from the first year the topic came up to the last year on record. A year with no recorded meetings and
    no topic meetings is left out (a gap). Returns (years, undated, total meetings, total passages)."""
    by_year: dict[int, dict[str, Any]] = {}
    undated = 0
    total_m = 0
    passages: int | None = None
    for r in topic_rows:
        m = int(r["meetings"] or 0)
        total_m += m
        if r.get("passages") is not None:
            passages = (passages or 0) + int(r["passages"])
        if r["y"] is None:
            undated += m
        else:
            by_year[int(r["y"])] = r
    if not by_year:
        return [], undated, total_m, passages
    first = min(by_year)
    last = max([*by_year, *((recorded or {}).keys())])
    out: list[TimelineYear] = []
    for y in range(first, last + 1):
        t = by_year.get(y)
        rec = recorded.get(y) if recorded is not None else None
        if t is None and not rec:
            continue  # nothing on record that year: a gap, never a zero
        m = int(t["meetings"]) if t else 0
        out.append(
            TimelineYear(
                year=str(y),
                meetings=m,
                passages=(int(t["passages"]) if t and t.get("passages") is not None else (0 if t is None and passages is not None else None)),
                all_recorded_meetings=rec if rec else None,
                share=_share(m, rec),
            )
        )
    return out, undated, total_m, passages


def shape_milestones(slug: str, rows: list[dict[str, Any]], bills: list[dict[str, Any]]) -> list[TimelineMilestone]:
    kinds = DC_OUTCOME_KIND if slug == DATA_CENTERS else TOPIC_OUTCOME_KIND
    out: list[TimelineMilestone] = []
    for r in rows:
        kind = kinds.get(r["outcome"] or "")
        if not kind or r["meeting_date"] is None:
            continue
        d = r["meeting_date"]
        out.append(
            TimelineMilestone(
                date=d.isoformat() if isinstance(d, date) else str(d),
                kind=kind,
                place=r["jurisdiction_name"],
                state_code=r["state_code"],
                title=r["title"],
                url=r["video_url"] or (f"https://www.youtube.com/watch?v={r['video_id']}" if r["video_id"] else None),
                video_id=r["video_id"],
                source="ai_reading",
            )
        )
    for b in bills:
        d = b["latest_action_date"]
        out.append(
            TimelineMilestone(
                date=d.isoformat() if isinstance(d, date) else str(d),
                kind="bill_enacted",
                place=b["state"] or b["state_code"],
                state_code=b["state_code"],
                title=" · ".join(x for x in (b["identifier"], b["title"]) if x) or None,
                url=b["url"],
                source="record",
            )
        )
    out.sort(key=lambda m: (m.date, m.kind))
    return out


def shape_period_rows(rows: list[dict[str, Any]], grain: str) -> tuple[list[PeriodRow], int]:
    kept: list[PeriodRow] = []
    hidden = 0
    for r in rows:
        t0, t1, r0, r1 = int(r["t0"]), int(r["t1"]), int(r["r0"]), int(r["r1"])
        if r0 < MIN_RECORDED_MEETINGS or r1 < MIN_RECORDED_MEETINGS or t0 + t1 < MIN_TOPIC_MEETINGS or t0 > r0 or t1 > r1:
            if t0 + t1 > 0:
                hidden += 1
            continue
        key = str(r["k"])
        label = _CODE_TO_STATE.get(key, key) if grain == "state" else key
        kept.append(
            PeriodRow(
                key=key, label=label,
                earlier_share=round(t0 / r0, 6), later_share=round(t1 / r1, 6),
                earlier_meetings=t0, later_meetings=t1, earlier_recorded=r0, later_recorded=r1,
            )
        )
    kept.sort(key=lambda x: (-x.later_share, x.label))
    return kept, hidden


# --- routes ----------------------------------------------------------------------------------------------------------


async def _topic(conn, slug: str) -> tuple[int | None, str | None]:
    row = await conn.fetchrow("SELECT topic_id, name FROM civicsearch_topic WHERE query_id = $1 LIMIT 1", slug)
    if row is None:
        if slug == DATA_CENTERS:
            return None, "Data centers"
        raise HTTPException(status_code=404, detail="Unknown topic.")
    return int(row["topic_id"]), row["name"]


async def _exists(conn, rel: str) -> bool:
    return bool(await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", rel))


@router.get("/{topic}/timeline", response_model=TopicTimelineResponse)
async def topic_timeline(
    topic: str = Path(..., description="Topic slug (civicsearch_topic.query_id), e.g. data-centers."),
    state: str | None = Query(None, description="2-letter state code (or full name)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the government's name. Needs state."),
) -> TopicTimelineResponse:
    """Meetings per year for a topic and scope, the share of all recorded meetings, and the milestone track.

    Example: ``GET /api/topics/data-centers/timeline?state=TX``
    """
    slug = _check_slug(topic)
    scope = build_scope(state, city)
    with tracer.start_as_current_span("topic-timeline") as span:
        span.set_attribute("topic", slug)
        span.set_attribute("scope.state", scope.state_code or "")
        span.set_attribute("scope.city", scope.city or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                topic_id, name = await _topic(conn, slug)
                sql, p = topic_years_sql(slug, topic_id, scope)
                topic_rows = [dict(r) for r in await conn.fetch(sql, *p)]
                coverage = await _exists(conn, "recorded_meeting_year")
                recorded: dict[int, int] | None = None
                if coverage:
                    sql, p = recorded_years_sql(scope)
                    recorded = {int(r["y"]): int(r["recorded"]) for r in await conn.fetch(sql, *p)}
                lean_rel = "data_center_meeting_lean" if slug == DATA_CENTERS else "topic_meeting_lean"
                ms_rows: list[dict[str, Any]] = []
                if await _exists(conn, lean_rel):
                    sql, p = milestones_sql(slug, scope)
                    ms_rows = [dict(r) for r in await conn.fetch(sql, *p)]
                bills_ok = topic_id is not None and await _exists(conn, "topic_legislation_bill")
                bill_rows: list[dict[str, Any]] = []
                # A bill is state-level: a city scope shows its state's bills only when asked at state scope.
                if bills_ok and scope.level != "city":
                    sql, p = bills_sql(topic_id, scope)  # type: ignore[arg-type]
                    bill_rows = [dict(r) for r in await conn.fetch(sql, *p)]
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("topic timeline failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's timeline is unavailable right now.") from exc

    years, undated, total_m, passages = shape_years(topic_rows, recorded)
    milestones = shape_milestones(slug, ms_rows, bill_rows)
    return TopicTimelineResponse(
        topic=slug, topic_name=name, scope=scope, years=years, undated_meetings=undated,
        total_meetings=total_m, total_passages=passages, milestones=milestones,
        coverage_available=coverage, bills_available=bool(bills_ok),
    )


@router.get("/{topic}/period-compare", response_model=PeriodCompareResponse)
async def topic_period_compare(
    topic: str = Path(..., description="Topic slug, e.g. data-centers."),
    state: str | None = Query(None, description="2-letter state code: rows become the state's governments."),
    from_year: int | None = Query(None, alias="from", ge=1990, le=2100, description="Earlier year (default: last year)."),
    to_year: int | None = Query(None, alias="to", ge=1990, le=2100, description="Later year (default: this year)."),
) -> PeriodCompareResponse:
    """The topic's share of recorded meetings in two years, per state (national) or per government (state scope).

    Example: ``GET /api/topics/data-centers/period-compare?state=TX&from=2025&to=2026``
    """
    slug = _check_slug(topic)
    scope = build_scope(state, None)
    y1 = to_year or date.today().year
    y0 = from_year or (y1 - 1)
    if y0 >= y1:
        raise HTTPException(status_code=422, detail="'from' must be earlier than 'to'.")
    with tracer.start_as_current_span("topic-period-compare") as span:
        span.set_attribute("topic", slug)
        span.set_attribute("scope.state", scope.state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                topic_id, _ = await _topic(conn, slug)
                grain = "place" if scope.state_code else "state"
                rows: list[dict[str, Any]] = []
                if await _exists(conn, "recorded_meeting_year"):
                    sql, p, grain = period_sql(slug, topic_id, scope, y0, y1)
                    rows = [dict(r) for r in await conn.fetch(sql, *p)]
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("topic period compare failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This comparison is unavailable right now.") from exc
    kept, hidden = shape_period_rows(rows, grain)
    return PeriodCompareResponse(
        topic=slug, scope=scope, from_year=str(y0), to_year=str(y1), grain=grain,  # type: ignore[arg-type]
        min_recorded_meetings=MIN_RECORDED_MEETINGS, min_topic_meetings=MIN_TOPIC_MEETINGS,
        hidden_rows=hidden, rows=kept,
    )
