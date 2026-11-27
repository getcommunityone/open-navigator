"""
What is coming up on a curated topic (#1302): scheduled meetings, public hearings and the topic's still-open state bills.

``GET /api/topics/{topic}/upcoming?state=&city=&limit=``
    Items from ``public.topic_upcoming`` dated today or later, soonest first, each with the evidence that ties it to the
    topic (``matched_text``, ``<mark>``ed) and the link to take part (agenda, meeting page, livestream or official
    notice). ``counts`` are per kind over every upcoming item in the scope, not just the ones returned.

    ``pending_bills`` are the topic's state bills that are neither enacted nor failed in our copy of OpenStates
    (``public.topic_legislation_bill`` status ``pending`` or ``passed_chamber``), furthest along first, then by latest
    action, and only when their latest action is from last year or this one (a bill untouched since an earlier session
    is not "still open", whatever its status says; #1308). They carry their last action and its date, never a guessed
    next step: our OpenStates copy has no future-dated hearing on a topic bill. A city scope reads its state's bills
    (the legislature is the state's).

    When the scope has nothing upcoming, ``broader`` gives the count one level up (city -> state -> national), so the
    page can say "Nothing upcoming on record for <place>" and offer the wider view.

``{topic}`` is the topic's slug (``water-fluoridation``) or numeric id. Dates go on the wire as ISO strings. A relation
that is not published yet answers 200 with an empty, ``available: false`` result.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.topic_policy import _iso, _state_code, _state_name, _topic_key
from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)

KINDS = ("meeting", "hearing", "deadline", "bill_action")
#: Most items one call returns.
MAX_ITEMS = 50
#: Still-open bills listed (the total is always given).
PENDING_BILLS = 5


class UpcomingCounts(BaseModel):
    meeting: int = 0
    hearing: int = 0
    deadline: int = 0
    bill_action: int = 0


class UpcomingItem(BaseModel):
    upcoming_id: str
    kind: str  # meeting | hearing | deadline | bill_action
    match_basis: str  # agenda_text | official_notice | place_discussed_before
    date: str
    time: str | None = None
    jurisdiction_name: str | None = None
    state_code: str
    state: str | None = None
    body_name: str | None = None
    title: str | None = None
    location: str | None = None
    source_url: str
    source_label: str
    matched_text: str
    prior_meeting_date: str | None = None
    prior_url: str | None = None
    tentative: bool = False


class PendingBill(BaseModel):
    bill_id: str
    identifier: str | None = None
    title: str | None = None
    state_code: str
    state: str | None = None
    status: str  # pending | passed_chamber
    last_action: str | None = None
    last_action_date: str | None = None
    url: str | None = None


class PendingBills(BaseModel):
    total: int = 0
    #: The latest action date on any of the topic's bills in our copy: how current the bill data is.
    latest_action_seen: str | None = None
    items: list[PendingBill] = []


class BroaderScope(BaseModel):
    state_code: str | None = None
    label: str
    total: int


class TopicUpcoming(BaseModel):
    topic: str
    topic_id: int | None = None
    state_code: str | None = None
    state: str | None = None
    city: str | None = None
    available: bool = False
    as_of: str
    #: When the newest source row was fetched, and when the mart was built.
    last_updated: str | None = None
    built_at: str | None = None
    total: int = 0
    counts: UpcomingCounts = UpcomingCounts()
    items: list[UpcomingItem] = []
    pending_bills: PendingBills = PendingBills()
    broader: BroaderScope | None = None


# $1 topic, $2 state (or null), $3 city (or null), $4 limit.
_ITEMS_SQL = """
    SELECT u.topic_upcoming_id, u.topic_id, u.kind, u.match_basis, u.item_date, u.item_time, u.jurisdiction_name,
           u.state_code, u.state, u.body_name, u.title, u.location, u.source_url, u.source_label, u.matched_text,
           u.prior_meeting_date, u.prior_url, u.tentative
    FROM topic_upcoming u
    WHERE (u.topic_slug = $1::text OR u.topic_id::text = $1::text)
      AND u.item_date >= current_date
      AND ($2::text IS NULL OR u.state_code = $2::text)
      AND ($3::text IS NULL OR lower(u.jurisdiction_name) = lower($3::text))
    ORDER BY u.item_date, array_position(ARRAY['hearing', 'deadline', 'bill_action', 'meeting'], u.kind),
             array_position(ARRAY['official_notice', 'agenda_text', 'place_discussed_before'], u.match_basis),
             u.jurisdiction_name, u.topic_upcoming_id
    LIMIT $4
"""

# $1 topic, $2 state (or null), $3 city (or null).
_COUNTS_SQL = """
    SELECT u.kind, count(*)::int AS n, max(u.topic_id) AS topic_id,
           max(u.source_updated_at) AS last_updated, max(u.built_at) AS built_at
    FROM topic_upcoming u
    WHERE (u.topic_slug = $1::text OR u.topic_id::text = $1::text)
      AND u.item_date >= current_date
      AND ($2::text IS NULL OR u.state_code = $2::text)
      AND ($3::text IS NULL OR lower(u.jurisdiction_name) = lower($3::text))
    GROUP BY u.kind
"""

# Whether the topic has any row at all (even past ones): says the mart covers it.
_TOPIC_SQL = """
    SELECT max(u.topic_id) AS topic_id, max(u.built_at) AS built_at
    FROM topic_upcoming u
    WHERE u.topic_slug = $1::text OR u.topic_id::text = $1::text
"""

# $1 topic, $2 state (or null), $3 limit.
_PENDING_SQL = """
    SELECT b.bill_id, b.identifier, b.title, b.state_code, b.state, b.status, b.last_action_description,
           b.last_action_date, b.url, count(*) OVER ()::int AS total
    FROM topic_legislation_bill b
    WHERE (b.topic_query_id = $1::text OR b.topic_id::text = $1::text)
      AND b.status IN ('pending', 'passed_chamber')
      AND b.year >= extract(year FROM current_date)::int - 1
      -- A chaptered or signed bill is law, whatever its status column says (#1308).
      AND coalesce(b.last_action_description, '') !~* '(chapter|acts of assembly|signed by (the )?governor|approved by (the )?governor|became law)'
      AND ($2::text IS NULL OR b.state_code = $2::text)
    ORDER BY array_position(ARRAY['passed_chamber', 'pending'], b.status), b.last_action_date DESC NULLS LAST,
             b.identifier
    LIMIT $3
"""

_LATEST_ACTION_SQL = """
    SELECT max(b.last_action_date) AS latest
    FROM topic_legislation_bill b
    WHERE b.topic_query_id = $1::text OR b.topic_id::text = $1::text
"""


def _counts(rows: list[Any]) -> UpcomingCounts:
    c = UpcomingCounts()
    for r in rows:
        if r["kind"] in KINDS:
            setattr(c, r["kind"], getattr(c, r["kind"]) + int(r["n"]))
    return c


def _total(c: UpcomingCounts) -> int:
    return c.meeting + c.hearing + c.deadline + c.bill_action


def shape_items(rows: list[Any]) -> list[UpcomingItem]:
    out: list[UpcomingItem] = []
    for r in rows:
        if r["item_date"] is None or not r["source_url"] or not r["matched_text"]:
            continue  # never an undated item or one without its evidence and link
        out.append(
            UpcomingItem(
                upcoming_id=r["topic_upcoming_id"],
                kind=r["kind"],
                match_basis=r["match_basis"],
                date=r["item_date"].isoformat(),
                time=r["item_time"],
                jurisdiction_name=r["jurisdiction_name"],
                state_code=r["state_code"],
                state=_state_name(r["state"], r["state_code"]),
                body_name=r["body_name"],
                title=r["title"],
                location=r["location"],
                source_url=r["source_url"],
                source_label=r["source_label"],
                matched_text=r["matched_text"],
                prior_meeting_date=_iso(r["prior_meeting_date"]),
                prior_url=r["prior_url"],
                tentative=bool(r["tentative"]),
            )
        )
    return out


def shape_pending(rows: list[Any], latest: Any) -> PendingBills:
    return PendingBills(
        total=int(rows[0]["total"]) if rows else 0,
        latest_action_seen=_iso(latest),
        items=[
            PendingBill(
                bill_id=r["bill_id"],
                identifier=r["identifier"],
                title=r["title"],
                state_code=r["state_code"],
                state=_state_name(r["state"], r["state_code"]),
                status=r["status"],
                last_action=r["last_action_description"],
                last_action_date=_iso(r["last_action_date"]),
                url=r["url"],
            )
            for r in rows
        ],
    )


@router.get("/{topic}/upcoming", response_model=TopicUpcoming)
async def topic_upcoming(
    topic: str = Path(..., description="Topic slug (e.g. water-fluoridation) or numeric topic id."),
    state: str | None = Query(None, description="Optional 2-letter state code."),
    city: str | None = Query(None, max_length=80, description="Optional city or government name (needs state)."),
    limit: int = Query(12, ge=1, le=MAX_ITEMS),
) -> TopicUpcoming:
    """Scheduled meetings, hearings and still-open state bills on a topic, from today on (#1302)."""
    key = _topic_key(topic)
    state_code = _state_code(state)
    city_name = city.strip() if city and city.strip() and state_code else None
    today = date.today().isoformat()
    base = dict(topic=key, state_code=state_code, state=_state_name(None, state_code), city=city_name, as_of=today)
    with tracer.start_as_current_span("topics.upcoming") as span:
        span.set_attribute("topics.topic", key)
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.city", city_name or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                meta = await conn.fetchrow(_TOPIC_SQL, key)
                count_rows = list(await conn.fetch(_COUNTS_SQL, key, state_code, city_name))
                item_rows = list(await conn.fetch(_ITEMS_SQL, key, state_code, city_name, limit))
                try:
                    pending_rows = list(await conn.fetch(_PENDING_SQL, key, state_code, PENDING_BILLS))
                    latest = await conn.fetchrow(_LATEST_ACTION_SQL, key)
                except asyncpg.exceptions.UndefinedTableError:
                    pending_rows, latest = [], None
                counts = _counts(count_rows)
                broader: BroaderScope | None = None
                if _total(counts) == 0 and state_code:
                    # One level up: the city's state, else national.
                    up_state = state_code if city_name else None
                    up_rows = list(await conn.fetch(_COUNTS_SQL, key, up_state, None))
                    broader = BroaderScope(
                        state_code=up_state,
                        label=_state_name(None, up_state) or up_state if up_state else "National",
                        total=_total(_counts(up_rows)),
                    )
        except asyncpg.exceptions.UndefinedTableError:
            span.set_attribute("topics.relation_missing", True)
            return TopicUpcoming(**base)
        except Exception as exc:
            logger.exception("topic upcoming failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="What's coming up on this topic is unavailable right now.") from exc

        latest_val = latest["latest"] if latest else None
        last_updated = max((r["last_updated"] for r in count_rows if r["last_updated"] is not None), default=None)
        topic_id = (meta["topic_id"] if meta else None) or next((r["topic_id"] for r in count_rows), None)
        span.set_attribute("topics.upcoming_total", _total(counts))
        return TopicUpcoming(
            **base,
            topic_id=topic_id,
            available=bool(meta and meta["built_at"] is not None) or bool(pending_rows),
            last_updated=_iso(last_updated),
            built_at=_iso(meta["built_at"]) if meta else None,
            total=_total(counts),
            counts=counts,
            items=shape_items(item_rows),
            pending_bills=shape_pending(pending_rows, latest_val),
            broader=broader,
        )
