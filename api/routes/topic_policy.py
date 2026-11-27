"""
Where policy is moving on a topic (#1274): state bills, what local bodies voted, and the positions the public took.

``GET /api/topics/{topic}/legislation``
    State bills about a curated topic (``public.topic_legislation_bill``) counted per state, category, latest-action
    year and status, with the topic's category vocabulary (``public.topic_legislation_category``): small enough for the
    map to recolour by period and direction on the client for any topic (guns has ~17,000 bills). Category and status
    come from documented dbt rules; nothing is estimated, and a state with no matching bill is simply absent.

``GET /api/topics/{topic}/legislation/{state}?since_year=&category=&limit=``
    One state's bills, furthest status first (enacted > passed a chamber > pending > failed), newest first, at most
    ``limit`` (200), with how many match.

``GET /api/topics/{topic}/positions?state=``
    Meetings per public position, from the AI reading of each meeting (``public.topic_meeting_lean``). Topics read with
    their own position labels (water fluoridation: five positions) count ``public_position``; the others count
    ``public_lean``. Meetings flagged ``excluded_no_item`` (a keyword false hit) are left out. Counts of meetings, never
    of speakers.

``GET /api/topics/{topic}/local-actions?state=``
    Meetings where the local body acted on the topic, in the same AI reading: ``outcome_group`` advanced (voted to keep,
    start or approve), blocked (voted to end, deny or limit) or tabled_or_deferred, by state, by year and as a list
    linking each meeting.

``{topic}`` is the topic's slug (``water-fluoridation``) or numeric id. Years go on the wire as strings (CLAUDE.md,
calendar years). A relation that is not published yet answers 200 with an empty result.
"""

from __future__ import annotations

import re
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import STATE_NAME_TO_CODE, get_db_pool

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_STATE_RE = re.compile(r"^[A-Z]{2}$")
_CODE_TO_STATE = {code: name for name, code in STATE_NAME_TO_CODE.items()}


def _state_name(name: str | None, code: str | None) -> str | None:
    """The full state name: the row's own when it is one, else looked up from the code (some rows carry 'GA')."""
    if name and len(name.strip()) > 2:
        return name
    return _CODE_TO_STATE.get(code or "", name)

#: Most advanced first: the state's colour on the map is the first of these any of its bills reached.
STATUS_ORDER = ("enacted", "passed_chamber", "pending", "failed")
#: Water fluoridation's five positions, in display order (llm.typesafe.topic_lean).
FIVE_POSITIONS = ("support_require_all", "support_local_choice", "no_opinion", "oppose_local_choice", "oppose_ban_all")
#: The shared lean labels every other topic uses.
LEAN_POSITIONS = ("mostly_supportive", "mixed", "mostly_opposed")
#: The outcome groups that count as the body acting on the topic.
ACTION_GROUPS = ("advanced", "blocked", "tabled_or_deferred")


def _topic_key(topic: str) -> str:
    key = topic.strip().lower()
    if not _SLUG_RE.match(key):
        raise HTTPException(status_code=400, detail="Unknown topic.")
    return key


def _state_code(state: str | None) -> str | None:
    if not state or not state.strip():
        return None
    code = state.strip().upper()
    if not _STATE_RE.match(code):
        raise HTTPException(status_code=400, detail="state must be a 2-letter state code.")
    return code


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


# ---------------------------------------------------------------------------
# Legislation
# ---------------------------------------------------------------------------

#: Most bills a state list returns at once (a busy topic can have thousands in one state).
MAX_STATE_BILLS = 200


class LegislationCategory(BaseModel):
    category: str
    label: str | None = None
    description: str | None = None
    display_order: int | None = None
    bills: int = 0


class LegislationSummaryRow(BaseModel):
    """Bills in one state with one category, latest-action year and status: what the map colours from."""

    state_code: str
    state: str | None = None
    category: str
    year: str | None = None
    status: str  # enacted | passed_chamber | pending | failed
    bills: int


class LegislationBill(BaseModel):
    bill_id: str
    identifier: str | None = None
    title: str | None = None
    session: str | None = None
    year: str | None = None
    category: str
    status: str  # enacted | passed_chamber | pending | failed
    passed_a_chamber: bool = False
    url: str | None = None
    introduced_date: str | None = None
    last_action_date: str | None = None
    last_action: str | None = None


class TopicLegislation(BaseModel):
    topic: str
    topic_id: int | None = None
    state_code: str | None = None
    available: bool = False
    total_bills: int = 0
    states_with_bills: int = 0
    status_counts: dict[str, int] = {}
    categories: list[LegislationCategory] = []
    summary: list[LegislationSummaryRow] = []


class TopicStateBills(BaseModel):
    topic: str
    state_code: str
    state: str | None = None
    since_year: str | None = None
    category: str | None = None
    #: Bills matching the filters; ``bills`` holds the first ``limit`` of them, furthest status first, newest first.
    matching: int = 0
    limit: int = MAX_STATE_BILLS
    bills: list[LegislationBill] = []


_SUMMARY_SQL = """
    SELECT b.topic_id, b.state_code, b.state, b.category, b.year, b.status, count(*)::int AS bills
    FROM topic_legislation_bill b
    WHERE (b.topic_query_id = $1::text OR b.topic_id::text = $1::text)
    GROUP BY b.topic_id, b.state_code, b.state, b.category, b.year, b.status
    ORDER BY b.state_code, b.year, b.category, b.status
"""

_CATEGORIES_SQL = """
    SELECT c.topic_id, c.category, c.label, c.description, c.display_order
    FROM topic_legislation_category c
    WHERE c.topic_query_id = $1::text OR c.topic_id::text = $1::text
    ORDER BY c.display_order, c.category
"""

# $1 topic, $2 state, $3 since year (or null), $4 category (or null), $5 limit.
_STATE_BILLS_SQL = """
    SELECT b.bill_id, b.state, b.identifier, b.title, b.session, b.year, b.category, b.status, b.passed_a_chamber,
           b.url, b.introduced_date, b.last_action_date, b.last_action_description,
           count(*) OVER ()::int AS matching
    FROM topic_legislation_bill b
    WHERE (b.topic_query_id = $1::text OR b.topic_id::text = $1::text)
      AND b.state_code = $2::text
      AND ($3::int IS NULL OR b.year >= $3::int)
      AND ($4::text IS NULL OR b.category = $4::text)
    ORDER BY array_position(ARRAY['enacted', 'passed_chamber', 'pending', 'failed'], b.status),
             b.last_action_date DESC NULLS LAST, b.identifier
    LIMIT $5
"""


def top_status(statuses: list[str]) -> str:
    """The most advanced status among a state's bills (enacted > passed_chamber > pending > failed)."""
    for s in STATUS_ORDER:
        if s in statuses:
            return s
    return statuses[0] if statuses else "pending"


def shape_legislation(key: str, rows: list[Any], categories: list[Any]) -> TopicLegislation:
    status_counts: dict[str, int] = {}
    cat_counts: dict[str, int] = {}
    states: set[str] = set()
    summary: list[LegislationSummaryRow] = []
    for r in rows:
        n = int(r["bills"])
        states.add(r["state_code"])
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + n
        cat_counts[r["category"]] = cat_counts.get(r["category"], 0) + n
        summary.append(
            LegislationSummaryRow(
                state_code=r["state_code"],
                state=_state_name(r["state"], r["state_code"]),
                category=r["category"],
                year=str(r["year"]) if r["year"] is not None else None,
                status=r["status"],
                bills=n,
            )
        )
    first = rows[0] if rows else (categories[0] if categories else None)
    return TopicLegislation(
        topic=key,
        topic_id=first["topic_id"] if first else None,
        available=bool(categories) or bool(rows),
        total_bills=sum(status_counts.values()),
        states_with_bills=len(states),
        status_counts=status_counts,
        categories=[
            LegislationCategory(
                category=c["category"], label=c["label"], description=c["description"],
                display_order=c["display_order"], bills=cat_counts.get(c["category"], 0),
            )
            for c in categories
        ],
        summary=summary,
    )


def shape_state_bills(
    key: str, state_code: str, since_year: int | None, category: str | None, limit: int, rows: list[Any]
) -> TopicStateBills:
    return TopicStateBills(
        topic=key,
        state_code=state_code,
        state=_state_name(rows[0]["state"] if rows else None, state_code),
        since_year=str(since_year) if since_year is not None else None,
        category=category,
        matching=int(rows[0]["matching"]) if rows else 0,
        limit=limit,
        bills=[
            LegislationBill(
                bill_id=r["bill_id"],
                identifier=r["identifier"],
                title=r["title"],
                session=r["session"],
                year=str(r["year"]) if r["year"] is not None else None,
                category=r["category"],
                status=r["status"],
                passed_a_chamber=bool(r["passed_a_chamber"]),
                url=r["url"],
                introduced_date=_iso(r["introduced_date"]),
                last_action_date=_iso(r["last_action_date"]),
                last_action=r["last_action_description"],
            )
            for r in rows
        ],
    )


@router.get("/{topic}/legislation", response_model=TopicLegislation)
async def topic_legislation(
    topic: str = Path(..., description="Topic slug (e.g. water-fluoridation) or numeric topic id."),
) -> TopicLegislation:
    """State bills about a curated topic, counted per state, category, year and status: what the map colours from
    (#1274). A state's bills themselves come from ``/legislation/{state}``."""
    key = _topic_key(topic)
    with tracer.start_as_current_span("topics.legislation") as span:
        span.set_attribute("topics.topic", key)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                categories = await conn.fetch(_CATEGORIES_SQL, key)
                rows = await conn.fetch(_SUMMARY_SQL, key)
        except asyncpg.exceptions.UndefinedTableError:
            span.set_attribute("topics.relation_missing", True)
            return TopicLegislation(topic=key)
        except Exception as exc:
            logger.exception("topic legislation failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's legislation is unavailable right now.") from exc
        span.set_attribute("topics.summary_rows", len(rows))
        return shape_legislation(key, list(rows), list(categories))


@router.get("/{topic}/legislation/{state}", response_model=TopicStateBills)
async def topic_state_bills(
    topic: str = Path(..., description="Topic slug (e.g. water-fluoridation) or numeric topic id."),
    state: str = Path(..., description="2-letter state code."),
    since_year: int | None = Query(None, ge=1900, le=2100, description="Only bills whose latest action is in this year or later."),
    category: str | None = Query(None, max_length=40, description="Only bills in this category."),
    limit: int = Query(MAX_STATE_BILLS, ge=1, le=MAX_STATE_BILLS),
) -> TopicStateBills:
    """One state's bills on a topic, furthest status first, newest first, with how many match (#1274)."""
    key = _topic_key(topic)
    state_code = _state_code(state)
    assert state_code is not None
    cat = category.strip().lower() if category and category.strip() else None
    with tracer.start_as_current_span("topics.state-bills") as span:
        span.set_attribute("topics.topic", key)
        span.set_attribute("topics.state", state_code)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(_STATE_BILLS_SQL, key, state_code, since_year, cat, limit)
        except asyncpg.exceptions.UndefinedTableError:
            span.set_attribute("topics.relation_missing", True)
            return TopicStateBills(topic=key, state_code=state_code, state=_state_name(None, state_code), limit=limit)
        except Exception as exc:
            logger.exception("topic state bills failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This state's bills are unavailable right now.") from exc
        return shape_state_bills(key, state_code, since_year, cat, limit, list(rows))

# ---------------------------------------------------------------------------
# Public positions in meetings
# ---------------------------------------------------------------------------


class PositionCount(BaseModel):
    key: str
    meetings: int = 0


class TopicPositions(BaseModel):
    topic: str
    state_code: str | None = None
    available: bool = False
    # 'five' = the topic's own five positions (public_position); 'lean' = the shared mostly_* labels (public_lean).
    scale: str | None = None
    read_meetings: int = 0
    spoke_meetings: int = 0
    did_not_speak: int = 0
    states: int = 0
    options: list[PositionCount] = []


_POSITIONS_SQL = """
    SELECT coalesce(l.public_position, l.public_lean) AS position,
           (l.public_position IS NOT NULL) AS five,
           count(*)::int AS meetings,
           count(DISTINCT l.state_code)::int AS states
    FROM topic_meeting_lean l
    JOIN civicsearch_topic t ON t.topic_id = l.topic_id
    WHERE (t.query_id = $1::text OR l.topic_id::text = $1::text)
      AND NOT coalesce(l.excluded_no_item, false)
      AND ($2::text IS NULL OR l.state_code = $2::text)
    GROUP BY 1, 2
"""

_POSITIONS_STATES_SQL = """
    SELECT count(DISTINCT l.state_code)::int AS states
    FROM topic_meeting_lean l
    JOIN civicsearch_topic t ON t.topic_id = l.topic_id
    WHERE (t.query_id = $1::text OR l.topic_id::text = $1::text)
      AND NOT coalesce(l.excluded_no_item, false)
      AND coalesce(l.public_position, l.public_lean) <> 'did_not_speak'
      AND ($2::text IS NULL OR l.state_code = $2::text)
"""


def shape_positions(key: str, state_code: str | None, rows: list[Any], states: int) -> TopicPositions:
    five = any(r["five"] for r in rows)
    order = FIVE_POSITIONS if five else LEAN_POSITIONS
    counts: dict[str, int] = {}
    silent = 0
    read = 0
    for r in rows:
        if bool(r["five"]) != five:
            continue  # a stray row read under the other scale is not mixed into this one
        read += r["meetings"]
        if r["position"] == "did_not_speak":
            silent += r["meetings"]
        elif r["position"] in order:
            counts[r["position"]] = counts.get(r["position"], 0) + r["meetings"]
    return TopicPositions(
        topic=key,
        state_code=state_code,
        available=bool(rows),
        scale=("five" if five else "lean") if rows else None,
        read_meetings=read,
        spoke_meetings=sum(counts.values()),
        did_not_speak=silent,
        states=states,
        options=[PositionCount(key=k, meetings=counts.get(k, 0)) for k in order],
    )


@router.get("/{topic}/positions", response_model=TopicPositions)
async def topic_positions(
    topic: str = Path(..., description="Topic slug (e.g. water-fluoridation) or numeric topic id."),
    state: str | None = Query(None, description="Optional 2-letter state code."),
) -> TopicPositions:
    """Meetings per public position, from the AI reading of each meeting (#1274)."""
    key = _topic_key(topic)
    state_code = _state_code(state)
    with tracer.start_as_current_span("topics.positions") as span:
        span.set_attribute("topics.topic", key)
        span.set_attribute("topics.state", state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(_POSITIONS_SQL, key, state_code)
                srow = await conn.fetchrow(_POSITIONS_STATES_SQL, key, state_code)
        except asyncpg.exceptions.UndefinedTableError:
            span.set_attribute("topics.relation_missing", True)
            return TopicPositions(topic=key, state_code=state_code)
        except Exception as exc:
            logger.exception("topic positions failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's positions are unavailable right now.") from exc
        return shape_positions(key, state_code, list(rows), int(srow["states"]) if srow else 0)


# ---------------------------------------------------------------------------
# Local actions in meetings
# ---------------------------------------------------------------------------


class ActionCounts(BaseModel):
    advanced: int = 0
    blocked: int = 0
    tabled_or_deferred: int = 0


class ActionState(BaseModel):
    state_code: str
    state: str | None = None
    counts: ActionCounts


class ActionYear(BaseModel):
    year: str
    counts: ActionCounts


class ActionMeeting(BaseModel):
    video_id: str
    jurisdiction_name: str | None = None
    state_code: str | None = None
    meeting_date: str | None = None
    outcome_group: str
    outcome: str | None = None
    outcome_p: float | None = None
    url: str | None = None
    title: str | None = None


class TopicLocalActions(BaseModel):
    topic: str
    state_code: str | None = None
    available: bool = False
    total: int = 0
    undated: int = 0
    totals: ActionCounts = ActionCounts()
    by_state: list[ActionState] = []
    by_year: list[ActionYear] = []
    meetings: list[ActionMeeting] = []


_ACTIONS_SQL = """
    SELECT l.video_id, l.jurisdiction_name, l.state_code, l.state, l.meeting_date, l.outcome_group, l.outcome,
           l.outcome_p, k.video_url, k.event_title
    FROM topic_meeting_lean l
    JOIN civicsearch_topic t ON t.topic_id = l.topic_id
    LEFT JOIN LATERAL (
        SELECT x.video_url, x.event_title FROM topic_transcript_link x
        WHERE x.video_id = l.video_id AND x.topic_id = l.topic_id LIMIT 1
    ) k ON TRUE
    WHERE (t.query_id = $1::text OR l.topic_id::text = $1::text)
      AND l.outcome_group IN ('advanced', 'blocked', 'tabled_or_deferred')
      AND NOT coalesce(l.excluded_no_item, false)
      AND ($2::text IS NULL OR l.state_code = $2::text)
    ORDER BY l.meeting_date DESC NULLS LAST, l.video_id
"""


def _bump(c: ActionCounts, group: str) -> None:
    setattr(c, group, getattr(c, group) + 1)


def shape_actions(key: str, state_code: str | None, rows: list[Any]) -> TopicLocalActions:
    totals = ActionCounts()
    states: dict[str, ActionState] = {}
    years: dict[str, ActionCounts] = {}
    meetings: list[ActionMeeting] = []
    undated = 0
    for r in rows:
        g = r["outcome_group"]
        if g not in ACTION_GROUPS:
            continue
        _bump(totals, g)
        sc = r["state_code"]
        if sc:
            st = states.get(sc)
            if st is None:
                st = states[sc] = ActionState(state_code=sc, state=_state_name(r["state"], sc), counts=ActionCounts())
            _bump(st.counts, g)
        d = r["meeting_date"]
        if d is None:
            undated += 1
        else:
            y = str(d.year)
            years.setdefault(y, ActionCounts())
            _bump(years[y], g)
        meetings.append(
            ActionMeeting(
                video_id=r["video_id"],
                jurisdiction_name=r["jurisdiction_name"],
                state_code=sc,
                meeting_date=_iso(d),
                outcome_group=g,
                outcome=r["outcome"],
                outcome_p=float(r["outcome_p"]) if r["outcome_p"] is not None else None,
                url=r["video_url"],
                title=r["event_title"],
            )
        )
    total = totals.advanced + totals.blocked + totals.tabled_or_deferred
    return TopicLocalActions(
        topic=key,
        state_code=state_code,
        available=bool(rows),
        total=total,
        undated=undated,
        totals=totals,
        by_state=sorted(
            states.values(),
            key=lambda s: (-(s.counts.advanced + s.counts.blocked + s.counts.tabled_or_deferred), s.state_code),
        ),
        by_year=[ActionYear(year=y, counts=years[y]) for y in sorted(years)],
        meetings=meetings,
    )


@router.get("/{topic}/local-actions", response_model=TopicLocalActions)
async def topic_local_actions(
    topic: str = Path(..., description="Topic slug (e.g. water-fluoridation) or numeric topic id."),
    state: str | None = Query(None, description="Optional 2-letter state code."),
) -> TopicLocalActions:
    """Meetings where the local body voted on the topic or put it off, by state and year (#1274)."""
    key = _topic_key(topic)
    state_code = _state_code(state)
    with tracer.start_as_current_span("topics.local-actions") as span:
        span.set_attribute("topics.topic", key)
        span.set_attribute("topics.state", state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(_ACTIONS_SQL, key, state_code)
        except asyncpg.exceptions.UndefinedTableError:
            span.set_attribute("topics.relation_missing", True)
            return TopicLocalActions(topic=key, state_code=state_code)
        except Exception as exc:
            logger.exception("topic local actions failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's local actions are unavailable right now.") from exc
        span.set_attribute("topics.actions", len(rows))
        return shape_actions(key, state_code, list(rows))
