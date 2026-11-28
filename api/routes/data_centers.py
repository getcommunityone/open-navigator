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

import re
from datetime import date, datetime
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.attribution_tier import TIER_FILTER, fetch_tier_aware
from api.routes.decision_people import DecisionPeople, DecisionPerson
from api.routes.search_postgres import (
    STATE_NAME_TO_CODE,
    get_db_pool,
    normalize_state_input,
)
from api.privacy_redaction import SNIPPET_FIELDS, TEXT_FIELDS, redact_response

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
    speaker_name: str | None = Field(
        None, description='"First L." unless an official of that government (#1468).'
    )
    speaker_role: str | None = Field(
        None, description="The speaker's role as said in the meeting (DC-1.2); null when not said."
    )
    # The place, used only to keep that government's officials' names during redaction (#1468); not served.
    state_code: str | None = Field(None, exclude=True)
    jurisdiction_name: str | None = Field(None, exclude=True)
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


class PayrollJobs(BaseModel):
    """BLS QCEW payroll employment for one area and year (#1019): NAICS 518210, private ownership. Counts are
    employers' payroll filings (annual average). When BLS withheld a figure, ``disclosed`` is false and the figures
    are null, never 0."""

    area_level: str
    area_name: str
    # Bare year as a string on the wire (CLAUDE.md, calendar years).
    year: str
    employment: int | None = None
    establishments: int | None = None
    avg_annual_pay: int | None = None
    employment_change_pct: float | None = None
    disclosed: bool
    source_url: str


class JobSource(BaseModel):
    """A place data center jobs are tracked (#1019); job boards are cited, not scraped."""

    name: str
    url: str
    kind: str
    description: str | None = None
    description_source_url: str | None = None
    automated_access: str


class JobClaimsResponse(BaseModel):
    scope: JobClaimScope
    totals: JobClaimTotals = Field(default_factory=JobClaimTotals)
    items: list[JobClaim]
    # Actual payroll jobs for the scope's state (when scoped) and the nation, newest year (#1019).
    employment: list[PayrollJobs] = Field(default_factory=list)
    # Where data center jobs are tracked, for the screen's citations (#1019).
    sources: list[JobSource] = Field(default_factory=list)


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
        start_seconds,
        state_code,
        jurisdiction_name
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


_PAYROLL_SQL = """
    SELECT area_level, coalesce(state, 'United States') AS area_name, year, employment, establishments,
           avg_annual_pay, employment_change_pct, disclosed, source_url
    FROM data_center_employment
    WHERE year = (SELECT max(year) FROM data_center_employment)
      AND (area_level = 'national' OR (area_level = 'state' AND state_code = $1::text))
    ORDER BY CASE area_level WHEN 'state' THEN 0 ELSE 1 END
"""

_JOB_SOURCES_SQL = """
    SELECT name, url, kind, description, description_source_url, automated_access
    FROM data_center_job_source
    ORDER BY CASE kind WHEN 'official_statistics' THEN 0 WHEN 'job_board' THEN 1 ELSE 2 END, name
"""


async def _payroll_and_sources(scope: JobClaimScope) -> tuple[list[PayrollJobs], list[JobSource]]:
    """The BLS payroll figures for the scope's state and the nation, and the cited job sites (#1019). A city scope
    shows its state: QCEW has counties, but cities are not linked to their county here. Missing tables (a database
    without the load) give empty lists, not an error."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            pay = await conn.fetch(_PAYROLL_SQL, scope.state_code)
            src = await conn.fetch(_JOB_SOURCES_SQL)
    except asyncpg.exceptions.UndefinedTableError:
        return [], []
    except Exception as e:  # noqa: BLE001 - the claims still answer without these
        logger.warning("data-centers payroll/sources unavailable: {}", e)
        return [], []
    employment = [
        PayrollJobs(
            area_level=r["area_level"],
            area_name=r["area_name"],
            year=str(r["year"]),
            employment=r["employment"],
            establishments=r["establishments"],
            avg_annual_pay=r["avg_annual_pay"],
            employment_change_pct=float(r["employment_change_pct"]) if r["employment_change_pct"] is not None else None,
            disclosed=bool(r["disclosed"]),
            source_url=r["source_url"],
        )
        for r in pay
    ]
    sources = [JobSource(**dict(r)) for r in src]
    return employment, sources


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
            employment, sources = await _payroll_and_sources(scope)
            return await redact_response(JobClaimsResponse(scope=scope, items=[], employment=employment, sources=sources), TEXT_FIELDS)
        except Exception as e:  # noqa: BLE001 - any other DB failure is a 500
            span.record_exception(e)
            logger.error(
                "data-centers job-claims error (scope={}): {}", scope.model_dump(), e
            )
            raise HTTPException(status_code=500, detail="Failed to load job claims")

        employment, sources = await _payroll_and_sources(scope)
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
        return await redact_response(JobClaimsResponse(scope=scope, totals=totals, items=items, employment=employment, sources=sources), TEXT_FIELDS)


# --- Data center sites (DC-4.1, #249) -----------------------------------------
#
# Backed by the dbt mart ``data_center_site``: one row per site from Epoch AI or, for sites
# Epoch doesn't list, the US Data Center Registry (#958), both CC BY 4.0, with the credit of
# its own source on every row. A site that left its source's list stays, as status
# 'no_longer_listed'; 'cancelled' comes only from the registry, which publishes it. Only
# ``state`` narrows the list: Epoch rows have no city (registry rows do, but a city filter would
# silently drop every Epoch site), and the response says so in ``city_applied``.

SiteStatus = Literal["planned", "under_construction", "operating", "cancelled", "no_longer_listed"]
SITE_STATUSES: tuple[str, ...] = ("planned", "under_construction", "operating", "cancelled", "no_longer_listed")
SiteSource = Literal["epoch", "us_data_center_registry"]


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
        None,
        description="Epoch: derived from its dated rows. Registry: its own status, mapped. Null when the source gives none.",
    )
    last_known_status: SiteStatus | None = None
    status_as_of: date | None = None
    construction_note: str | None = None
    it_power_mw: float | None = None
    first_seen_on: date | None = None
    last_seen_on: date | None = None
    is_listed: bool
    source_name: str
    source_url: str | None = Field(None, description="The source record or dataset page; null only if the table lacks one (#983).")
    license: str
    attribution: str
    source: SiteSource = Field("epoch", description="Which inventory the row comes from (#958).")
    source_status: str | None = Field(None, description="The registry's own status word; null for Epoch.")
    operator: str | None = None
    city: str | None = None
    county: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    capacity_mw_planned: float | None = None
    capacity_mw_operational: float | None = None


class DataCenterSiteCounts(BaseModel):
    """Sites per status for the whole scope (before ``status`` and ``limit``): 0 means none."""

    planned: int = 0
    under_construction: int = 0
    operating: int = 0
    cancelled: int = 0
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
    "last_seen_on, is_listed, source_name, source_url, license, attribution, source, source_status, "
    "operator, city, county, latitude, longitude, capacity_mw_planned, capacity_mw_operational"
)

_SITE_ORDER = (
    "CASE status WHEN 'planned' THEN 0 WHEN 'under_construction' THEN 1 "
    "WHEN 'operating' THEN 2 WHEN 'cancelled' THEN 3 WHEN 'no_longer_listed' THEN 4 ELSE 5 END, "
    "CASE source WHEN 'epoch' THEN 0 ELSE 1 END, site_name"
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
    Data center sites (Epoch AI and the US Data Center Registry, CC BY 4.0) with status and
    source; sites no longer listed by their source stay in the list.

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
        except (asyncpg.exceptions.UndefinedTableError, asyncpg.exceptions.UndefinedColumnError) as e:
            # Missing, or not yet rebuilt with the #958 columns (an API deployed before the table): unavailable, not 500.
            span.set_attribute("sites.relation_missing", True)
            logger.warning("data-centers: relation 'data_center_site' isn't here yet or is out of date ({}); empty list", e)
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
            return await redact_response(DataCenterAgendaItemsResponse(scope=applied, items=[]), TEXT_FIELDS)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers agenda-items error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load agenda items")
        counts = DataCenterAgendaCounts(**dict(count_rows[0])) if count_rows else DataCenterAgendaCounts()
        span.set_attribute("agenda_items.count", len(rows))
        return await redact_response(DataCenterAgendaItemsResponse(
            scope=applied, counts=counts, items=[DataCenterAgendaItem(**dict(r)) for r in rows]
        ), TEXT_FIELDS)



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
    jurisdictions: list[str] = Field(
        ...,
        description=(
            "Towns whose meeting records raised this concern, sorted (state and city scopes). "
            "Empty for national rows."
        ),
    )


class AreaConcernsResponse(BaseModel):
    scope: JobClaimScope
    items: list[AreaConcern] = Field(..., description="The area's concerns, most mentioned first.")
    national: list[AreaConcern] = Field(..., description="The same, across all recorded objections.")


def build_concerns_queries(scope: JobClaimScope) -> tuple[str | None, list[Any], str]:
    """(area SQL or None when national, params, national SQL).

    The mart has only ``jurisdiction`` and ``national`` rows, so a state or city scope is
    rolled up here to one row per concern (#1139): mentions summed across the scope's towns,
    ``share`` recomputed over the scope's total mentions, ``concern_rank`` re-ranked,
    ``objection_count`` the scope's objections (each town's total counted once),
    ``is_dominant`` the mart's rule (rank 1 with at least 3 mentions), and the towns listed
    in ``jurisdictions``. ``jurisdiction_name`` is set only when one town raised it.
    """
    national_sql = (
        "SELECT concern, mention_count, objection_count, share, concern_rank, is_dominant, "
        "jurisdiction_name, last_meeting_on, ARRAY[]::text[] AS jurisdictions "
        "FROM area_concern WHERE area_level = 'national' "
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
        "WITH scoped AS ("
        "  SELECT state_code, jurisdiction_name, concern, mention_count, objection_count, last_meeting_on"
        f"  FROM area_concern WHERE {' AND '.join(where)}"
        "), scope_objections AS ("
        "  SELECT coalesce(sum(objection_count), 0)::int AS n"
        "  FROM (SELECT DISTINCT state_code, jurisdiction_name, objection_count FROM scoped) AS towns"
        "), by_concern AS ("
        "  SELECT concern, sum(mention_count)::int AS mention_count, max(last_meeting_on) AS last_meeting_on,"
        "    coalesce(array_agg(DISTINCT jurisdiction_name ORDER BY jurisdiction_name)"
        "      FILTER (WHERE jurisdiction_name IS NOT NULL), ARRAY[]::text[]) AS jurisdictions"
        "  FROM scoped GROUP BY concern"
        "), ranked AS ("
        "  SELECT c.*, o.n AS objection_count,"
        "    (c.mention_count::double precision / nullif(sum(c.mention_count) OVER (), 0)) AS share,"
        "    rank() OVER (ORDER BY c.mention_count DESC)::int AS concern_rank"
        "  FROM by_concern AS c CROSS JOIN scope_objections AS o"
        ") "
        "SELECT concern, mention_count, objection_count, share, concern_rank, "
        "(concern_rank = 1 AND mention_count >= 3) AS is_dominant, "
        "CASE WHEN cardinality(jurisdictions) = 1 THEN jurisdictions[1] END AS jurisdiction_name, "
        "last_meeting_on, jurisdictions "
        "FROM ranked ORDER BY concern_rank, concern"
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


# --- Data centers discussed in meeting transcripts (#445) ------------------------
#
# Backed by the dbt mart ``data_center_meeting_mention``: one row per (meeting video,
# ~3-minute passage) whose own words say "data center", with a verbatim highlighted
# excerpt (``evidence``) and, when the transcript is timed, the second to jump to.
# Sibling of the agenda items above: transcripts reach places whose agendas we don't have.

MentionStrength = Literal["site_specific", "data_center"]


class DataCenterMeetingMention(BaseModel):
    data_center_meeting_mention_id: str
    video_id: str
    video_url: str
    jump_url: str | None = Field(
        None, description="video_url at start_seconds (YouTube t=); null when the transcript has no timing."
    )
    meeting_title: str | None = None
    meeting_date: date | None = None
    jurisdiction_id: str | None = None
    jurisdiction_name: str | None = None
    state_code: str | None = None
    state: str | None = None
    passage_index: int
    start_seconds: float | None = Field(None, description="Seconds into the recording; null when untimed.")
    evidence: str = Field(..., description="Verbatim transcript excerpt; matched words wrapped in <mark>.")
    match_terms: list[str] = Field(default_factory=list)
    match_strength: MentionStrength
    data_center_site_id: str | None = None
    site_name: str | None = Field(None, description="The tracked site discussed or nearby, if any.")
    site_match_basis: Literal["named_in_passage", "nearby_site"] | None = None
    meeting_summary: str | None = Field(
        None,
        description="The meeting's AI summary from the record (event_meeting.meeting_summary, #1124); null when the "
        "meeting has none or isn't in event_meeting.",
    )
    meeting_url: str | None = Field(
        None, description="The app route of the meeting page (/meetings/<event_meeting_id>); null when not on record."
    )
    speaker_display_name: str | None = Field(
        None,
        description='"First L." of the person the record attributes the quoted words to (#1124): a counted public '
        "comment from the meeting's analysis whose verbatim quote is inside this excerpt. Null when no attribution "
        "exists (never guessed), or when two different speakers match.",
    )
    speaker_role: str | None = Field(None, description="That speaker's role as recorded; null with no speaker.")
    ai_outcome: str | None = Field(
        None,
        description="AI reading (#1140, data_center_meeting_lean.dc_outcome) of what officials did with the item: "
        "approved, denied, tabled_or_deferred, moratorium or discussed_no_action. Null when not screened or no item.",
    )
    ai_public_lean: str | None = Field(
        None,
        description="AI reading of whether the public mostly opposed, mostly supported or split at that meeting (data_center_meeting_lean.public_lean): "
        "mostly_opposed, mostly_supported, mixed or no_public_comment_on_data_center. Null when not screened.",
    )


class DataCenterMeetingMentionStateCount(BaseModel):
    """Meetings in one state where a data center came up (distinct recordings)."""

    state_code: str
    state: str | None = None
    meetings: int


class DataCenterMeetingMentionPlaceCount(BaseModel):
    """Meetings for one government in the scoped state (#1039), placed on the county map by geoid or coordinates."""

    jurisdiction_id: str
    jurisdiction_name: str | None = None
    jurisdiction_type: str | None = None
    geoid: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    meetings: int
    speakers_for: int = 0
    speakers_against: int = 0
    speakers_question: int = 0
    speakers_neutral: int = 0
    public_against_meetings: int = Field(
        0,
        description="Meetings where Jev read the public as mostly opposed to a data center (P >= 0.7) (#1117): an AI "
        "reading of the transcript, not counted speakers. 0 when none or when data_center_meeting_lean isn't loaded.",
    )
    disagreement_meetings: int = Field(
        0,
        description="Meetings where Jev read the public as mostly opposed and officials as mostly supportive, and the "
        "outcome wasn't a moratorium, a denial or an approval of rules (#1117, the #1113 refined rule). 0 when none.",
    )


class DataCenterMeetingMentionCounts(BaseModel):
    """Real counts for the whole scope (before ``limit``): 0 means none."""

    passages: int = 0
    meetings: int = 0
    site_specific: int = 0
    by_state: list[DataCenterMeetingMentionStateCount] = Field(
        default_factory=list,
        description="Meetings per state across the whole country (not narrowed by state or city), largest first (#970); states with none are left out.",
    )
    by_place: list[DataCenterMeetingMentionPlaceCount] = Field(
        default_factory=list,
        description="Only when a state is in scope (#1039): meetings per government in that state (not narrowed by city), largest first, with its geoid and coordinates for the county map, and the real speaker sums for its meetings (#1106; 0 when none). Governments with none are left out.",
    )


class DataCenterMeetingMentionsResponse(BaseModel):
    scope: JobClaimScope
    counts: DataCenterMeetingMentionCounts = Field(default_factory=DataCenterMeetingMentionCounts)
    items: list[DataCenterMeetingMention]


def _mention_where(
    state_code: str | None, city: str | None, site_id: str | None, strength: str | None
) -> tuple[str, list[Any]]:
    """The WHERE clause (and its bound params, $1…) shared by the mention queries."""
    where: list[str] = []
    params: list[Any] = []
    if state_code:
        params.append(state_code)
        where.append(f"m.state_code = ${len(params)}")
    if city:
        params.append(f"%{city}%")
        where.append(f"m.jurisdiction_name ILIKE ${len(params)}")
    if site_id:
        params.append(site_id)
        where.append(f"m.data_center_site_id = ${len(params)}")
    if strength:
        params.append(strength)
        where.append(f"m.match_strength = ${len(params)}")
    return " AND ".join(where) or "TRUE", params


def build_mention_queries(
    scope: JobClaimScope, site_id: str | None, strength: str | None, limit: int
) -> tuple[str, list[Any], str, list[Any]]:
    """(items SQL, params, counts SQL, params). Newest meeting first, then by moment in the meeting."""
    where_sql, params = _mention_where(scope.state_code, scope.city, site_id, strength)
    counts_params = list(params)
    params.append(limit)
    items_sql = (
        "SELECT m.data_center_meeting_mention_id, m.video_id, m.video_url, m.meeting_title, "
        "m.meeting_date, m.jurisdiction_id, m.jurisdiction_name, m.state_code, m.state, "
        "m.passage_index, m.start_seconds::float8 AS start_seconds, m.evidence, "
        "coalesce(m.match_terms, ARRAY[]::text[]) AS match_terms, m.match_strength, "
        "m.data_center_site_id, s.site_name, m.site_match_basis "
        "FROM data_center_meeting_mention m "
        "LEFT JOIN data_center_site s ON s.data_center_site_id = m.data_center_site_id "
        f"WHERE {where_sql} "
        "ORDER BY m.meeting_date DESC NULLS LAST, m.video_id, m.passage_index "
        f"LIMIT ${len(params)}"
    )
    counts_sql = (
        "SELECT count(*)::int AS passages, count(DISTINCT m.video_id)::int AS meetings, "
        "count(*) FILTER (WHERE m.match_strength = 'site_specific')::int AS site_specific "
        f"FROM data_center_meeting_mention m WHERE {where_sql}"
    )
    return items_sql, params, counts_sql, counts_params


def build_mention_state_quotes_query(
    scope: JobClaimScope, site_id: str | None, strength: str | None, per_state: int
) -> tuple[str, list[Any]]:
    """Up to ``per_state`` passages per state for the story map cards (#1230), one per meeting (its first passage).

    Only real public meetings: a recording Jev read as ``government_other`` (media briefing, ceremony, interview) or
    ``not_government`` (podcast, stream) is never quoted (``meeting_video_kind``); an unscreened one is kept. Then
    meetings Jev read as the public mostly opposed (``data_center_meeting_lean.public_against``, P >= 0.7, the only
    lean the maps serve), newest first; then screened meetings; then the rest, newest first.
    """
    where_sql, params = _mention_where(scope.state_code, scope.city, site_id, strength)
    params.append(per_state)
    sql = (
        "WITH first_passage AS ("
        "SELECT DISTINCT ON (m.video_id) m.* FROM data_center_meeting_mention m "
        f"WHERE ({where_sql}) AND m.state_code IS NOT NULL "
        "ORDER BY m.video_id, m.passage_index"
        "), ranked AS ("
        "SELECT f.*, row_number() OVER ("
        "PARTITION BY f.state_code ORDER BY "
        "CASE WHEN l.public_against THEN 0 WHEN k.is_public_meeting THEN 1 ELSE 2 END, "
        "f.meeting_date DESC NULLS LAST, f.video_id"
        ") AS state_rank "
        "FROM first_passage f "
        "LEFT JOIN data_center_meeting_lean l ON l.video_id = f.video_id "
        "LEFT JOIN meeting_video_kind k ON k.video_id = f.video_id "
        "WHERE k.is_public_meeting IS NOT FALSE"
        ") "
        "SELECT r.data_center_meeting_mention_id, r.video_id, r.video_url, r.meeting_title, "
        "r.meeting_date, r.jurisdiction_id, r.jurisdiction_name, r.state_code, r.state, "
        "r.passage_index, r.start_seconds::float8 AS start_seconds, r.evidence, "
        "coalesce(r.match_terms, ARRAY[]::text[]) AS match_terms, r.match_strength, "
        "r.data_center_site_id, s.site_name, r.site_match_basis "
        "FROM ranked r "
        "LEFT JOIN data_center_site s ON s.data_center_site_id = r.data_center_site_id "
        f"WHERE r.state_rank <= ${len(params)} "
        "ORDER BY r.state_code, r.state_rank"
    )
    return sql, params


def build_mention_by_state_query(site_id: str | None, strength: str | None) -> tuple[str, list[Any]]:
    """Distinct meetings per state across the whole country (#970), with the same site and strength filters.

    Never narrowed to the requested state or city: the Overview map shades every state with its own count and highlights
    the scope, so a state outside the scope is never shown as having no meetings when it simply wasn't counted.
    """
    where_sql, params = _mention_where(None, None, site_id, strength)
    sql = (
        "SELECT m.state_code, max(m.state) AS state, count(DISTINCT m.video_id)::int AS meetings "
        f"FROM data_center_meeting_mention m WHERE ({where_sql}) AND m.state_code IS NOT NULL "
        "GROUP BY m.state_code ORDER BY meetings DESC, m.state_code"
    )
    return sql, params


def build_mention_by_place_query(state_code: str, site_id: str | None, strength: str | None) -> tuple[str, list[Any]]:
    """Distinct meetings per government in one state (#1039), with the same site and strength filters.

    Never narrowed to the city: the state's county map shades every county and highlights the scope.
    Each government also carries the real speaker sums from ``data_center_meeting_position`` (#1106) for
    its distinct meetings: positions are summed per ``video_id`` first, then joined to the distinct
    (government, meeting) set, so a meeting with many passages is never counted more than once. 0 when none.
    """
    where_sql, params = _mention_where(state_code, None, site_id, strength)
    sql = (
        "WITH pos AS ("
        "SELECT p.video_id, sum(p.speakers_for)::int AS speakers_for, "
        "sum(p.speakers_against)::int AS speakers_against, "
        "sum(p.speakers_question)::int AS speakers_question, "
        "sum(p.speakers_neutral)::int AS speakers_neutral "
        "FROM data_center_meeting_position p WHERE p.video_id IS NOT NULL GROUP BY p.video_id"
        "), mv AS ("
        "SELECT DISTINCT m.jurisdiction_id, m.video_id FROM data_center_meeting_mention m "
        f"WHERE ({where_sql}) AND m.jurisdiction_id IS NOT NULL"
        "), sp AS ("
        "SELECT mv.jurisdiction_id, sum(pos.speakers_for)::int AS speakers_for, "
        "sum(pos.speakers_against)::int AS speakers_against, "
        "sum(pos.speakers_question)::int AS speakers_question, "
        "sum(pos.speakers_neutral)::int AS speakers_neutral "
        "FROM mv JOIN pos ON pos.video_id = mv.video_id GROUP BY mv.jurisdiction_id"
        ") "
        "SELECT m.jurisdiction_id, max(m.jurisdiction_name) AS jurisdiction_name, "
        "max(j.jurisdiction_type) AS jurisdiction_type, max(j.geoid) AS geoid, "
        "max(j.latitude)::float8 AS latitude, max(j.longitude)::float8 AS longitude, "
        "count(DISTINCT m.video_id)::int AS meetings, "
        "coalesce(max(sp.speakers_for), 0)::int AS speakers_for, "
        "coalesce(max(sp.speakers_against), 0)::int AS speakers_against, "
        "coalesce(max(sp.speakers_question), 0)::int AS speakers_question, "
        "coalesce(max(sp.speakers_neutral), 0)::int AS speakers_neutral "
        "FROM data_center_meeting_mention m "
        "LEFT JOIN jurisdictions j ON j.jurisdiction_id::text = m.jurisdiction_id "
        "LEFT JOIN sp ON sp.jurisdiction_id = m.jurisdiction_id "
        f"WHERE ({where_sql}) AND m.jurisdiction_id IS NOT NULL "
        "GROUP BY m.jurisdiction_id ORDER BY meetings DESC, m.jurisdiction_id"
    )
    return sql, params


def build_lean_by_place_query(state_code: str, site_id: str | None, strength: str | None) -> tuple[str, list[Any]]:
    """Jev's public-against and disagreement meeting counts per government in one state (#1117), over the same
    distinct (government, meeting) set as ``build_mention_by_place_query`` (same site and strength filters).
    Only governments with at least one such meeting are returned."""
    where_sql, params = _mention_where(state_code, None, site_id, strength)
    sql = (
        "WITH mv AS (SELECT DISTINCT m.jurisdiction_id, m.video_id FROM data_center_meeting_mention m "
        f"WHERE ({where_sql}) AND m.jurisdiction_id IS NOT NULL) "
        "SELECT mv.jurisdiction_id, "
        "count(*) FILTER (WHERE l.public_against)::int AS public_against_meetings, "
        "count(*) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_meetings "
        "FROM mv JOIN data_center_meeting_lean l ON l.video_id = mv.video_id "
        "GROUP BY mv.jurisdiction_id "
        "HAVING count(*) FILTER (WHERE l.public_against OR l.officials_sided_against_public) > 0"
    )
    return sql, params


LEAN_BY_STATE_SQL = (
    "SELECT l.state_code, "
    "count(*) FILTER (WHERE l.public_against)::int AS public_against_meetings, "
    "count(*) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_meetings "
    "FROM data_center_meeting_lean l WHERE l.state_code IS NOT NULL "
    "GROUP BY l.state_code "
    "HAVING count(*) FILTER (WHERE l.public_against OR l.officials_sided_against_public) > 0 "
    "ORDER BY l.state_code"
)
"""Jev's public-against and disagreement meetings per state for the whole country (#1117): never narrowed by the
scope, like ``POSITION_BY_STATE_SQL``. Only supported/mixed readings are never served."""


async def _fetch_lean(conn: Any, sql: str, *params: Any) -> dict[str, dict[str, int]]:
    """Lean counts keyed by the first column, or {} when data_center_meeting_lean (or a column) isn't in this
    database: the maps then show speakers and meetings only, never a failure."""
    try:
        rows = await conn.fetch(sql, *params)
    except asyncpg.exceptions.PostgresError as e:
        logger.warning("data-centers: data_center_meeting_lean unavailable ({}); lean counts 0", e)
        return {}
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        row = dict(r)
        key = row.get("state_code") or row.get("jurisdiction_id")
        if key:
            out[str(key)] = {
                "public_against_meetings": int(row.get("public_against_meetings") or 0),
                "disagreement_meetings": int(row.get("disagreement_meetings") or 0),
            }
    return out


MENTION_MEETING_SQL = (
    "SELECT DISTINCT ON (e.video_id) e.video_id, e.event_meeting_id, "
    "nullif(btrim(e.meeting_summary), '') AS meeting_summary "
    "FROM event_meeting e WHERE e.video_id = ANY($1::text[]) "
    "ORDER BY e.video_id, (nullif(btrim(e.meeting_summary), '') IS NULL), e.event_meeting_id"
)
"""The meeting page and AI summary for each passage's recording (#1124). A recording with two event_meeting rows takes
the one with a summary, then the lowest id."""

_NORM_QUOTE = "lower(regexp_replace(c.quote, '\\s+', ' ', 'g'))"
_NORM_EVIDENCE = "lower(regexp_replace(regexp_replace(m.evidence, '</?mark>', '', 'g'), '\\s+', ' ', 'g'))"
MENTION_SPEAKER_SQL = (
    "SELECT m.data_center_meeting_mention_id, "
    "min(c.speaker_display_name) AS speaker_display_name, min(c.speaker_role) AS speaker_role, "
    "count(DISTINCT c.speaker_display_name)::int AS speakers "
    "FROM data_center_meeting_mention m "
    "JOIN data_center_public_comment c ON c.video_id = m.video_id "
    "WHERE m.data_center_meeting_mention_id = ANY($1::text[]) "
    "AND c.speaker_display_name IS NOT NULL AND length(btrim(c.quote)) >= 20 "
    f"AND position({_NORM_QUOTE} IN {_NORM_EVIDENCE}) > 0 "
    "GROUP BY m.data_center_meeting_mention_id"
)
"""Who said the quoted words (#1124), only where the record says so: a public comment from the same recording, with a
name, whose whole verbatim quote (20+ characters) is inside the passage's excerpt. No timing guess, no fuzzy match."""

MENTION_INTRO_SPEAKER_SQL = (
    "SELECT s.data_center_meeting_mention_id, s.speaker_kind, s.speaker_display_name, s.speaker_role "
    "FROM meeting_passage_speaker s "
    "WHERE s.data_center_meeting_mention_id = ANY($1::text[]) AND s.speaker_display_name IS NOT NULL "
    f"{TIER_FILTER}"
)
"""Who said the passage from their self-introduction in the recording (#1231): the nearest preceding "my name is ..."
within the same meeting (meeting_passage_speaker). Used only where the hand-counted public comments name nobody."""

_FIRST_L = re.compile(r"^\S+( \S\.)?$")


def first_l(name: str | None) -> str | None:
    """A served name as "First L." at most (AGENTS.md, Privacy): "Audra T." and "Audra" pass; "Audra Thompson" → "Audra T."."""
    n = " ".join((name or "").split())
    if not n:
        return None
    if _FIRST_L.match(n):
        return n
    parts = n.split(" ")
    last = next((ch for ch in parts[-1] if ch.isalpha()), None)
    return f"{parts[0]} {last.upper()}." if last else parts[0]


async def _mention_extras(conn: Any, rows: list[dict[str, Any]]) -> None:
    """Add meeting_summary, meeting_url, speaker_display_name and speaker_role to each row in place (#1124).

    Each lookup is optional: a serving copy without event_meeting or data_center_public_comment (or a column) leaves
    the fields null, and the passages are still served."""
    video_ids = sorted({r["video_id"] for r in rows if r.get("video_id")})
    mention_ids = [r["data_center_meeting_mention_id"] for r in rows]
    meetings: dict[str, dict[str, Any]] = {}
    speakers: dict[str, dict[str, Any]] = {}
    if video_ids:
        try:
            for r in await conn.fetch(MENTION_MEETING_SQL, video_ids):
                meetings[str(r["video_id"])] = dict(r)
        except asyncpg.exceptions.PostgresError as e:
            logger.warning("data-centers: event_meeting unavailable for mention cards ({}); summaries null", e)
    if mention_ids:
        try:
            for r in await conn.fetch(MENTION_SPEAKER_SQL, mention_ids):
                row = dict(r)
                if int(row.get("speakers") or 0) == 1:
                    speakers[str(row["data_center_meeting_mention_id"])] = row
        except asyncpg.exceptions.PostgresError as e:
            logger.warning("data-centers: data_center_public_comment unavailable for mention cards ({}); speakers null", e)
    intro_speakers: dict[str, dict[str, Any]] = {}
    unnamed = [m for m in mention_ids if str(m) not in speakers]
    if unnamed:
        try:
            for r in await fetch_tier_aware(conn, MENTION_INTRO_SPEAKER_SQL, unnamed, what="data-centers mention cards"):
                intro_speakers[str(r["data_center_meeting_mention_id"])] = dict(r)
        except asyncpg.exceptions.PostgresError as e:
            logger.warning("data-centers: meeting_passage_speaker unavailable for mention cards ({}); speakers null", e)
    for r in rows:
        meeting = meetings.get(str(r.get("video_id")))
        if meeting:
            r["meeting_summary"] = meeting.get("meeting_summary") or None
            emid = meeting.get("event_meeting_id")
            r["meeting_url"] = f"/meetings/{emid}" if emid is not None else None
        sp = speakers.get(str(r["data_center_meeting_mention_id"]))
        if sp:
            r["speaker_display_name"] = first_l(sp.get("speaker_display_name"))
            r["speaker_role"] = (sp.get("speaker_role") or None) if r["speaker_display_name"] else None
            continue
        intro = intro_speakers.get(str(r["data_center_meeting_mention_id"]))
        if intro:
            raw = intro.get("speaker_display_name")
            # Officials (matched to our officials data) keep their name; everyone else is "First L." at most.
            if intro.get("speaker_kind") == "official":
                name = " ".join(str(raw or "").split()) or None
            else:
                name = first_l(raw)
            r["speaker_display_name"] = name
            r["speaker_role"] = (intro.get("speaker_role") or None) if name else None


MENTION_LEAN_SQL = (
    "SELECT video_id, nullif(dc_outcome, 'no_data_center_item') AS ai_outcome, "
    # A for/against lean under P 0.7 is split (#1200), as on the maps and in the title, so the unit matrix's "By who
    # spoke" groups never call an unsure reading "For data centers".
    "CASE WHEN public_lean IN ('mostly_opposed', 'mostly_supported') AND coalesce(public_lean_p, 0) < 0.7 "
    "THEN 'mixed' ELSE public_lean END AS ai_public_lean "
    "FROM data_center_meeting_lean WHERE video_id = ANY($1::text[])"
)


async def _mention_lean(conn: Any, rows: list[dict[str, Any]]) -> None:
    """Stamp each passage with its meeting's AI reading (#1140), for the unit matrix's outcome and public groupings.
    A serving copy without data_center_meeting_lean leaves both null."""
    ids = sorted({r["video_id"] for r in rows if r.get("video_id")})
    if not ids:
        return
    try:
        lean = {r["video_id"]: dict(r) for r in await conn.fetch(MENTION_LEAN_SQL, ids)}
    except asyncpg.exceptions.PostgresError as e:
        logger.warning("data-centers: meeting lean unavailable ({})", e)
        return
    for r in rows:
        hit = lean.get(r.get("video_id"))
        if hit:
            r["ai_outcome"] = hit["ai_outcome"]
            r["ai_public_lean"] = hit["ai_public_lean"]


def jump_url(video_url: str, start_seconds: float | None) -> str | None:
    """The recording at the passage's moment (YouTube ``t=`` in whole seconds)."""
    if start_seconds is None or "youtu" not in video_url:
        return None
    sep = "&" if "?" in video_url else "?"
    return f"{video_url}{sep}t={int(start_seconds)}s"


@router.get("/meeting-mentions", response_model=DataCenterMeetingMentionsResponse)
async def list_data_center_meeting_mentions(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    site_id: str | None = Query(None, description="Only passages linked to this data_center_site_id."),
    strength: MentionStrength | None = Query(
        None, description="site_specific (names a tracked site/owner) or data_center."
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    quotes_per_state: int | None = Query(
        None,
        ge=1,
        le=10,
        description="For the story map cards (#1230): instead of the newest `limit` passages, up to this many per state, "
        "one per meeting, real public meetings only, meetings where the public mostly opposed first, newest first. "
        "Counts are unchanged.",
    ),
) -> DataCenterMeetingMentionsResponse:
    """
    Meeting passages where a data center was discussed, newest meeting first, each with a
    quoted, highlighted excerpt of the transcript and the moment to jump to. With ``quotes_per_state``, each state's
    map quotes instead (see ``build_mention_state_quotes_query``).

    Example:
        GET /api/data-centers/meeting-mentions?state=NC&city=Charlotte
    """
    scope = build_scope(state, city, None)
    applied = JobClaimScope(
        level="city" if scope.city else ("state" if scope.state_code else "national"),
        state_code=scope.state_code,
        state=scope.state,
        city=scope.city,
    )
    site_clean = _clean(site_id)
    items_sql, params, counts_sql, counts_params = build_mention_queries(applied, site_clean, strength, limit)
    by_state_sql, by_state_params = build_mention_by_state_query(site_clean, strength)
    with tracer.start_as_current_span("data-centers.meeting-mentions") as span:
        span.set_attribute("meeting_mentions.scope_level", applied.level)
        span.set_attribute("meeting_mentions.state_code", applied.state_code or "")
        span.set_attribute("meeting_mentions.city", applied.city or "")
        span.set_attribute("meeting_mentions.site_id", site_clean or "")
        span.set_attribute("meeting_mentions.limit", limit)
        span.set_attribute("meeting_mentions.quotes_per_state", quotes_per_state or 0)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("data-centers.meeting-mentions.query"):
                    if quotes_per_state:
                        quotes_sql, quotes_params = build_mention_state_quotes_query(
                            applied, site_clean, strength, quotes_per_state
                        )
                        try:
                            rows = await conn.fetch(quotes_sql, *quotes_params)
                        except (asyncpg.exceptions.UndefinedTableError, asyncpg.exceptions.UndefinedColumnError) as e:
                            # A serving copy without meeting_video_kind / data_center_meeting_lean: the newest passages.
                            logger.warning("data-centers: map-quote tables unavailable ({}); newest passages", e)
                            rows = await conn.fetch(items_sql, *params)
                    else:
                        rows = await conn.fetch(items_sql, *params)
                    count_rows = await conn.fetch(counts_sql, *counts_params)
                    state_rows = await conn.fetch(by_state_sql, *by_state_params)
                    place_rows = []
                    place_lean: dict[str, dict[str, int]] = {}
                    if applied.state_code:
                        place_sql, place_params = build_mention_by_place_query(
                            applied.state_code, site_clean, strength
                        )
                        try:
                            place_rows = await conn.fetch(place_sql, *place_params)
                        except asyncpg.exceptions.PostgresError as e:
                            # A serving copy without jurisdictions: the map falls back to the national view.
                            logger.warning("data-centers: by_place unavailable ({})", e)
                        if place_rows:
                            lean_sql, lean_params = build_lean_by_place_query(applied.state_code, site_clean, strength)
                            place_lean = await _fetch_lean(conn, lean_sql, *lean_params)
                item_rows = [dict(r) for r in rows]
                with tracer.start_as_current_span("data-centers.meeting-mentions.card-extras"):
                    await _mention_extras(conn, item_rows)
                    await _mention_lean(conn, item_rows)
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("meeting_mentions.relation_missing", True)
            logger.warning("data-centers: relation 'data_center_meeting_mention' isn't here yet ({}); empty list", e)
            return await redact_response(DataCenterMeetingMentionsResponse(scope=applied, items=[]), TEXT_FIELDS)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers meeting-mentions error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load meeting mentions")
        counts = (
            DataCenterMeetingMentionCounts(**dict(count_rows[0])) if count_rows else DataCenterMeetingMentionCounts()
        )
        counts.by_state = [DataCenterMeetingMentionStateCount(**dict(r)) for r in state_rows]
        counts.by_place = [
            DataCenterMeetingMentionPlaceCount(**{**dict(r), **place_lean.get(str(dict(r)["jurisdiction_id"]), {})})
            for r in place_rows
        ]
        items = []
        for row in item_rows:
            row["jump_url"] = jump_url(row["video_url"], row.get("start_seconds"))
            items.append(DataCenterMeetingMention(**row))
        span.set_attribute("meeting_mentions.count", len(items))
        span.set_attribute("meeting_mentions.with_summary", sum(1 for i in items if i.meeting_summary))
        span.set_attribute("meeting_mentions.with_speaker", sum(1 for i in items if i.speaker_display_name))
        return await redact_response(DataCenterMeetingMentionsResponse(scope=applied, counts=counts, items=items), TEXT_FIELDS)


# --- company-hosted community meetings and project timelines (#532) ------------------------

CommunityEventKind = Literal[
    "town_hall", "community_meeting", "open_house", "information_session", "public_meeting"
]


class CommunityEventSource(BaseModel):
    """One article or announcement that reports the meeting (verbatim)."""

    url: str
    title: str
    publisher: str | None = None
    published_on: date | None = None
    source: str = Field(..., description="gdelt, google_news or company_feed (the company's own press release).")
    evidence: str = Field(..., description="The item's title and snippet, verbatim; the meeting word in <mark>.")


class RecordingCandidate(BaseModel):
    """A video a search found for the meeting: a candidate for review, never attached."""

    video_url: str
    title: str | None = None
    channel: str | None = None
    published_on: date | None = None
    match_reason: str


class CommunityEvent(BaseModel):
    community_event_id: str
    host_type: Literal["company"] = Field("company", description="Always a company: never a government meeting.")
    master_org_id: str | None = None
    host_name: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    jurisdiction_id: str | None = None
    city: str | None = None
    state_code: str | None = None
    state: str | None = None
    event_kind: CommunityEventKind
    event_date: date | None = Field(None, description="Only when an article states it.")
    event_date_basis: Literal["stated", "stated_month_day"] | None = None
    recording_url: str | None = Field(None, description="A video link an article itself carries.")
    title: str
    first_reported_on: date | None = None
    sources: list[CommunityEventSource] = Field(default_factory=list)
    recording_candidates: list[RecordingCandidate] = Field(default_factory=list)


class CommunityEventsResponse(BaseModel):
    scope: JobClaimScope
    project_id: str | None = None
    unconfirmed: int = Field(0, description="Items kept for review (host or project unmatched); not shown as events.")
    items: list[CommunityEvent]


def build_community_event_queries(
    scope: JobClaimScope, project_id: str | None, limit: int
) -> tuple[str, list[Any], str, list[Any]]:
    """(events SQL, params, unconfirmed-count SQL, params). Confirmed events only; newest first."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"e.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"(e.city ILIKE ${len(params)} OR j.name ILIKE ${len(params)})")
    if project_id:
        params.append(project_id)
        where.append(f"e.project_id = ${len(params)}")
    scoped = " AND ".join(where) or "TRUE"
    count_params = list(params)
    params.append(limit)
    events_sql = (
        "SELECT e.community_event_id, e.master_org_id, e.host_name, e.project_id, e.project_name, "
        "e.jurisdiction_id, e.city, e.state_code, e.state, e.event_kind, e.event_date, "
        "e.event_date_basis, e.recording_url, e.title, e.first_reported_on "
        "FROM data_center_community_event e "
        "LEFT JOIN jurisdictions j ON j.jurisdiction_id = e.jurisdiction_id "
        f"WHERE e.status = 'confirmed' AND {scoped} "
        "ORDER BY coalesce(e.event_date, e.first_reported_on) DESC NULLS LAST, e.community_event_id "
        f"LIMIT ${len(params)}"
    )
    unconfirmed_sql = (
        "SELECT count(*)::int AS n FROM data_center_community_event e "
        "LEFT JOIN jurisdictions j ON j.jurisdiction_id = e.jurisdiction_id "
        f"WHERE e.status = 'unconfirmed' AND {scoped}"
    )
    return events_sql, params, unconfirmed_sql, count_params


_EVENT_SOURCES_SQL = (
    "SELECT community_event_id, url, title, publisher, published_on, source, evidence "
    "FROM data_center_community_event_source WHERE community_event_id = ANY($1::text[]) "
    "ORDER BY published_on NULLS LAST, url"
)
_EVENT_RECORDINGS_SQL = (
    "SELECT community_event_id, video_url, title, channel, published_on, match_reason "
    "FROM data_center_community_event_recording WHERE community_event_id = ANY($1::text[]) "
    "ORDER BY published_on NULLS LAST, video_url"
)


async def _fetch_optional(conn: Any, sql: str, *params: Any) -> list[Any]:
    """Rows, or [] when the relation isn't in this database yet."""
    try:
        return await conn.fetch(sql, *params)
    except asyncpg.exceptions.UndefinedTableError:
        return []


@router.get("/community-events", response_model=CommunityEventsResponse)
async def list_community_events(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the city or government name."),
    project_id: str | None = Query(None, description="Only events about this data_center_project."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> CommunityEventsResponse:
    """
    Company-hosted data center community meetings (town halls, open houses, information
    sessions, community and public meetings) found in news and company announcements,
    newest first, each with every source that reports it and any recording candidates.
    Hosted by a company: these are not government meetings.

    Example:
        GET /api/data-centers/community-events?state=AL&city=Brookwood
    """
    scope = build_scope(state, city, None)
    applied = JobClaimScope(
        level="city" if scope.city else ("state" if scope.state_code else "national"),
        state_code=scope.state_code,
        state=scope.state,
        city=scope.city,
    )
    project_clean = _clean(project_id)
    events_sql, params, unconfirmed_sql, count_params = build_community_event_queries(
        applied, project_clean, limit
    )
    with tracer.start_as_current_span("data-centers.community-events") as span:
        span.set_attribute("community_events.scope_level", applied.level)
        span.set_attribute("community_events.state_code", applied.state_code or "")
        span.set_attribute("community_events.city", applied.city or "")
        span.set_attribute("community_events.project_id", project_clean or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(events_sql, *params)
                unconfirmed_rows = await conn.fetch(unconfirmed_sql, *count_params)
                ids = [r["community_event_id"] for r in rows]
                source_rows = await _fetch_optional(conn, _EVENT_SOURCES_SQL, ids) if ids else []
                recording_rows = await _fetch_optional(conn, _EVENT_RECORDINGS_SQL, ids) if ids else []
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("community_events.relation_missing", True)
            logger.warning("data-centers: 'data_center_community_event' isn't here yet ({}); empty list", e)
            return CommunityEventsResponse(scope=applied, project_id=project_clean, items=[])
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers community-events error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load community events")
        sources: dict[str, list[CommunityEventSource]] = {}
        for r in source_rows:
            row = dict(r)
            sources.setdefault(row.pop("community_event_id"), []).append(CommunityEventSource(**row))
        recordings: dict[str, list[RecordingCandidate]] = {}
        for r in recording_rows:
            row = dict(r)
            recordings.setdefault(row.pop("community_event_id"), []).append(RecordingCandidate(**row))
        items = [
            CommunityEvent(
                **dict(r),
                sources=sources.get(r["community_event_id"], []),
                recording_candidates=recordings.get(r["community_event_id"], []),
            )
            for r in rows
        ]
        unconfirmed = int(unconfirmed_rows[0]["n"]) if unconfirmed_rows else 0
        span.set_attribute("community_events.count", len(items))
        return CommunityEventsResponse(scope=applied, project_id=project_clean, unconfirmed=unconfirmed, items=items)


TimelineStage = Literal["announced", "company_meeting", "planning", "vote", "government_meeting"]

# Deterministic stage words, read from the decision's own headline/statement.
_PLANNING_RE = r"(?i)\m(planning commission|planning board|zoning|rezon\w*|site plan|land use|variance|annex\w*)\M"
_VOTE_RE = r"(?i)\m(vot(e|ed|es)|approv\w+|adopt\w*|ordinance|resolution)\M"


class ProjectCompany(BaseModel):
    master_org_id: str
    company_name: str | None = None
    role: str
    confidence: str
    source_url: str
    source_excerpt: str


class ProjectFigure(BaseModel):
    metric: str
    value: float
    unit: str
    source_url: str
    source_excerpt: str
    published_on: date | None = None


class TimelineItem(BaseModel):
    stage: TimelineStage
    on: date | None = Field(None, description="The date the source gives; null when it gives none.")
    label: str = Field(..., description="What happened, from the source's own words.")
    host: str = Field(..., description="Who held or did it: the company, or the government.")
    source_label: str = Field(..., description="Where it comes from: a publisher, a press release, a transcript.")
    url: str | None = None
    evidence: str | None = Field(None, description="Verbatim excerpt; matched words in <mark> where marked.")


class DataCenterProject(BaseModel):
    project_id: str
    project_name: str
    project_source: Literal["curated", "epoch"]
    data_center_site_id: str | None = None
    area: str | None = None
    city: str | None = None
    county: str | None = None
    state_code: str | None = None
    state: str | None = None
    jurisdiction_id: str | None = None
    status: str | None = None
    announced_on: date | None = Field(None, description="Only with the passage that dates it.")
    announced_source_url: str | None = None
    announced_source_excerpt: str | None = None
    has_conflicting_figures: bool = False
    source_kind: str
    source_url: str
    source_excerpt: str
    companies: list[ProjectCompany] = Field(default_factory=list)
    figures: list[ProjectFigure] = Field(default_factory=list)
    timeline: list[TimelineItem] = Field(default_factory=list)


class DataCenterProjectsResponse(BaseModel):
    scope: JobClaimScope
    total: int = 0
    items: list[DataCenterProject]


def build_project_queries(
    scope: JobClaimScope, project_id: str | None, source: str | None, limit: int
) -> tuple[str, list[Any], str, list[Any]]:
    """(projects SQL, params, count SQL, params). Curated projects first, then by name.

    A city scope matches the project's city or any of its governments' names
    (data_center_project_jurisdiction), so "Brookwood" also finds a project the sources
    place in Tuscaloosa County only when that county is one of its governments.
    """
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"p.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(
            f"(p.city ILIKE ${len(params)} OR EXISTS (SELECT 1 FROM data_center_project_jurisdiction pj "
            f"JOIN jurisdictions j ON j.jurisdiction_id = pj.jurisdiction_id "
            f"WHERE pj.project_id = p.project_id AND j.name ILIKE ${len(params)}))"
        )
    if project_id:
        params.append(project_id)
        where.append(f"p.project_id = ${len(params)}")
    if source:
        params.append(source)
        where.append(f"p.project_source = ${len(params)}")
    where_sql = " AND ".join(where) or "TRUE"
    count_params = list(params)
    params.append(limit)
    sql = (
        "SELECT p.project_id, p.project_name, p.project_source, p.data_center_site_id, p.area, p.city, "
        "p.county, p.state_code, p.state, p.jurisdiction_id, p.status, p.announced_on, "
        "p.announced_source_url, p.announced_source_excerpt, "
        "p.has_conflicting_figures, p.source_kind, p.source_url, p.source_excerpt "
        f"FROM data_center_project p WHERE {where_sql} "
        "ORDER BY (p.project_source = 'curated') DESC, p.announced_on DESC NULLS LAST, p.project_name "
        f"LIMIT ${len(params)}"
    )
    count_sql = f"SELECT count(*)::int AS n FROM data_center_project p WHERE {where_sql}"
    return sql, params, count_sql, count_params


_PROJECT_COMPANIES_SQL = (
    "SELECT pc.project_id, pc.master_org_id, c.company_name, pc.role, pc.confidence, pc.source_url, "
    "pc.source_excerpt FROM data_center_project_company pc "
    "LEFT JOIN mdm_organization_data_center c ON c.master_org_id = pc.master_org_id "
    "WHERE pc.project_id = ANY($1::text[]) ORDER BY pc.project_id, pc.role, c.company_name"
)
_PROJECT_FIGURES_SQL = (
    "SELECT project_id, metric, value::float8 AS value, unit, source_url, source_excerpt, published_on "
    "FROM data_center_project_figure WHERE project_id = ANY($1::text[]) "
    "ORDER BY project_id, metric, published_on NULLS LAST, source_url"
)
_PROJECT_EVENTS_SQL = (
    "SELECT e.project_id, e.community_event_id, e.host_name, e.event_kind, e.event_date, "
    "e.first_reported_on, e.title, s.url, s.publisher, s.evidence "
    "FROM data_center_community_event e "
    "LEFT JOIN LATERAL (SELECT url, publisher, evidence FROM data_center_community_event_source "
    "  WHERE community_event_id = e.community_event_id ORDER BY published_on NULLS LAST, url LIMIT 1) s ON TRUE "
    "WHERE e.status = 'confirmed' AND e.project_id = ANY($1::text[])"
)
_PROJECT_MENTIONS_SQL = (
    "SELECT pm.project_id, pm.record_type, pm.evidence, pm.event_decision_id, "
    "m.meeting_date, m.meeting_title, m.jurisdiction_name, m.video_url, "
    "d.headline, d.jurisdiction_name AS decision_jurisdiction, "
    f"(coalesce(d.headline, '') || ' ' || coalesce(d.decision_statement, '')) ~ '{_PLANNING_RE}' AS is_planning, "
    f"(coalesce(d.headline, '') || ' ' || coalesce(d.decision_statement, '')) ~ '{_VOTE_RE}' AS is_vote "
    "FROM data_center_project_mention pm "
    "LEFT JOIN data_center_meeting_mention m "
    "  ON m.data_center_meeting_mention_id = pm.data_center_meeting_mention_id "
    "LEFT JOIN LATERAL (SELECT headline, decision_statement, jurisdiction_name FROM event_decision "
    "  WHERE event_decision_id = pm.event_decision_id ORDER BY extracted_at DESC LIMIT 1) d ON TRUE "
    "WHERE pm.project_id = ANY($1::text[])"
)

_KIND_LABEL = {
    "town_hall": "Town hall",
    "community_meeting": "Community meeting",
    "open_house": "Open house",
    "information_session": "Information session",
    "public_meeting": "Public meeting",
}
_STAGE_ORDER = {"announced": 0, "company_meeting": 1, "planning": 2, "government_meeting": 2, "vote": 3}


def build_timeline(project: dict[str, Any], events: list[dict], mentions: list[dict]) -> list[TimelineItem]:
    """announced → company meeting → planning → vote, each labelled by its source and host.

    Dated items sort by date; undated ones follow, in stage order. Nothing is dated that the
    source doesn't date."""
    items: list[TimelineItem] = []
    if project.get("project_source") == "curated":
        items.append(
            TimelineItem(
                stage="announced",
                on=project.get("announced_on"),
                label=(f"{project['project_name']} announced" if project.get("announced_on")
                       else f"{project['project_name']} named in a "
                       + ("company announcement" if project.get("source_kind") == "company_announcement"
                          else "news article")),
                host=next((c.company_name for c in project.get("companies", []) if c.role == "developer"
                           and c.company_name), "The developer"),
                source_label="Company announcement" if project.get("source_kind") == "company_announcement"
                else "News article",
                # the passage that dates the announcement, when there is one; else the
                # passage that names the project (then the date is null too)
                url=project.get("announced_source_url") or project.get("source_url"),
                evidence=project.get("announced_source_excerpt") or project.get("source_excerpt"),
            )
        )
    for e in events:
        items.append(
            TimelineItem(
                stage="company_meeting",
                on=e.get("event_date"),
                label=f"{_KIND_LABEL.get(e['event_kind'], 'Meeting')} hosted by {e.get('host_name') or 'the company'}",
                host=f"{e.get('host_name') or 'The company'} (company-hosted, not a government meeting)",
                source_label=e.get("publisher") or "News article",
                url=e.get("url"),
                evidence=e.get("evidence") or e.get("title"),
            )
        )
    for m in mentions:
        if m["record_type"] == "meeting_passage":
            items.append(
                TimelineItem(
                    stage="government_meeting",
                    on=m.get("meeting_date"),
                    label=m.get("meeting_title") or "Government meeting",
                    host=m.get("jurisdiction_name") or "Local government",
                    source_label="Meeting transcript",
                    url=m.get("video_url"),
                    evidence=m.get("evidence"),
                )
            )
        else:
            stage: TimelineStage = "vote" if m.get("is_vote") else ("planning" if m.get("is_planning") else "government_meeting")
            items.append(
                TimelineItem(
                    stage=stage,
                    on=None,
                    label=m.get("headline") or "Government decision",
                    host=m.get("decision_jurisdiction") or "Local government",
                    source_label="Meeting decision",
                    url=f"/decisions/{m['event_decision_id']}" if m.get("event_decision_id") else None,
                    evidence=m.get("evidence"),
                )
            )
    items.sort(key=lambda t: (t.on is None, t.on or date.max, _STAGE_ORDER[t.stage]))
    return items


@router.get("/projects", response_model=DataCenterProjectsResponse)
async def list_data_center_projects(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; the project's city or one of its governments."),
    project_id: str | None = Query(None, description="One data_center_project."),
    source: Literal["curated", "epoch"] | None = Query(None, description="curated (announcements/news) or epoch."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> DataCenterProjectsResponse:
    """
    Data center projects with their companies, every sourced figure and a timeline:
    announced → company-hosted meeting → planning → council vote. Each timeline item says
    who held it (the company or the government) and where it comes from.

    Example:
        GET /api/data-centers/projects?state=AL
    """
    scope = build_scope(state, city, None)
    applied = JobClaimScope(
        level="city" if scope.city else ("state" if scope.state_code else "national"),
        state_code=scope.state_code,
        state=scope.state,
        city=scope.city,
    )
    project_clean = _clean(project_id)
    sql, params, count_sql, count_params = build_project_queries(applied, project_clean, source, limit)
    with tracer.start_as_current_span("data-centers.projects") as span:
        span.set_attribute("projects.scope_level", applied.level)
        span.set_attribute("projects.state_code", applied.state_code or "")
        span.set_attribute("projects.city", applied.city or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
                count_rows = await conn.fetch(count_sql, *count_params)
                ids = [r["project_id"] for r in rows]
                company_rows = await _fetch_optional(conn, _PROJECT_COMPANIES_SQL, ids) if ids else []
                figure_rows = await _fetch_optional(conn, _PROJECT_FIGURES_SQL, ids) if ids else []
                event_rows = await _fetch_optional(conn, _PROJECT_EVENTS_SQL, ids) if ids else []
                mention_rows = await _fetch_optional(conn, _PROJECT_MENTIONS_SQL, ids) if ids else []
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("projects.relation_missing", True)
            logger.warning("data-centers: 'data_center_project' isn't here yet ({}); empty list", e)
            return await redact_response(DataCenterProjectsResponse(scope=applied, items=[]), SNIPPET_FIELDS | {"label", "source_excerpt", "announced_source_excerpt"})
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers projects error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load data center projects")

        def group(rs: list[Any]) -> dict[str, list[dict]]:
            out: dict[str, list[dict]] = {}
            for r in rs:
                row = dict(r)
                out.setdefault(row.pop("project_id"), []).append(row)
            return out

        companies, figures = group(company_rows), group(figure_rows)
        events, mentions = group(event_rows), group(mention_rows)
        items = []
        for r in rows:
            row = dict(r)
            pid = row["project_id"]
            project = DataCenterProject(
                **row,
                companies=[ProjectCompany(**c) for c in companies.get(pid, [])],
                figures=[ProjectFigure(**f) for f in figures.get(pid, [])],
            )
            project.timeline = build_timeline(
                {**row, "companies": project.companies}, events.get(pid, []), mentions.get(pid, [])
            )
            items.append(project)
        total = int(count_rows[0]["n"]) if count_rows else len(items)
        span.set_attribute("projects.count", len(items))
        return await redact_response(DataCenterProjectsResponse(scope=applied, total=total, items=items), SNIPPET_FIELDS | {"label", "source_excerpt", "announced_source_excerpt"})


# --- who spoke for and against, and the recorded votes (#930) ------------------------------

POSITION_QUOTES_DEFAULT = 3
POSITION_QUOTES_MAX = 10


class PositionTotals(BaseModel):
    """Whole-scope sums from ``data_center_meeting_position``. Every field is null when the
    mart isn't loaded; ``votes_*`` are also null (never 0) when no decision recorded a tally."""

    meetings: int | None = Field(
        None, description="Meetings the counts come from: at least one counted speaker or one recorded tally."
    )
    meetings_reviewed: int | None = Field(
        None, description="Analysed meetings in scope where a data center came up (the mart's rows)."
    )
    speakers_for: int | None = None
    speakers_against: int | None = None
    speakers_question: int | None = None
    speakers_neutral: int | None = None
    decisions_with_tally: int | None = Field(
        None, description="Data center decisions whose vote tally records both a yes and a no count."
    )
    votes_for: int | None = None
    votes_against: int | None = None


class PositionQuote(BaseModel):
    """One public speaker's own words on a data center item, with the moment in the recording."""

    public_comment_id: str
    quote: str = Field(..., description="Verbatim from the transcript; rows without one are not returned.")
    speaker_role: str | None = None
    speaker_display_name: str | None = Field(
        None, description='"First L." (e.g. "Audra T."), first name only when ambiguous; null when no name was heard.'
    )
    jurisdiction_name: str | None = None
    state_code: str | None = None
    meeting_date: date | None = None
    video_url: str | None = None
    start_seconds: float | None = None
    jump_url: str | None = Field(None, description="video_url at start_seconds; null when untimed.")
    decision_headline: str | None = Field(
        None,
        description="The item the comment is on (a contested decision or an uncontested item); "
        "null for general public comment.",
    )
    match_basis: Literal["data_center_decision", "data_center_item", "own_words", "same_item"] | None = Field(
        None,
        description="Why the comment counts: its decision or uncontested item names a data center, "
        "its own words do, or another speaker on the same item does (#932).",
    )


class PositionQuotes(BaseModel):
    for_: list[PositionQuote] = Field(default_factory=list, alias="for")
    against: list[PositionQuote] = Field(default_factory=list)
    question: list[PositionQuote] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class PositionStateCount(BaseModel):
    """One state's sums from ``data_center_meeting_position`` (#1087)."""

    state_code: str
    speakers_for: int = 0
    speakers_against: int = 0
    speakers_question: int = 0
    speakers_neutral: int = 0
    meetings: int = Field(0, description="Meetings in the mart for the state (analysed, a data center came up).")
    public_against_meetings: int = Field(
        0,
        description="Meetings where Jev read the public as mostly opposed to a data center (P >= 0.7) (#1117): an AI "
        "reading of the transcript, not counted speakers. 0 when none or when data_center_meeting_lean isn't loaded.",
    )
    disagreement_meetings: int = Field(
        0,
        description="Meetings where Jev read the public as mostly opposed and officials as mostly supportive, and the "
        "outcome wasn't a moratorium, a denial or an approval of rules (#1117, the #1113 refined rule). 0 when none.",
    )


class LeanTotals(BaseModel):
    """National totals of Jev's meeting readings (#1122), from ``data_center_meeting_lean``. AI readings of the
    transcripts, never counted speakers; never narrowed by the scope."""

    public_against_meetings: int = Field(0, description="Meetings where Jev read the public as mostly opposed.")
    public_against_states: int = Field(0, description="States with at least one such meeting.")
    stopped_meetings: int = Field(
        0, description="Meetings whose data center outcome Jev read as tabled/deferred, denied or a moratorium."
    )
    disagreement_meetings: int = Field(0, description="Meetings where officials sided against the public (#1113 rule).")
    disagreement_states: int = Field(0, description="States with at least one such meeting.")
    public_for_meetings: int = Field(
        0,
        description="Meetings where Jev read the public as mostly supportive (P >= 0.7) (#1134). Kept for audit: hand checks "
        "found 'supported' unreliable (development/data-center-meeting-lean.md), so the hero never uses it in a claim.",
    )
    public_mixed_meetings: int = Field(
        0, description="Meetings where Jev read the public as mixed (P >= 0.7) (#1134). Kept for audit, like public_for."
    )
    public_spoke_meetings: int = Field(
        0,
        description="Meetings where Jev read the public as speaking on a data center at all (any lean but "
        "no_public_comment_on_data_center, P >= 0.7) (#1134).",
    )


class DataCenterPositionsResponse(BaseModel):
    scope: JobClaimScope
    available: bool = Field(
        True, description="False when the mart isn't in the database yet: totals are null, not zero."
    )
    totals: PositionTotals = Field(default_factory=PositionTotals)
    quotes: PositionQuotes = Field(default_factory=PositionQuotes)
    by_state: list[PositionStateCount] = Field(
        default_factory=list,
        description="Speakers per state across the whole country (never narrowed by the scope), for the home map "
        "(#1087). Only states with at least one meeting in the mart; empty when the mart isn't loaded.",
    )
    lean_totals: LeanTotals | None = Field(
        None,
        description="National totals of Jev's meeting readings for the home hero (#1122), never narrowed by the "
        "scope; null when data_center_meeting_lean (or a column) isn't in this database.",
    )
    scope_lean_totals: LeanTotals | None = Field(
        None,
        description="The same totals narrowed to the scope (#1134): the state, or the city as a case-insensitive "
        "substring of the meeting's jurisdiction name, like the speaker totals. Equal to lean_totals nationally; null "
        "when data_center_meeting_lean (or a column) isn't in this database.",
    )


def build_position_queries(
    scope: JobClaimScope, limit: int, per_state: int = 0
) -> tuple[str, list[Any], str, list[Any]]:
    """(totals SQL, params, quotes SQL, params). The rule for which comments and votes count
    lives in dbt (int_data_center__public_comment, data_center_meeting_position); this only
    sums and lists what the marts hold.

    Quotes from a speaker heard by name ("Rob D.") come first. With ``per_state`` > 0 the quotes are up to that many
    per state and side instead of ``limit`` per side, so the home map has a named speaker for each state it can."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"p.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"p.jurisdiction_name ILIKE ${len(params)}")
    where_sql = " AND ".join(where) or "TRUE"
    totals_sql = (
        "SELECT count(*)::int AS meetings_reviewed, "
        "count(*) FILTER (WHERE p.speakers_for + p.speakers_against + p.speakers_question "
        "+ p.speakers_neutral > 0 OR p.decisions_with_tally > 0)::int AS meetings, "
        "coalesce(sum(p.speakers_for), 0)::int AS speakers_for, "
        "coalesce(sum(p.speakers_against), 0)::int AS speakers_against, "
        "coalesce(sum(p.speakers_question), 0)::int AS speakers_question, "
        "coalesce(sum(p.speakers_neutral), 0)::int AS speakers_neutral, "
        "coalesce(sum(p.decisions_with_tally), 0)::int AS decisions_with_tally, "
        "sum(p.votes_for)::int AS votes_for, sum(p.votes_against)::int AS votes_against "
        f"FROM data_center_meeting_position p WHERE {where_sql}"
    )
    quote_params = [*params, per_state if per_state > 0 else limit]
    rank_by = "p.state_code, p.stance_bucket" if per_state > 0 else "p.stance_bucket"
    # One quote per meeting first, so a single long meeting doesn't fill a side; a named speaker before an unnamed one.
    quotes_sql = (
        "SELECT * FROM ("
        "SELECT p.public_comment_id, p.stance_bucket, p.quote, p.speaker_role, p.jurisdiction_name, "
        # Defensive read (#1036): works before the column reaches a serving copy.
        "to_jsonb(p) ->> 'speaker_display_name' AS speaker_display_name, "
        "p.state_code, p.meeting_date, p.video_url, p.start_seconds::float8 AS start_seconds, "
        "p.decision_headline, p.match_basis, "
        "row_number() OVER (PARTITION BY " + rank_by + " ORDER BY "
        "((to_jsonb(p) ->> 'speaker_display_name') IS NULL), p.meeting_rank, "
        "p.meeting_date DESC NULLS LAST, p.start_seconds NULLS LAST, p.public_comment_id) AS side_rank "
        "FROM (SELECT p.*, row_number() OVER (PARTITION BY p.stance_bucket, p.event_meeting_id "
        "ORDER BY p.start_seconds NULLS LAST, p.public_comment_id) AS meeting_rank "
        "FROM data_center_public_comment p "
        f"WHERE {where_sql} AND p.is_counted AND p.quote IS NOT NULL "
        "AND p.stance_bucket IN ('for', 'against', 'question')) p"
        f") q WHERE q.side_rank <= ${len(quote_params)} "
        "ORDER BY q.stance_bucket, q.side_rank"
    )
    return totals_sql, params, quotes_sql, quote_params


POSITION_QUOTES_PER_STATE_MAX = 5


POSITION_BY_STATE_SQL = (
    "SELECT p.state_code, "
    "coalesce(sum(p.speakers_for), 0)::int AS speakers_for, "
    "coalesce(sum(p.speakers_against), 0)::int AS speakers_against, "
    "coalesce(sum(p.speakers_question), 0)::int AS speakers_question, "
    "coalesce(sum(p.speakers_neutral), 0)::int AS speakers_neutral, "
    "count(*)::int AS meetings "
    "FROM data_center_meeting_position p WHERE p.state_code IS NOT NULL "
    "GROUP BY p.state_code ORDER BY p.state_code"
)
"""Per-state speaker sums for the whole country (#1087): no scope parameters, so a state or city page's
home map still shows every state. States with no row in the mart are simply absent."""


_LEAN_CONFIDENT = "coalesce(l.public_lean_p, 0) >= 0.7"
"""The confident threshold the mart's ``public_against`` uses (data_center_meeting_lean.sql), for the other leans (#1134)."""

LEAN_TOTALS_SQL = (
    "SELECT count(*) FILTER (WHERE l.public_against)::int AS public_against_meetings, "
    "count(DISTINCT l.state_code) FILTER (WHERE l.public_against)::int AS public_against_states, "
    "count(*) FILTER (WHERE l.dc_outcome IN ('tabled_or_deferred', 'denied', 'moratorium'))::int AS stopped_meetings, "
    "count(*) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_meetings, "
    "count(DISTINCT l.state_code) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_states, "
    f"count(*) FILTER (WHERE l.public_lean = 'mostly_supported' AND {_LEAN_CONFIDENT})::int AS public_for_meetings, "
    f"count(*) FILTER (WHERE l.public_lean = 'mixed' AND {_LEAN_CONFIDENT})::int AS public_mixed_meetings, "
    "count(*) FILTER (WHERE l.public_lean IN ('mostly_opposed', 'mostly_supported', 'mixed') "
    f"AND {_LEAN_CONFIDENT})::int AS public_spoke_meetings "
    "FROM data_center_meeting_lean l"
)
"""National totals of Jev's readings for the home hero (#1122): no scope parameters. The mart only holds screens
under the current Jev question version."""


def build_scope_lean_totals_query(scope: JobClaimScope) -> tuple[str, list[Any]]:
    """``LEAN_TOTALS_SQL`` narrowed to the scope (#1134): state code, then the city as an ILIKE substring of the
    meeting's jurisdiction name (the speaker totals' rule). Nationally it is ``LEAN_TOTALS_SQL`` with no parameters."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"l.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"l.jurisdiction_name ILIKE ${len(params)}")
    if not where:
        return LEAN_TOTALS_SQL, []
    return f"{LEAN_TOTALS_SQL} WHERE {' AND '.join(where)}", params


async def _fetch_lean_totals(conn: Any, sql: str = LEAN_TOTALS_SQL, params: list[Any] | None = None) -> LeanTotals | None:
    """``LEAN_TOTALS_SQL`` (or its scoped form) as a model, or None when data_center_meeting_lean (or a column) isn't
    in this database: the hero then leaves its AI-reading points out, never a failure."""
    try:
        rows = await conn.fetch(sql, *(params or []))
    except asyncpg.exceptions.PostgresError as e:
        logger.warning("data-centers: data_center_meeting_lean unavailable ({}); lean_totals null", e)
        return None
    if not rows:
        return None
    return LeanTotals(**{k: int(v or 0) for k, v in dict(rows[0]).items()})


def merge_lean_by_state(state_rows: list[Any], lean: dict[str, dict[str, int]]) -> list[PositionStateCount]:
    """Speaker sums per state plus Jev's lean counts (#1117). A state with lean counts but no speaker rows gets a row
    with 0 speakers and 0 meetings in the position mart, so the map can tint it; sorted by state code."""
    out: dict[str, PositionStateCount] = {}
    for r in state_rows:
        row = dict(r)
        out[row["state_code"]] = PositionStateCount(**{**row, **lean.get(row["state_code"], {})})
    for code, counts in lean.items():
        if code not in out:
            out[code] = PositionStateCount(state_code=code, **counts)
    return [out[k] for k in sorted(out)]


@router.get("/positions", response_model=DataCenterPositionsResponse)
async def data_center_positions(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    limit: int = Query(
        POSITION_QUOTES_DEFAULT, ge=1, le=POSITION_QUOTES_MAX, description="Quotes per side."
    ),
    per_state: int = Query(
        0,
        ge=0,
        le=POSITION_QUOTES_PER_STATE_MAX,
        description="If set, up to this many quotes per state and side instead of `limit` per side (the home map).",
    ),
) -> DataCenterPositionsResponse:
    """
    Who spoke for and against a data center item at local meetings, who asked a question,
    and the votes where a tally was recorded, for the scope; plus a few of the speakers'
    own words on each side, each linked to the moment in the recording.

    Only comments about the data center item count (a comment on another item of the same
    meeting never does). ``available`` is false and every total null when the mart isn't
    loaded; ``votes_for`` / ``votes_against`` are null when ``decisions_with_tally`` is 0.

    Example:
        GET /api/data-centers/positions?state=AL&city=Tuscaloosa
    """
    scope = build_scope(state, city, None)
    applied = JobClaimScope(
        level="city" if scope.city else ("state" if scope.state_code else "national"),
        state_code=scope.state_code,
        state=scope.state,
        city=scope.city,
    )
    totals_sql, params, quotes_sql, quote_params = build_position_queries(applied, limit, per_state)
    with tracer.start_as_current_span("data-centers.positions") as span:
        span.set_attribute("positions.scope_level", applied.level)
        span.set_attribute("positions.state_code", applied.state_code or "")
        span.set_attribute("positions.city", applied.city or "")
        span.set_attribute("positions.limit", limit)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("data-centers.positions.query"):
                    total_rows = await conn.fetch(totals_sql, *params)
                    quote_rows = await conn.fetch(quotes_sql, *quote_params)
                    state_rows = await conn.fetch(POSITION_BY_STATE_SQL)
                    state_lean = await _fetch_lean(conn, LEAN_BY_STATE_SQL)
                    lean_totals = await _fetch_lean_totals(conn)
                    scope_sql, scope_params = build_scope_lean_totals_query(applied)
                    scope_lean_totals = (
                        await _fetch_lean_totals(conn, scope_sql, scope_params) if scope_params else lean_totals
                    )
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("positions.relation_missing", True)
            logger.warning("data-centers: 'data_center_meeting_position' isn't here yet ({}); unavailable", e)
            return await redact_response(DataCenterPositionsResponse(scope=applied, available=False), TEXT_FIELDS)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers positions error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load data center positions")
        totals = PositionTotals(**dict(total_rows[0])) if total_rows else PositionTotals()
        if not totals.decisions_with_tally:
            totals.votes_for = totals.votes_against = None
        sides: dict[str, list[PositionQuote]] = {"for": [], "against": [], "question": []}
        for r in quote_rows:
            row = dict(r)
            side = row.pop("stance_bucket")
            row.pop("side_rank", None)
            if side not in sides:
                continue
            row["jump_url"] = jump_url(row["video_url"], row.get("start_seconds")) if row.get("video_url") else None
            sides[side].append(PositionQuote(**row))
        span.set_attribute("positions.meetings", totals.meetings or 0)
        return await redact_response(DataCenterPositionsResponse(
            scope=applied,
            totals=totals,
            quotes=PositionQuotes(for_=sides["for"], against=sides["against"], question=sides["question"]),
            by_state=merge_lean_by_state(state_rows, state_lean),
            lean_totals=lean_totals,
            scope_lean_totals=scope_lean_totals,
        ), TEXT_FIELDS)


# --- decisions on data center items (#933) ----------------------------------------------------------------------------

DECISIONS_DEFAULT = 200
DECISIONS_MAX = 500


class DataCenterDecision(DecisionPeople):
    """One decision a local meeting took on a data center item, debated or not."""

    data_center_decision_id: str
    contested: bool = Field(
        ..., description="True: debated (a contested decision). False: taken up without debate (consent agenda)."
    )
    headline: str | None = None
    outcome: str | None = None
    votes_for: int | None = Field(None, description="Recorded yes votes; null unless the tally records both sides.")
    votes_against: int | None = Field(None, description="Recorded no votes; null unless the tally records both sides.")
    vote_text: str | None = Field(
        None, description="How an uncontested item passed, as said (voice vote, 5-0); never parsed into numbers."
    )
    meeting_date: date | None = None
    jurisdiction_name: str | None = None
    state_code: str | None = None
    video_url: str | None = None
    decision_url: str | None = Field(None, description="Site path of the decision's page; contested decisions only.")
    meeting_url: str | None = Field(None, description="The meeting's page in the app (/meetings/{event_meeting_id}).")
    relevance: Literal["on_topic", "in_passing"] | None = Field(
        None,
        description="#1293: 'on_topic' when the headline names a data center project or rule, 'in_passing' otherwise "
        "(api/routes/topic_relevance.py, deterministic rules).",
    )
    relevance_basis: str | None = Field(None, description="Which rule decided; for audit.")


class DataCenterDecisionCounts(BaseModel):
    """Whole-scope counts (not capped by ``limit``). Null when the mart isn't loaded."""

    contested: int | None = None
    uncontested: int | None = None
    meetings: int | None = Field(None, description="Meetings the decisions were taken in.")
    on_topic: int | None = Field(None, description="#1293: decisions on a data center (topic_relevance rules).")
    in_passing: int | None = Field(None, description="#1293: decisions that only mention data centers.")


class DataCenterDecisionsResponse(BaseModel):
    scope: JobClaimScope
    available: bool = Field(
        True, description="False when the mart isn't in the database yet: counts are null, not zero."
    )
    counts: DataCenterDecisionCounts = Field(default_factory=DataCenterDecisionCounts)
    items: list[DataCenterDecision] = Field(default_factory=list)


def build_decision_queries(scope: JobClaimScope, limit: int) -> tuple[str, list[Any], str, list[Any]]:
    """(counts SQL, params, items SQL, params) over ``data_center_decision``. Which decisions are
    about a data center is decided in dbt; this only counts and lists them, newest first."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"d.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"d.jurisdiction_name ILIKE ${len(params)}")
    where_sql = " AND ".join(where) or "TRUE"
    counts_sql = (
        "SELECT count(*) FILTER (WHERE d.contested)::int AS contested, "
        "count(*) FILTER (WHERE NOT d.contested)::int AS uncontested, "
        "count(DISTINCT d.event_meeting_id)::int AS meetings "
        f"FROM data_center_decision d WHERE {where_sql}"
    )
    item_params = [*params, limit]
    items_sql = (
        "SELECT d.data_center_decision_id, d.contested, d.headline, d.outcome, d.votes_for, d.votes_against, "
        "d.vote_text, d.meeting_date, d.jurisdiction_name, d.state_code, d.video_url, d.decision_url, "
        "CASE WHEN d.event_meeting_id IS NOT NULL THEN '/meetings/' || d.event_meeting_id::text END AS meeting_url "
        f"FROM data_center_decision d WHERE {where_sql} "
        "ORDER BY d.meeting_date DESC NULLS LAST, d.data_center_decision_id "
        f"LIMIT ${len(item_params)}"
    )
    return counts_sql, params, items_sql, item_params


def decision_headlines_sql(scope: JobClaimScope) -> tuple[str, list[Any]]:
    """Every decision headline in scope, for the on-topic / in-passing counts (#1293)."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"d.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"d.jurisdiction_name ILIKE ${len(params)}")
    return f"SELECT d.headline FROM data_center_decision d WHERE {' AND '.join(where) or 'TRUE'}", params


async def _decision_people(items: list["DataCenterDecision"]) -> None:
    """Fill supported_by / opposed_by for decisions with a page (#1320), from event_decision.competing_views. Optional: a
    serving copy without event_decision or person_government leaves them empty."""
    from api.routes.decision_people import DECISION_PEOPLE_SQL, load_officials, people_fields

    ids = {it.decision_url.rsplit("/", 1)[-1]: it for it in items if it.decision_url and it.decision_url.startswith("/decisions/")}
    if not ids:
        return
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = [dict(r) for r in await conn.fetch(DECISION_PEOPLE_SQL, list(ids))]
            officials = await load_officials(conn, {(r.get("state_code"), r.get("jurisdiction_name")) for r in rows})
    except asyncpg.exceptions.PostgresError as e:
        logger.warning("data-centers: decision people unavailable ({})", e)
        return
    for r in rows:
        it = ids.get(str(r.get("event_decision_id")))
        if it is None:
            continue
        f = people_fields(r, officials)
        it.supported_by = [DecisionPerson(**p) for p in f["supported_by"]]
        it.opposed_by = [DecisionPerson(**p) for p in f["opposed_by"]]
        it.spoke_on_it = [DecisionPerson(**p) for p in f["spoke_on_it"]]
        it.supported_view = f["supported_view"]
        it.opposition_recorded = f["opposition_recorded"]


def mark_decision_relevance(counts: "DataCenterDecisionCounts", items: list["DataCenterDecision"], headlines: list[str | None]) -> None:
    """Stamp each listed decision on-topic or in passing and count the whole scope (#1293). No reading is joined: the
    data-center decisions carry only a headline, so an unsure one is in passing."""
    from api.routes.topic_relevance import classify_decision

    for it in items:
        it.relevance, it.relevance_basis = classify_decision("data-centers", it.headline, None)
    rels = [classify_decision("data-centers", h, None)[0] for h in headlines]
    counts.on_topic = sum(1 for r in rels if r == "on_topic")
    counts.in_passing = len(rels) - counts.on_topic


@router.get("/decisions", response_model=DataCenterDecisionsResponse)
async def data_center_decisions(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    limit: int = Query(DECISIONS_DEFAULT, ge=1, le=DECISIONS_MAX, description="Decisions to list, newest first."),
) -> DataCenterDecisionsResponse:
    """
    The decisions local meetings took on data center items in the scope: debated ones and
    ones taken up without debate (consent agenda), newest first, with the whole-scope counts.

    ``votes_for`` / ``votes_against`` are given only when a debated decision's tally records
    both sides; an item taken up without debate carries its vote as said in ``vote_text``.
    ``available`` is false and every count null when the mart isn't loaded.

    Example:
        GET /api/data-centers/decisions?state=GA
    """
    scope = build_scope(state, city, None)
    applied = JobClaimScope(
        level="city" if scope.city else ("state" if scope.state_code else "national"),
        state_code=scope.state_code,
        state=scope.state,
        city=scope.city,
    )
    counts_sql, params, items_sql, item_params = build_decision_queries(applied, limit)
    with tracer.start_as_current_span("data-centers.decisions") as span:
        span.set_attribute("decisions.scope_level", applied.level)
        span.set_attribute("decisions.state_code", applied.state_code or "")
        span.set_attribute("decisions.city", applied.city or "")
        span.set_attribute("decisions.limit", limit)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("data-centers.decisions.query"):
                    count_rows = await conn.fetch(counts_sql, *params)
                    item_rows = await conn.fetch(items_sql, *item_params)
                    head_sql, head_params = decision_headlines_sql(applied)
                    headlines = [r["headline"] for r in await conn.fetch(head_sql, *head_params)]
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("decisions.relation_missing", True)
            logger.warning("data-centers: 'data_center_decision' isn't here yet ({}); unavailable", e)
            return await redact_response(DataCenterDecisionsResponse(scope=applied, available=False), SNIPPET_FIELDS | {"vote_text"})
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers decisions error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load data center decisions")
        counts = DataCenterDecisionCounts(**dict(count_rows[0])) if count_rows else DataCenterDecisionCounts()
        items = [DataCenterDecision(**dict(r)) for r in item_rows]
        mark_decision_relevance(counts, items, headlines)
        await _decision_people(items)
        span.set_attribute("decisions.items", len(items))
        span.set_attribute("decisions.on_topic", counts.on_topic or 0)
        return await redact_response(DataCenterDecisionsResponse(scope=applied, counts=counts, items=items), SNIPPET_FIELDS | {"vote_text"})


# --- upcoming data center hearings, verified against the official page (#955) ------------------------------------------

HEARINGS_DEFAULT = 100
HEARINGS_MAX = 500


class DataCenterHearing(BaseModel):
    """A data center hearing whose official government page states the date together with the data center item."""

    data_center_hearing_id: str
    jurisdiction_id: str | None = None
    jurisdiction_name: str | None = None
    state_code: str | None = None
    state: str | None = None
    body_name: str | None = None
    topic: str | None = None
    meeting_date: date
    source_url: str = Field(..., description="The official page that states the hearing.")
    source_name: str | None = None
    evidence: str | None = Field(None, description="Verbatim excerpt of the official page; matched words in <mark>.")
    tentative: bool = Field(False, description="The page calls the date tentative, expected, not final or to be determined.")
    checked_at: datetime | None = Field(None, description="When the official page was last read.")
    is_upcoming: bool = Field(..., description="The meeting is today or later.")


class DataCenterHearingCounts(BaseModel):
    upcoming: int | None = None
    past: int | None = None


class DataCenterHearingsResponse(BaseModel):
    scope: JobClaimScope
    available: bool = Field(True, description="False when the table isn't loaded: counts are null, not zero.")
    counts: DataCenterHearingCounts = Field(default_factory=DataCenterHearingCounts)
    items: list[DataCenterHearing] = Field(default_factory=list)


def build_hearing_queries(scope: JobClaimScope, when: str, limit: int) -> tuple[str, list[Any], str, list[Any]]:
    """(items SQL, params, counts SQL, params) over ``data_center_hearing_verified``, the served
    slice that holds verified hearings only (verification happens in dbt; an unverified lead is
    never published). Upcoming first (soonest), then past (newest)."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"h.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"h.jurisdiction_name ILIKE ${len(params)}")
    counts_where = " AND ".join(where) or "TRUE"
    counts_params = list(params)
    if when == "upcoming":
        where.append("h.meeting_date >= current_date")
    elif when == "past":
        where.append("h.meeting_date < current_date")
    params.append(limit)
    items_sql = (
        "SELECT h.data_center_hearing_id, h.jurisdiction_id, h.jurisdiction_name, h.state_code, h.state, "
        "h.body_name, h.topic, h.meeting_date, h.source_url, h.source_name, h.evidence, h.tentative, "
        "h.checked_at, (h.meeting_date >= current_date) AS is_upcoming "
        f"FROM data_center_hearing_verified h WHERE {' AND '.join(where) or 'TRUE'} "
        "ORDER BY (h.meeting_date >= current_date) DESC, "
        "CASE WHEN h.meeting_date >= current_date THEN h.meeting_date END ASC, "
        "h.meeting_date DESC, h.data_center_hearing_id "
        f"LIMIT ${len(params)}"
    )
    counts_sql = (
        "SELECT count(*) FILTER (WHERE h.meeting_date >= current_date)::int AS upcoming, "
        "count(*) FILTER (WHERE h.meeting_date < current_date)::int AS past "
        f"FROM data_center_hearing_verified h WHERE {counts_where}"
    )
    return items_sql, params, counts_sql, counts_params


@router.get("/hearings", response_model=DataCenterHearingsResponse)
async def list_data_center_hearings(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    when: Literal["upcoming", "past", "all"] = Query("upcoming", description="Which meetings to list."),
    limit: int = Query(HEARINGS_DEFAULT, ge=1, le=HEARINGS_MAX, description="Hearings to list."),
) -> DataCenterHearingsResponse:
    """
    Upcoming local government hearings on data centers whose official page (a government
    agenda, notice or project page) states the date together with the data center item, each
    with a verbatim excerpt and the link; ``tentative`` when the page says the date isn't final.
    Leads that aren't backed by an official page are never returned. ``available`` is false, with null counts, when the table isn't loaded.

    Example:
        GET /api/data-centers/hearings?state=AZ&when=upcoming
    """
    scope = build_scope(state, city, None)
    applied = JobClaimScope(
        level="city" if scope.city else ("state" if scope.state_code else "national"),
        state_code=scope.state_code,
        state=scope.state,
        city=scope.city,
    )
    items_sql, params, counts_sql, counts_params = build_hearing_queries(applied, when, limit)
    with tracer.start_as_current_span("data-centers.hearings") as span:
        span.set_attribute("hearings.scope_level", applied.level)
        span.set_attribute("hearings.when", when)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("data-centers.hearings.query"):
                    rows = await conn.fetch(items_sql, *params)
                    count_rows = await conn.fetch(counts_sql, *counts_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("hearings.relation_missing", True)
            logger.warning("data-centers: 'data_center_hearing_verified' isn't here yet ({}); unavailable", e)
            return await redact_response(DataCenterHearingsResponse(scope=applied, available=False), TEXT_FIELDS)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers hearings error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load data center hearings")
        counts = DataCenterHearingCounts(**dict(count_rows[0])) if count_rows else DataCenterHearingCounts()
        items = [DataCenterHearing(**dict(r)) for r in rows]
        span.set_attribute("hearings.items", len(items))
        return await redact_response(DataCenterHearingsResponse(scope=applied, counts=counts, items=items), TEXT_FIELDS)
