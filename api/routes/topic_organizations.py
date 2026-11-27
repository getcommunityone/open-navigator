"""
Who's working on a curated topic (#1345): the nonprofits tied to it, for a place, ranked by evidence.

``GET /api/topics/{topic}/organizations?state=&city=&limit=``
    Rows from ``public.topic_organization_serving`` (#1382: the 20 strongest per topic and state plus every one named
    in a meeting; the full mart stays in gold), counted from ``public.topic_organization_count`` (per topic, state and
    method). A city scope is counted from its served rows; ``partial`` says when its state has more than are served. Ranked by how strong the tie is
    (``evidence_rank``: 1 named in one of the topic's meetings in the same state, 2 its 990 mission names the topic,
    3 its name does, 4 its IRS (NTEE) category is the topic's field), then by latest revenue. Each item carries the
    evidence (``match_text``: the meeting passage or mission with the topic's words in ``<mark>``, or the IRS
    category) so the page can say why it is listed. ``counts`` are per method over the whole scope.

    ``side`` is set only when a curated rule says it outright (a name or mission that states the position, e.g. "Second
    Amendment rights" or "gun violence prevention"); otherwise it is null and the page shows none.

    When the scope has none, ``broader`` gives the count one level up (city -> state -> national).

Organizations are public; no officer or person data is read or returned. Revenue is the IRS/990 figure with its tax
year; years go on the wire as strings. A relation that is not published yet answers 200 with ``available: false``.
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

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)

METHODS = ("named_in_meeting", "keyword_in_mission", "keyword_in_name", "ntee_code", "cause_tag")
MAX_ITEMS = 50


class OrganizationCounts(BaseModel):
    named_in_meeting: int = 0
    keyword_in_mission: int = 0
    keyword_in_name: int = 0
    ntee_code: int = 0
    cause_tag: int = 0


class TopicOrganizationItem(BaseModel):
    master_org_id: str
    org_name: str
    city: str | None = None
    state_code: str | None = None
    state: str | None = None
    match_method: str
    match_methods: list[str] = []
    match_text: str | None = None
    match_source_url: str | None = None
    match_date: str | None = None
    match_place: str | None = None
    mission: str | None = None
    side: str | None = None
    ntee_code: str | None = None
    revenue: int | None = None
    revenue_tax_year: str | None = None
    website_url: str | None = None


class BroaderOrgScope(BaseModel):
    state_code: str | None = None
    label: str
    total: int


class TopicOrganizations(BaseModel):
    topic: str
    topic_id: int | None = None
    state_code: str | None = None
    state: str | None = None
    city: str | None = None
    available: bool = False
    total: int = 0
    counts: OrganizationCounts = OrganizationCounts()
    items: list[TopicOrganizationItem] = []
    broader: BroaderOrgScope | None = None
    built_at: str | None = None
    #: True when the counts may be short: a city scope counted from the served rows of a state that has more.
    partial: bool = False


_SCOPE = """
    (o.topic_slug = $1::text OR o.topic_id::text = $1::text)
    AND ($2::text IS NULL OR o.state_code = $2::text)
    AND ($3::text IS NULL OR lower(o.city) = lower($3::text))
"""

# $1 topic, $2 state, $3 city, $4 limit.
_ITEMS_SQL = f"""
    SELECT o.master_org_id, o.org_name, o.city, o.state_code, o.match_method,
           o.match_text, o.match_source_url, o.match_date, o.match_place, o.mission, o.side,
           o.revenue, o.revenue_tax_year, o.website_url
    FROM topic_organization_serving o
    WHERE {_SCOPE}
    ORDER BY o.evidence_rank, o.revenue DESC NULLS LAST, o.org_name, o.master_org_id
    LIMIT $4
"""

# $1 topic, $2 state (or null). The true totals per method.
_COUNTS_SQL = """
    SELECT c.match_method, sum(c.n)::int AS n, max(c.topic_id) AS topic_id, max(c.built_at) AS built_at
    FROM topic_organization_count c
    WHERE (c.topic_slug = $1::text OR c.topic_id::text = $1::text)
      AND ($2::text IS NULL OR c.state_code = $2::text)
    GROUP BY c.match_method
"""

# $1 topic, $2 state, $3 city: a city's counts from its served rows.
_CITY_COUNTS_SQL = f"""
    SELECT o.match_method, count(*)::int AS n, max(o.topic_id) AS topic_id, max(o.built_at) AS built_at
    FROM topic_organization_serving o
    WHERE {_SCOPE}
    GROUP BY o.match_method
"""

#: Rows served per topic and state (topic_organization_serving); a state with more is cut to its strongest.
SERVED_PER_STATE = 20


def _counts(rows: list[Any]) -> OrganizationCounts:
    c = OrganizationCounts()
    for r in rows:
        if r["match_method"] in METHODS:
            setattr(c, r["match_method"], getattr(c, r["match_method"]) + int(r["n"]))
    return c


def _total(c: OrganizationCounts) -> int:
    return c.named_in_meeting + c.keyword_in_mission + c.keyword_in_name + c.ntee_code + c.cause_tag


def _city_title(city: str | None) -> str | None:
    """``city_norm`` is lower case ("tuscaloosa"); show it as a name."""
    if not city:
        return None
    return " ".join(w.capitalize() for w in city.split())


def shape_items(rows: list[Any]) -> list[TopicOrganizationItem]:
    out: list[TopicOrganizationItem] = []
    for r in rows:
        if not r["master_org_id"] or not r["org_name"]:
            continue
        out.append(
            TopicOrganizationItem(
                master_org_id=r["master_org_id"],
                org_name=r["org_name"],
                city=_city_title(r["city"]),
                state_code=r["state_code"],
                state=_state_name(None, r["state_code"]),
                match_method=r["match_method"],
                match_methods=[r["match_method"]],
                match_text=r["match_text"],
                match_source_url=r["match_source_url"],
                match_date=_iso(r["match_date"]),
                match_place=r["match_place"],
                mission=r["mission"],
                side=r["side"],
                revenue=int(r["revenue"]) if r["revenue"] is not None else None,
                revenue_tax_year=str(r["revenue_tax_year"]) if r["revenue_tax_year"] is not None else None,
                website_url=r["website_url"],
            )
        )
    return out


@router.get("/{topic}/organizations", response_model=TopicOrganizations)
async def topic_organizations(
    topic: str = Path(..., description="Topic slug (e.g. water-fluoridation) or numeric topic id."),
    state: str | None = Query(None, description="Optional 2-letter state code."),
    city: str | None = Query(None, max_length=80, description="Optional city (needs state)."),
    limit: int = Query(12, ge=1, le=MAX_ITEMS),
) -> TopicOrganizations:
    """The nonprofits tied to a topic in a place, strongest evidence first (#1345)."""
    key = _topic_key(topic)
    state_code = _state_code(state)
    city_name = city.strip() if city and city.strip() and state_code else None
    base = dict(topic=key, state_code=state_code, state=_state_name(None, state_code), city=city_name)
    with tracer.start_as_current_span("topics.organizations") as span:
        span.set_attribute("topics.topic", key)
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.city", city_name or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                partial = False
                if city_name:
                    count_rows = list(await conn.fetch(_CITY_COUNTS_SQL, key, state_code, city_name))
                    state_total = _total(_counts(list(await conn.fetch(_COUNTS_SQL, key, state_code))))
                    partial = state_total > SERVED_PER_STATE
                else:
                    count_rows = list(await conn.fetch(_COUNTS_SQL, key, state_code))
                item_rows = list(await conn.fetch(_ITEMS_SQL, key, state_code, city_name, limit))
                counts = _counts(count_rows)
                broader: BroaderOrgScope | None = None
                if _total(counts) == 0 and state_code:
                    up_state = state_code if city_name else None
                    up_rows = list(await conn.fetch(_COUNTS_SQL, key, up_state))
                    broader = BroaderOrgScope(
                        state_code=up_state,
                        label=(_state_name(None, up_state) or up_state) if up_state else "National",
                        total=_total(_counts(up_rows)),
                    )
                    count_rows = count_rows or up_rows  # still says the mart covers the topic
                    partial = False
        except asyncpg.exceptions.UndefinedTableError:
            span.set_attribute("topics.relation_missing", True)
            return TopicOrganizations(**base)
        except Exception as exc:
            logger.exception("topic organizations failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="Nonprofits on this topic are unavailable right now.") from exc

        topic_id = next((r["topic_id"] for r in count_rows if r["topic_id"] is not None), None)
        built_at = max((r["built_at"] for r in count_rows if r["built_at"] is not None), default=None)
        span.set_attribute("topics.organizations_total", _total(counts))
        return TopicOrganizations(
            **base,
            topic_id=topic_id,
            available=built_at is not None,
            total=_total(counts),
            counts=counts,
            items=shape_items(item_rows),
            broader=broader,
            built_at=_iso(built_at),
            partial=partial and _total(counts) > 0,
        )
