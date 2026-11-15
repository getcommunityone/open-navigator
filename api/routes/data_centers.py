"""
Data-center job claims, split by phase (issue #246, DC-1.1), each attributed to its
speaker and meeting (issue #247, DC-1.2: ``speaker_role``, ``body_name``).

Backed by the dbt mart ``job_claim`` (published to ``public``): one row per
jobs claim a speaker made in a meeting, tagged ``construction`` or
``operations``. This route only reads the modeled relation; all extraction and
shaping lives in dbt.

``GET /api/data-centers/job-claims`` filters to ``project_type = 'data_center'``
and narrows by ``state`` (2-letter code, or a full name normalized to one),
``city`` (case-insensitive match on ``jurisdiction_name``) and/or
``jurisdiction_id`` (exact). The response echoes the applied filters as
``scope`` so the UI label always matches the data (CLAUDE.md, scope label rule).

Unknown values stay ``null``; nothing is defaulted to 0 (CLAUDE.md, No
Fabricated Data). When ``job_claim`` isn't in the database yet (the mart is
new), the route returns the scope with an empty ``items`` list instead of a 500.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.search_postgres import (
    STATE_NAME_TO_CODE,
    get_db_pool,
    normalize_state_input,
)

router = APIRouter(prefix="/data-centers", tags=["data-centers"])

tracer = trace.get_tracer(__name__)

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

_STATE_CODE_TO_NAME: dict[str, str] = {
    code: name for name, code in STATE_NAME_TO_CODE.items()
}

ScopeLevel = Literal["national", "state", "city", "jurisdiction"]


class JobClaimScope(BaseModel):
    """The filters actually applied to ``items``; ``level='national'`` when none."""

    level: ScopeLevel
    state_code: str | None = Field(
        None, description="2-letter state code filter, if any."
    )
    state: str | None = Field(
        None, description="Full state name for state_code, if known."
    )
    city: str | None = Field(
        None, description="City filter (matched on jurisdiction_name)."
    )
    jurisdiction_id: str | None = Field(
        None, description="Exact jurisdiction_id filter."
    )


class JobClaim(BaseModel):
    """One jobs claim from a meeting; unknown values are null, never 0."""

    job_claim_id: str
    phase: Literal["construction", "operations"] = Field(
        ..., description="Never combined: one row per phase (the mart's CHECK)."
    )
    headcount_low: int | None = None
    headcount_high: int | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    project_name: str | None = None
    quote: str = Field(
        ..., description="Verbatim words of the claim; the mart drops rows without one."
    )
    speaker_name: str | None = None
    speaker_role: str | None = Field(
        None, description="The speaker's role as said in the meeting (DC-1.2); null when not said."
    )
    person_id: str | None = None
    event_meeting_id: int = Field(
        ..., description="FK to event_meeting (the mart's NOT NULL integer key)."
    )
    meeting_date: date | None = None
    body_name: str | None = Field(
        None, description="The governing body that met (e.g. city council), from event_meeting."
    )
    video_id: str | None = None
    start_seconds: float | None = None


class JobClaimTotals(BaseModel):
    """Claims per phase for the whole scope, before ``limit``: real counts, so 0 means none."""

    construction: int = 0
    operations: int = 0


class JobClaimsResponse(BaseModel):
    scope: JobClaimScope
    totals: JobClaimTotals = Field(default_factory=JobClaimTotals)
    items: list[JobClaim]


_SELECT_SQL = """
    SELECT
        job_claim_id,
        phase,
        headcount_low,
        headcount_high,
        starts_on,
        ends_on,
        project_name,
        quote,
        speaker_name,
        speaker_role,
        person_id,
        event_meeting_id,
        meeting_date,
        body_name,
        video_id,
        start_seconds
    FROM job_claim
"""


def _clean(value: str | None) -> str | None:
    """Strip a query value; blank becomes None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def build_scope(
    state: str | None, city: str | None, jurisdiction_id: str | None
) -> JobClaimScope:
    """Normalize the raw query params into the scope that the query applies."""
    state_code = normalize_state_input(_clean(state))
    city_clean = _clean(city)
    jurisdiction_clean = _clean(jurisdiction_id)

    level: ScopeLevel = "national"
    if jurisdiction_clean:
        level = "jurisdiction"
    elif city_clean:
        level = "city"
    elif state_code:
        level = "state"

    return JobClaimScope(
        level=level,
        state_code=state_code,
        state=_STATE_CODE_TO_NAME.get(state_code) if state_code else None,
        city=city_clean,
        jurisdiction_id=jurisdiction_clean,
    )


def _scope_where(scope: JobClaimScope) -> tuple[list[str], list[Any]]:
    """WHERE clauses + params for the scope. ``city`` matches like the browse routes
    (meeting_browse, decision_browse): a substring of the city or the jurisdiction name,
    so a scope carried over from another page finds the same place."""
    clauses: list[str] = ["project_type = 'data_center'"]
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        clauses.append(f"state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        clauses.append(
            f"(city ILIKE ${len(params)} OR jurisdiction_name ILIKE ${len(params)})"
        )
    if scope.jurisdiction_id:
        params.append(scope.jurisdiction_id)
        clauses.append(f"jurisdiction_id = ${len(params)}")
    return clauses, params


def build_job_claims_totals_query(scope: JobClaimScope) -> tuple[str, list[Any]]:
    """Claims per phase for the whole scope (no limit)."""
    clauses, params = _scope_where(scope)
    sql = (
        "    SELECT phase, count(*)::int AS claim_count\n"
        "    FROM job_claim\n"
        f"    WHERE {' AND '.join(clauses)}\n"
        "    GROUP BY phase\n"
    )
    return sql, params


def build_job_claims_query(scope: JobClaimScope, limit: int) -> tuple[str, list[Any]]:
    """SQL + positional params for the scope. Values are always bound, never inlined."""
    clauses, params = _scope_where(scope)
    params.append(limit)
    sql = (
        f"{_SELECT_SQL}"
        f"    WHERE {' AND '.join(clauses)}\n"
        "    ORDER BY meeting_date DESC NULLS LAST, start_seconds ASC NULLS LAST, job_claim_id\n"
        f"    LIMIT ${len(params)}\n"
    )
    return sql, params


@router.get("/job-claims", response_model=JobClaimsResponse)
async def list_job_claims(
    state: str | None = Query(
        None,
        description="2-letter state code (a full state name is normalized to one).",
    ),
    city: str | None = Query(
        None,
        description="City name; case-insensitive substring of city or jurisdiction_name.",
    ),
    jurisdiction_id: str | None = Query(None, description="Exact jurisdiction_id."),
    limit: int = Query(
        DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows (1..500)."
    ),
) -> JobClaimsResponse:
    """
    Data-center jobs claims from meetings, split by phase (construction / operations).

    Example:
        GET /api/data-centers/job-claims?state=AL&city=Tuscaloosa&limit=100
    """
    scope = build_scope(state, city, jurisdiction_id)
    sql, params = build_job_claims_query(scope, limit)
    totals_sql, totals_params = build_job_claims_totals_query(scope)

    with tracer.start_as_current_span("data-centers.job-claims") as span:
        span.set_attribute("job_claims.scope_level", scope.level)
        span.set_attribute("job_claims.state_code", scope.state_code or "")
        span.set_attribute("job_claims.city", scope.city or "")
        span.set_attribute("job_claims.jurisdiction_id", scope.jurisdiction_id or "")
        span.set_attribute("job_claims.limit", limit)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("data-centers.job-claims.query"):
                    rows = await conn.fetch(sql, *params)
                    total_rows = await conn.fetch(totals_sql, *totals_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("job_claims.relation_missing", True)
            logger.warning(
                "data-centers: relation 'job_claim' isn't in this database yet ({}); "
                "returning an empty list",
                e,
            )
            return JobClaimsResponse(scope=scope, items=[])
        except Exception as e:  # noqa: BLE001 - any other DB failure is a 500
            span.record_exception(e)
            logger.error(
                "data-centers job-claims error (scope={}): {}", scope.model_dump(), e
            )
            raise HTTPException(status_code=500, detail="Failed to load job claims")

        items = [JobClaim(**dict(row)) for row in rows]
        totals = JobClaimTotals(
            **{
                r["phase"]: r["claim_count"]
                for r in total_rows
                if r["phase"] in ("construction", "operations")
            }
        )
        span.set_attribute("job_claims.count", len(items))
        logger.info(
            "🏗️ Data-center job claims -> {} rows (scope={})", len(items), scope.level
        )
        return JobClaimsResponse(scope=scope, totals=totals, items=items)


# --- Data center sites (DC-4.1, #249) -----------------------------------------
#
# Backed by the dbt mart ``data_center_site`` (Epoch AI, CC BY 4.0): one row per site,
# with a status derived from Epoch's dated timeline rows and the credit on every row.
# A site that left Epoch's list stays, as status 'no_longer_listed'. Epoch has no city
# field, so only ``state`` narrows the list; the response says so in ``city_applied``.

SiteStatus = Literal["planned", "under_construction", "operating", "no_longer_listed"]
SITE_STATUSES: tuple[str, ...] = ("planned", "under_construction", "operating", "no_longer_listed")


class DataCenterSite(BaseModel):
    """One data center site; unknown values are null."""

    data_center_site_id: str
    site_name: str
    owner: str | None = None
    users: str | None = None
    project: str | None = None
    address: str | None = None
    country: str | None = None
    state_code: str | None = None
    state: str | None = None
    status: SiteStatus | None = Field(
        None, description="Derived from Epoch's dated rows; null when Epoch has none for the site."
    )
    last_known_status: SiteStatus | None = None
    status_as_of: date | None = None
    construction_note: str | None = None
    it_power_mw: float | None = None
    first_seen_on: date | None = None
    last_seen_on: date | None = None
    is_listed: bool
    source_name: str
    source_url: str
    license: str
    attribution: str


class DataCenterSiteCounts(BaseModel):
    """Sites per status for the whole scope (before ``status`` and ``limit``): 0 means none."""

    planned: int = 0
    under_construction: int = 0
    operating: int = 0
    no_longer_listed: int = 0
    status_not_published: int = 0


class DataCenterSitesResponse(BaseModel):
    scope: JobClaimScope
    city_applied: bool = Field(
        ..., description="Always false: the source has no city field, so a city filter can't narrow sites."
    )
    counts: DataCenterSiteCounts = Field(default_factory=DataCenterSiteCounts)
    items: list[DataCenterSite]


_SITE_COLUMNS = (
    "data_center_site_id, site_name, owner, users, project, address, country, state_code, state, "
    "status, last_known_status, status_as_of, construction_note, it_power_mw, first_seen_on, "
    "last_seen_on, is_listed, source_name, source_url, license, attribution"
)

_SITE_ORDER = (
    "CASE status WHEN 'planned' THEN 0 WHEN 'under_construction' THEN 1 "
    "WHEN 'operating' THEN 2 WHEN 'no_longer_listed' THEN 3 ELSE 4 END, site_name"
)


def build_sites_queries(
    scope: JobClaimScope, status: str | None, limit: int
) -> tuple[str, list[Any], str, list[Any]]:
    """(items SQL, params, counts SQL, params). Values are bound, never inlined."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"state_code = ${len(params)}")
    counts_where = " AND ".join(where) or "TRUE"
    counts_params = list(params)
    if status:
        params.append(status)
        where.append(f"status = ${len(params)}")
    params.append(limit)
    items_sql = (
        f"SELECT {_SITE_COLUMNS} FROM data_center_site "
        f"WHERE {' AND '.join(where) or 'TRUE'} ORDER BY {_SITE_ORDER} LIMIT ${len(params)}"
    )
    counts_sql = (
        "SELECT coalesce(status, 'status_not_published') AS status, count(*)::int AS n "
        f"FROM data_center_site WHERE {counts_where} GROUP BY 1"
    )
    return items_sql, params, counts_sql, counts_params


@router.get("/sites", response_model=DataCenterSitesResponse)
async def list_data_center_sites(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(
        None, description="Accepted so a page's scope can be passed through; it can't narrow sites."
    ),
    status: SiteStatus | None = Query(None, description="Only sites with this status."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> DataCenterSitesResponse:
    """
    Data center sites (Epoch AI, CC BY 4.0) with status and source; sites no longer
    listed by the source stay in the list.

    Example:
        GET /api/data-centers/sites?state=TX
    """
    scope = build_scope(state, city, None)
    # Sites narrow by state only; echo the scope that was actually applied.
    applied = JobClaimScope(
        level="state" if scope.state_code else "national",
        state_code=scope.state_code,
        state=scope.state,
    )
    items_sql, params, counts_sql, counts_params = build_sites_queries(applied, status, limit)
    with tracer.start_as_current_span("data-centers.sites") as span:
        span.set_attribute("sites.scope_level", applied.level)
        span.set_attribute("sites.status", status or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(items_sql, *params)
                count_rows = await conn.fetch(counts_sql, *counts_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("sites.relation_missing", True)
            logger.warning("data-centers: relation 'data_center_site' isn't here yet ({}); empty list", e)
            return DataCenterSitesResponse(scope=applied, city_applied=False, items=[])
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers sites error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load data center sites")
        counts = DataCenterSiteCounts(
            **{r["status"]: r["n"] for r in count_rows if r["status"] in DataCenterSiteCounts.model_fields}
        )
        span.set_attribute("sites.count", len(rows))
        return DataCenterSitesResponse(
            scope=applied,
            city_applied=False,
            counts=counts,
            items=[DataCenterSite(**dict(r)) for r in rows],
        )


# --- Data center items on agendas (DC-4.2, #250) --------------------------------
#
# Backed by the dbt mart ``data_center_agenda_item``: one row per agenda that mentions a
# data center, with a verbatim highlighted excerpt (``evidence``) and whether a zoning,
# land-use, tax-incentive or utility word sits near the mention. Upcoming vs past is
# worked out here from today, so a stale table can't call a past meeting upcoming.

AgendaWhen = Literal["upcoming", "past", "all"]


class DataCenterAgendaItem(BaseModel):
    data_center_agenda_item_id: str
    event_meeting_document_id: str
    jurisdiction_id: str | None = None
    jurisdiction_name: str | None = None
    state_code: str | None = None
    state: str | None = None
    body_name: str | None = None
    meeting_title: str | None = None
    doc_date: date | None = None
    document_url: str | None = None
    mentions_zoning_or_utility: bool
    evidence: str = Field(..., description="Verbatim agenda excerpt; matched words wrapped in <mark>.")
    data_center_site_id: str | None = None
    site_name: str | None = Field(None, description="The tracked site the agenda names, if any.")
    is_upcoming: bool = Field(..., description="The meeting is today or later.")
    concerns: list[str] = Field(
        default_factory=list, description="Local concerns named near the data center mention (DC-4.3)."
    )
    local_concern: str | None = Field(
        None, description="What residents of this jurisdiction object to most (area_concern), if known."
    )
    matches_local_concern: bool = Field(
        False, description="The item names the jurisdiction's dominant concern; ranked first."
    )


class DataCenterAgendaCounts(BaseModel):
    upcoming: int = 0
    past: int = 0


class DataCenterAgendaItemsResponse(BaseModel):
    scope: JobClaimScope
    counts: DataCenterAgendaCounts = Field(default_factory=DataCenterAgendaCounts)
    items: list[DataCenterAgendaItem]


def build_agenda_queries(
    scope: JobClaimScope, when: str, limit: int
) -> tuple[str, list[Any], str, list[Any]]:
    """(items SQL, params, counts SQL, params). Upcoming first (soonest), then past (newest)."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"a.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"a.jurisdiction_name ILIKE ${len(params)}")
    counts_where = " AND ".join(where) or "TRUE"
    counts_params = list(params)
    if when == "upcoming":
        where.append("a.doc_date >= current_date")
    elif when == "past":
        where.append("a.doc_date < current_date")
    params.append(limit)
    # DC-4.3 (#251): each item's jurisdiction's dominant concern (area_concern); items
    # naming it rank first within upcoming and within past.
    items_sql = (
        "SELECT a.data_center_agenda_item_id, a.event_meeting_document_id, a.jurisdiction_id, "
        "a.jurisdiction_name, a.state_code, a.state, a.body_name, a.meeting_title, a.doc_date, "
        "a.document_url, a.mentions_zoning_or_utility, a.evidence, a.data_center_site_id, "
        "s.site_name, coalesce(a.doc_date >= current_date, false) AS is_upcoming, "
        "coalesce(a.concerns, ARRAY[]::text[]) AS concerns, "
        "c.concern AS local_concern, "
        "coalesce(c.concern = ANY(a.concerns), false) AS matches_local_concern "
        "FROM data_center_agenda_item a "
        "LEFT JOIN data_center_site s ON s.data_center_site_id = a.data_center_site_id "
        "LEFT JOIN LATERAL ("
        "  SELECT ac.concern FROM area_concern ac "
        "  WHERE ac.area_level = 'jurisdiction' AND ac.is_dominant "
        "    AND ac.state_code = a.state_code AND ac.jurisdiction_name = a.jurisdiction_name "
        "  ORDER BY ac.mention_count DESC, ac.concern LIMIT 1"
        ") c ON TRUE "
        f"WHERE {' AND '.join(where) or 'TRUE'} "
        "ORDER BY (a.doc_date >= current_date) DESC NULLS LAST, "
        "coalesce(c.concern = ANY(a.concerns), false) DESC, "
        "CASE WHEN a.doc_date >= current_date THEN a.doc_date END ASC, "
        "a.doc_date DESC NULLS LAST, a.data_center_agenda_item_id "
        f"LIMIT ${len(params)}"
    )
    counts_sql = (
        "SELECT count(*) FILTER (WHERE a.doc_date >= current_date)::int AS upcoming, "
        "count(*) FILTER (WHERE a.doc_date < current_date)::int AS past "
        f"FROM data_center_agenda_item a WHERE {counts_where}"
    )
    return items_sql, params, counts_sql, counts_params


@router.get("/agenda-items", response_model=DataCenterAgendaItemsResponse)
async def list_data_center_agenda_items(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    when: AgendaWhen = Query("all", description="upcoming (today or later), past, or all."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> DataCenterAgendaItemsResponse:
    """
    Agendas that mention a data center, upcoming meetings first, each with a quoted,
    highlighted excerpt.

    Example:
        GET /api/data-centers/agenda-items?state=AL&city=Tuscaloosa&when=upcoming
    """
    scope = build_scope(state, city, None)
    applied = JobClaimScope(
        level="city" if scope.city else ("state" if scope.state_code else "national"),
        state_code=scope.state_code,
        state=scope.state,
        city=scope.city,
    )
    items_sql, params, counts_sql, counts_params = build_agenda_queries(applied, when, limit)
    with tracer.start_as_current_span("data-centers.agenda-items") as span:
        span.set_attribute("agenda_items.scope_level", applied.level)
        span.set_attribute("agenda_items.when", when)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(items_sql, *params)
                count_rows = await conn.fetch(counts_sql, *counts_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("agenda_items.relation_missing", True)
            logger.warning("data-centers: agenda-item relations aren't here yet ({}); empty list", e)
            return DataCenterAgendaItemsResponse(scope=applied, items=[])
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers agenda-items error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load agenda items")
        counts = DataCenterAgendaCounts(**dict(count_rows[0])) if count_rows else DataCenterAgendaCounts()
        span.set_attribute("agenda_items.count", len(rows))
        return DataCenterAgendaItemsResponse(
            scope=applied, counts=counts, items=[DataCenterAgendaItem(**dict(r)) for r in rows]
        )



# --- What residents object to (DC-4.3, #251) -----------------------------------
#
# Backed by the dbt mart ``area_concern``: objections recorded in an area's meetings,
# sorted into concerns. Real counts only; an area with no recorded objections returns
# no items, and the page says so instead of falling back to a national figure.

class AreaConcern(BaseModel):
    concern: str
    mention_count: int
    objection_count: int
    share: float | None = None
    concern_rank: int
    is_dominant: bool
    jurisdiction_name: str | None = None
    last_meeting_on: date | None = None


class AreaConcernsResponse(BaseModel):
    scope: JobClaimScope
    items: list[AreaConcern] = Field(..., description="The area's concerns, most mentioned first.")
    national: list[AreaConcern] = Field(..., description="The same, across all recorded objections.")


def build_concerns_queries(scope: JobClaimScope) -> tuple[str | None, list[Any], str]:
    """(area SQL or None when national, params, national SQL)."""
    columns = (
        "concern, mention_count, objection_count, share, concern_rank, is_dominant, "
        "jurisdiction_name, last_meeting_on"
    )
    national_sql = (
        f"SELECT {columns} FROM area_concern WHERE area_level = 'national' "
        "ORDER BY concern_rank, concern"
    )
    if not scope.state_code and not scope.city:
        return None, [], national_sql
    where = ["area_level = 'jurisdiction'"]
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"jurisdiction_name ILIKE ${len(params)}")
    area_sql = (
        f"SELECT {columns} FROM area_concern WHERE {' AND '.join(where)} "
        "ORDER BY jurisdiction_name, concern_rank, concern"
    )
    return area_sql, params, national_sql


@router.get("/concerns", response_model=AreaConcernsResponse)
async def list_area_concerns(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
) -> AreaConcernsResponse:
    """
    What residents object to in their own meetings, by concern, for the area and nationally.

    Example:
        GET /api/data-centers/concerns?state=AL&city=Tuscaloosa
    """
    scope = build_scope(state, city, None)
    applied = JobClaimScope(
        level="city" if scope.city else ("state" if scope.state_code else "national"),
        state_code=scope.state_code,
        state=scope.state,
        city=scope.city,
    )
    area_sql, params, national_sql = build_concerns_queries(applied)
    with tracer.start_as_current_span("data-centers.concerns") as span:
        span.set_attribute("concerns.scope_level", applied.level)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                national_rows = await conn.fetch(national_sql)
                area_rows = await conn.fetch(area_sql, *params) if area_sql else national_rows
        except asyncpg.exceptions.UndefinedTableError as e:
            logger.warning("data-centers: relation 'area_concern' isn't here yet ({}); empty", e)
            return AreaConcernsResponse(scope=applied, items=[], national=[])
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers concerns error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load concerns")
        return AreaConcernsResponse(
            scope=applied,
            items=[AreaConcern(**dict(r)) for r in area_rows],
            national=[AreaConcern(**dict(r)) for r in national_rows],
        )
