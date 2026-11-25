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


class DataCenterMeetingMentionCounts(BaseModel):
    """Real counts for the whole scope (before ``limit``): 0 means none."""

    passages: int = 0
    meetings: int = 0
    site_specific: int = 0


class DataCenterMeetingMentionsResponse(BaseModel):
    scope: JobClaimScope
    counts: DataCenterMeetingMentionCounts = Field(default_factory=DataCenterMeetingMentionCounts)
    items: list[DataCenterMeetingMention]


def build_mention_queries(
    scope: JobClaimScope, site_id: str | None, strength: str | None, limit: int
) -> tuple[str, list[Any], str, list[Any]]:
    """(items SQL, params, counts SQL, params). Newest meeting first, then by moment in the meeting."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"m.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"m.jurisdiction_name ILIKE ${len(params)}")
    if site_id:
        params.append(site_id)
        where.append(f"m.data_center_site_id = ${len(params)}")
    if strength:
        params.append(strength)
        where.append(f"m.match_strength = ${len(params)}")
    where_sql = " AND ".join(where) or "TRUE"
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
) -> DataCenterMeetingMentionsResponse:
    """
    Meeting passages where a data center was discussed, newest meeting first, each with a
    quoted, highlighted excerpt of the transcript and the moment to jump to.

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
    with tracer.start_as_current_span("data-centers.meeting-mentions") as span:
        span.set_attribute("meeting_mentions.scope_level", applied.level)
        span.set_attribute("meeting_mentions.state_code", applied.state_code or "")
        span.set_attribute("meeting_mentions.city", applied.city or "")
        span.set_attribute("meeting_mentions.site_id", site_clean or "")
        span.set_attribute("meeting_mentions.limit", limit)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("data-centers.meeting-mentions.query"):
                    rows = await conn.fetch(items_sql, *params)
                    count_rows = await conn.fetch(counts_sql, *counts_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("meeting_mentions.relation_missing", True)
            logger.warning("data-centers: relation 'data_center_meeting_mention' isn't here yet ({}); empty list", e)
            return DataCenterMeetingMentionsResponse(scope=applied, items=[])
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers meeting-mentions error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load meeting mentions")
        counts = (
            DataCenterMeetingMentionCounts(**dict(count_rows[0])) if count_rows else DataCenterMeetingMentionCounts()
        )
        items = []
        for r in rows:
            row = dict(r)
            row["jump_url"] = jump_url(row["video_url"], row.get("start_seconds"))
            items.append(DataCenterMeetingMention(**row))
        span.set_attribute("meeting_mentions.count", len(items))
        return DataCenterMeetingMentionsResponse(scope=applied, counts=counts, items=items)


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
            return DataCenterProjectsResponse(scope=applied, items=[])
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
        return DataCenterProjectsResponse(scope=applied, total=total, items=items)


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


class DataCenterPositionsResponse(BaseModel):
    scope: JobClaimScope
    available: bool = Field(
        True, description="False when the mart isn't in the database yet: totals are null, not zero."
    )
    totals: PositionTotals = Field(default_factory=PositionTotals)
    quotes: PositionQuotes = Field(default_factory=PositionQuotes)


def build_position_queries(scope: JobClaimScope, limit: int) -> tuple[str, list[Any], str, list[Any]]:
    """(totals SQL, params, quotes SQL, params). The rule for which comments and votes count
    lives in dbt (int_data_center__public_comment, data_center_meeting_position); this only
    sums and lists what the marts hold."""
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
    quote_params = [*params, limit]
    # One quote per meeting first, so a single long meeting doesn't fill a side.
    quotes_sql = (
        "SELECT * FROM ("
        "SELECT p.public_comment_id, p.stance_bucket, p.quote, p.speaker_role, p.jurisdiction_name, "
        "p.state_code, p.meeting_date, p.video_url, p.start_seconds::float8 AS start_seconds, "
        "p.decision_headline, p.match_basis, "
        "row_number() OVER (PARTITION BY p.stance_bucket ORDER BY p.meeting_rank, "
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


@router.get("/positions", response_model=DataCenterPositionsResponse)
async def data_center_positions(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    limit: int = Query(
        POSITION_QUOTES_DEFAULT, ge=1, le=POSITION_QUOTES_MAX, description="Quotes per side."
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
    totals_sql, params, quotes_sql, quote_params = build_position_queries(applied, limit)
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
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("positions.relation_missing", True)
            logger.warning("data-centers: 'data_center_meeting_position' isn't here yet ({}); unavailable", e)
            return DataCenterPositionsResponse(scope=applied, available=False)
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
        return DataCenterPositionsResponse(
            scope=applied,
            totals=totals,
            quotes=PositionQuotes(for_=sides["for"], against=sides["against"], question=sides["question"]),
        )


# --- decisions on data center items (#933) ----------------------------------------------------------------------------

DECISIONS_DEFAULT = 200
DECISIONS_MAX = 500


class DataCenterDecision(BaseModel):
    """One decision a local meeting took on a data center item, debated or not."""

    data_center_decision_id: str
    contested: bool = Field(
        ..., description="True: debated (a contested decision). False: passed without debate (consent agenda)."
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


class DataCenterDecisionCounts(BaseModel):
    """Whole-scope counts (not capped by ``limit``). Null when the mart isn't loaded."""

    contested: int | None = None
    uncontested: int | None = None
    meetings: int | None = Field(None, description="Meetings the decisions were taken in.")


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
        "d.vote_text, d.meeting_date, d.jurisdiction_name, d.state_code, d.video_url, d.decision_url "
        f"FROM data_center_decision d WHERE {where_sql} "
        "ORDER BY d.meeting_date DESC NULLS LAST, d.data_center_decision_id "
        f"LIMIT ${len(item_params)}"
    )
    return counts_sql, params, items_sql, item_params


@router.get("/decisions", response_model=DataCenterDecisionsResponse)
async def data_center_decisions(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    limit: int = Query(DECISIONS_DEFAULT, ge=1, le=DECISIONS_MAX, description="Decisions to list, newest first."),
) -> DataCenterDecisionsResponse:
    """
    The decisions local meetings took on data center items in the scope: debated ones and
    ones passed without debate (consent agenda), newest first, with the whole-scope counts.

    ``votes_for`` / ``votes_against`` are given only when a debated decision's tally records
    both sides; an item passed without debate carries its vote as said in ``vote_text``.
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
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("decisions.relation_missing", True)
            logger.warning("data-centers: 'data_center_decision' isn't here yet ({}); unavailable", e)
            return DataCenterDecisionsResponse(scope=applied, available=False)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers decisions error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load data center decisions")
        counts = DataCenterDecisionCounts(**dict(count_rows[0])) if count_rows else DataCenterDecisionCounts()
        items = [DataCenterDecision(**dict(r)) for r in item_rows]
        span.set_attribute("decisions.items", len(items))
        return DataCenterDecisionsResponse(scope=applied, counts=counts, items=items)
