"""
What happened next on a curated topic (#1314): the chain from the meetings where it came up to what followed.

``GET /api/topics/{topic}/outcomes?state=&city=``
    One count per step, each with up to three linked examples (source id, link, date, place):

    ``meetings``      meetings whose transcript discussed the topic (``public.topic_transcript_link``).
    ``public``        of those read by the AI (Jev), meetings where the public spoke, by lean (opposed / mixed /
                      supportive): ``topic_meeting_lean.public_lean``, or ``data_center_meeting_lean`` for data centers.
                      Meetings, never speakers. Keyword false hits (``excluded_no_item``) are left out.
    ``actions``       meetings where the council or board acted, in the same reading: advanced (kept, started, approved),
                      blocked (ended, denied), moratorium (data centers) or tabled / put off.
    ``bills``         the topic's state bills by status (``public.topic_legislation_bill``); a city reads its state.
    ``linked_bills``  meetings in scope that named one of the topic's own state bills, by evidence only
                      (``public.meeting_bill_link``: the bill's number written in the transcript, a decision, the agenda
                      or minutes, in the same state).
    ``next``          what's coming up (``public.topic_upcoming`` from today on) and the state bills still open, as on
                      ``/upcoming`` (#1302).

    Nothing is estimated: a step with no record has ``count: 0`` and the page says "No recorded … yet". A relation that
    is not published answers that step as ``available: false``.

``{topic}`` is the topic's slug (``water-fluoridation``) or numeric id. Dates go on the wire as ISO strings.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool
from api.routes.topic_policy import _iso, _state_code, _state_name, _topic_key
from api.routes.topic_upcoming import _PENDING_SQL

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)

EXAMPLES = 3
DATA_CENTERS = "data-centers"

#: Public lean -> the three words the page uses. Silence is counted apart.
LEAN = {
    "mostly_opposed": "opposed",
    "mixed": "mixed",
    "mostly_supportive": "supportive",
    "mostly_supported": "supportive",
}
SILENT = {"did_not_speak", "no_public_comment_on_data_center"}
#: Outcome -> the four groups of "what officials did".
ACTION = {
    "advanced": "advanced",
    "approved": "advanced",
    "blocked": "blocked",
    "denied": "blocked",
    "moratorium": "moratorium",
    "tabled_or_deferred": "tabled",
}


class Example(BaseModel):
    id: str
    title: str | None = None
    date: str | None = None
    state_code: str | None = None
    jurisdiction_name: str | None = None
    url: str | None = None
    #: A short verbatim line (``<mark>``ed where it is matched text) or the reading's label.
    detail: str | None = None


class Step(BaseModel):
    available: bool = False
    count: int = 0
    examples: list[Example] = []


class PublicStep(Step):
    read: int = 0
    silent: int = 0
    by_lean: dict[str, int] = {}


class ActionStep(Step):
    by_outcome: dict[str, int] = {}


class BillStep(Step):
    by_status: dict[str, int] = {}


class LinkStep(Step):
    bills: int = 0
    by_method: dict[str, int] = {}


class NextStep(Step):
    upcoming: int = 0
    pending_bills: int = 0


class Steps(BaseModel):
    meetings: Step = Step()
    public: PublicStep = PublicStep()
    actions: ActionStep = ActionStep()
    bills: BillStep = BillStep()
    linked_bills: LinkStep = LinkStep()
    next: NextStep = NextStep()


class TopicOutcomes(BaseModel):
    topic: str
    state_code: str | None = None
    state: str | None = None
    city: str | None = None
    steps: Steps = Steps()


# $1 topic, $2 state, $3 city -- every query below takes these three.
_TOPIC_FILTER = "(t.query_id = $1::text OR t.topic_id::text = $1::text)"
_PLACE = "($2::text IS NULL OR {a}.state_code = $2::text) AND ($3::text IS NULL OR lower({a}.jurisdiction_name) = lower($3::text))"

_MEETINGS_SQL = f"""
    SELECT count(DISTINCT k.video_id)::int AS n
    FROM topic_transcript_link k JOIN civicsearch_topic t ON t.topic_id = k.topic_id
    WHERE {_TOPIC_FILTER} AND {_PLACE.format(a='k')}
"""
_MEETINGS_EX_SQL = f"""
    SELECT k.video_id, k.event_title, k.event_date, k.state_code, k.jurisdiction_name, k.video_url, k.evidence_passage
    FROM topic_transcript_link k JOIN civicsearch_topic t ON t.topic_id = k.topic_id
    WHERE {_TOPIC_FILTER} AND {_PLACE.format(a='k')} AND k.evidence_passage LIKE '%<mark>%'
    ORDER BY k.event_date DESC NULLS LAST, k.video_id
    LIMIT {EXAMPLES}
"""

# The AI reading, one row per meeting: lean and outcome in the topic's own words.
_READING_GENERIC = """
    SELECT l.video_id, l.state_code, l.jurisdiction_name, l.meeting_date, l.public_lean AS lean,
           l.outcome_group AS outcome
    FROM topic_meeting_lean l JOIN civicsearch_topic t ON t.topic_id = l.topic_id
    WHERE (t.query_id = $1::text OR t.topic_id::text = $1::text) AND NOT coalesce(l.excluded_no_item, false)
"""
_READING_DC = """
    SELECT d.video_id, d.state_code, d.jurisdiction_name, d.meeting_date, d.public_lean AS lean,
           d.dc_outcome AS outcome
    FROM data_center_meeting_lean d
    -- $1 (the topic) is data-centers here; named so every query takes the same three parameters.
    WHERE $1::text IS NOT NULL AND NOT coalesce(d.excluded_no_item, false) AND d.dc_outcome IS DISTINCT FROM 'no_data_center_item'
"""


def _reading_sql(dc: bool) -> str:
    return _READING_DC if dc else _READING_GENERIC


def _lean_counts_sql(dc: bool) -> str:
    return f"""
        WITH r AS ({_reading_sql(dc)})
        SELECT r.lean, count(*)::int AS n FROM r WHERE {_PLACE.format(a='r')} GROUP BY r.lean
    """


def _action_counts_sql(dc: bool) -> str:
    return f"""
        WITH r AS ({_reading_sql(dc)})
        SELECT r.outcome, count(*)::int AS n FROM r WHERE {_PLACE.format(a='r')} GROUP BY r.outcome
    """


def _examples_sql(dc: bool, column: str, values: tuple[str, ...]) -> str:
    vals = ", ".join(f"'{v}'" for v in values)
    # The newest few first, then their titles and links: the lookup runs for three rows, not the whole reading.
    return f"""
        WITH r AS ({_reading_sql(dc)}),
        tp AS (SELECT topic_id FROM civicsearch_topic WHERE query_id = $1::text OR topic_id::text = $1::text LIMIT 1),
        top AS (
            SELECT r.* FROM r
            WHERE {_PLACE.format(a='r')} AND r.{column} IN ({vals})
            ORDER BY r.meeting_date DESC NULLS LAST, r.video_id
            LIMIT {EXAMPLES}
        )
        SELECT top.video_id, top.state_code, top.jurisdiction_name, top.meeting_date, top.{column} AS label,
               k.event_title, k.video_url
        FROM top
        LEFT JOIN LATERAL (
            SELECT x.event_title, x.video_url FROM topic_transcript_link x, tp
            WHERE x.video_id = top.video_id AND x.topic_id = tp.topic_id LIMIT 1
        ) k ON TRUE
        ORDER BY top.meeting_date DESC NULLS LAST, top.video_id
    """


_BILLS_SQL = """
    SELECT b.status, count(*)::int AS n
    FROM topic_legislation_bill b
    WHERE (b.topic_query_id = $1::text OR b.topic_id::text = $1::text) AND ($2::text IS NULL OR b.state_code = $2::text)
    GROUP BY b.status
"""
_BILLS_EX_SQL = f"""
    SELECT b.bill_id, b.identifier, b.title, b.status, b.state_code, b.last_action_date, b.last_action_description, b.url
    FROM topic_legislation_bill b
    WHERE (b.topic_query_id = $1::text OR b.topic_id::text = $1::text) AND ($2::text IS NULL OR b.state_code = $2::text)
    ORDER BY array_position(ARRAY['enacted', 'passed_chamber', 'pending', 'failed'], b.status),
             b.last_action_date DESC NULLS LAST, b.identifier
    LIMIT {EXAMPLES}
"""

# Links in scope: a meeting there that named one of the topic's own state bills. (Any bill named at a meeting about the
# topic is not enough: a council meeting that touched data centers also names firefighter and cannabis bills.)
_LINKS_CTE = f"""
    WITH tb AS (
        SELECT b.bill_id FROM topic_legislation_bill b
        WHERE (b.topic_query_id = $1::text OR b.topic_id::text = $1::text) AND ($2::text IS NULL OR b.state_code = $2::text)
    ),
    l AS (
        SELECT m.* FROM meeting_bill_link m JOIN tb ON tb.bill_id = m.bill_uid
        WHERE {_PLACE.format(a='m')}
    )
"""
_LINKS_SQL = _LINKS_CTE + """
    SELECT count(DISTINCT l.meeting_key)::int AS meetings, count(DISTINCT l.bill_uid)::int AS bills FROM l
"""
_LINKS_METHOD_SQL = _LINKS_CTE + """
    SELECT l.match_method, count(*)::int AS n FROM l GROUP BY l.match_method
"""
_LINKS_EX_SQL = _LINKS_CTE + f"""
    SELECT l.meeting_bill_link_id, l.identifier, l.bill_title, l.meeting_date, l.state_code, l.jurisdiction_name, l.url,
           l.match_text, l.match_method
    FROM l
    ORDER BY l.meeting_date DESC NULLS LAST, l.meeting_bill_link_id
    LIMIT {EXAMPLES}
"""

_UPCOMING_SQL = f"""
    SELECT count(*)::int AS n FROM topic_upcoming u
    WHERE (u.topic_slug = $1::text OR u.topic_id::text = $1::text) AND u.item_date >= current_date
      AND {_PLACE.format(a='u')}
"""
_UPCOMING_EX_SQL = f"""
    SELECT u.topic_upcoming_id, u.title, u.item_date, u.state_code, u.jurisdiction_name, u.source_url, u.kind
    FROM topic_upcoming u
    WHERE (u.topic_slug = $1::text OR u.topic_id::text = $1::text) AND u.item_date >= current_date
      AND {_PLACE.format(a='u')}
    ORDER BY u.item_date, u.topic_upcoming_id
    LIMIT {EXAMPLES}
"""


async def _try(conn: Any, sql: str, *args: Any) -> list[Any] | None:
    """Rows, or None when the relation is not published (that step is then unavailable)."""
    try:
        return list(await conn.fetch(sql, *args))
    except asyncpg.exceptions.UndefinedTableError:
        return None


def shape_public(rows: list[Any] | None, examples: list[Any] | None) -> PublicStep:
    if rows is None:
        return PublicStep()
    by: dict[str, int] = {}
    silent = read = 0
    for r in rows:
        n = int(r["n"])
        read += n
        if r["lean"] in SILENT:
            silent += n
        elif r["lean"] in LEAN:
            by[LEAN[r["lean"]]] = by.get(LEAN[r["lean"]], 0) + n
    return PublicStep(
        available=True,
        count=sum(by.values()),
        read=read,
        silent=silent,
        by_lean=by,
        examples=[_reading_example(e) for e in examples or []],
    )


def shape_actions(rows: list[Any] | None, examples: list[Any] | None) -> ActionStep:
    if rows is None:
        return ActionStep()
    by: dict[str, int] = {}
    for r in rows:
        g = ACTION.get(r["outcome"] or "")
        if g:
            by[g] = by.get(g, 0) + int(r["n"])
    return ActionStep(
        available=True,
        count=sum(by.values()),
        by_outcome=by,
        examples=[_reading_example(e, ACTION.get(e["label"] or "")) for e in examples or []],
    )


def _reading_example(e: Any, label: str | None = None) -> Example:
    return Example(
        id=e["video_id"],
        title=e["event_title"],
        date=_iso(e["meeting_date"]),
        state_code=e["state_code"],
        jurisdiction_name=e["jurisdiction_name"],
        url=e["video_url"] or (f"https://www.youtube.com/watch?v={e['video_id']}" if e["video_id"] else None),
        detail=label or LEAN.get(e["label"] or "", e["label"]),
    )


@router.get("/{topic}/outcomes", response_model=TopicOutcomes)
async def topic_outcomes(
    topic: str = Path(..., description="Topic slug (e.g. water-fluoridation) or numeric topic id."),
    state: str | None = Query(None, description="Optional 2-letter state code."),
    city: str | None = Query(None, max_length=80, description="Optional city or government name (needs state)."),
) -> TopicOutcomes:
    """The chain from the meetings where a topic came up to what followed, with linked examples (#1314)."""
    key = _topic_key(topic)
    state_code = _state_code(state)
    city_name = city.strip() if city and city.strip() and state_code else None
    dc = key == DATA_CENTERS
    args = (key, state_code, city_name)
    with tracer.start_as_current_span("topics.outcomes") as span:
        span.set_attribute("topics.topic", key)
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.city", city_name or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                m_rows = await _try(conn, _MEETINGS_SQL, *args)
                m_ex = await _try(conn, _MEETINGS_EX_SQL, *args) or []
                lean_rows = await _try(conn, _lean_counts_sql(dc), *args)
                lean_ex = await _try(conn, _examples_sql(dc, "lean", tuple(LEAN)), *args)
                act_rows = await _try(conn, _action_counts_sql(dc), *args)
                act_ex = await _try(conn, _examples_sql(dc, "outcome", tuple(ACTION)), *args)
                bill_rows = await _try(conn, _BILLS_SQL, key, state_code)
                bill_ex = await _try(conn, _BILLS_EX_SQL, key, state_code) or []
                link_rows = await _try(conn, _LINKS_SQL, *args)
                link_methods = await _try(conn, _LINKS_METHOD_SQL, *args) or []
                link_ex = await _try(conn, _LINKS_EX_SQL, *args) or []
                up_rows = await _try(conn, _UPCOMING_SQL, *args)
                up_ex = await _try(conn, _UPCOMING_EX_SQL, *args) or []
                pend_rows = await _try(conn, _PENDING_SQL, key, state_code, 1)
        except Exception as exc:
            logger.exception("topic outcomes failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's outcomes are unavailable right now.") from exc

    steps = Steps(
        meetings=Step(
            available=m_rows is not None,
            count=int(m_rows[0]["n"]) if m_rows else 0,
            examples=[
                Example(
                    id=e["video_id"], title=e["event_title"], date=_iso(e["event_date"]), state_code=e["state_code"],
                    jurisdiction_name=e["jurisdiction_name"], url=e["video_url"], detail=e["evidence_passage"],
                )
                for e in m_ex
            ],
        ),
        public=shape_public(lean_rows, lean_ex),
        actions=shape_actions(act_rows, act_ex),
        bills=BillStep(
            available=bill_rows is not None,
            count=sum(int(r["n"]) for r in bill_rows or []),
            by_status={r["status"]: int(r["n"]) for r in bill_rows or []},
            examples=[
                Example(
                    id=e["bill_id"], title=f"{e['identifier']}: {e['title']}" if e["identifier"] else e["title"],
                    date=_iso(e["last_action_date"]), state_code=e["state_code"], url=e["url"],
                    detail=e["status"],
                )
                for e in bill_ex
            ],
        ),
        linked_bills=LinkStep(
            available=link_rows is not None,
            count=int(link_rows[0]["meetings"]) if link_rows else 0,
            bills=int(link_rows[0]["bills"]) if link_rows else 0,
            by_method={r["match_method"]: int(r["n"]) for r in link_methods},
            examples=[
                Example(
                    id=e["meeting_bill_link_id"],
                    title=f"{e['state_code']} {e['identifier']}" + (f": {e['bill_title']}" if e["bill_title"] else ""),
                    date=_iso(e["meeting_date"]), state_code=e["state_code"], jurisdiction_name=e["jurisdiction_name"],
                    url=e["url"], detail=e["match_text"],
                )
                for e in link_ex
            ],
        ),
        next=NextStep(
            available=up_rows is not None,
            upcoming=int(up_rows[0]["n"]) if up_rows else 0,
            pending_bills=int(pend_rows[0]["total"]) if pend_rows else 0,
            examples=[
                Example(
                    id=e["topic_upcoming_id"], title=e["title"], date=_iso(e["item_date"]), state_code=e["state_code"],
                    jurisdiction_name=e["jurisdiction_name"], url=e["source_url"], detail=e["kind"],
                )
                for e in up_ex
            ],
        ),
    )
    steps.next.count = steps.next.upcoming + steps.next.pending_bills
    return TopicOutcomes(
        topic=key, state_code=state_code, state=_state_name(None, state_code), city=city_name, steps=steps
    )
