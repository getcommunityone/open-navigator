"""Data center sites over time (#1348): ``GET /api/data-centers/sites-timeline``.

Backs the Data Center Story's "Over time" screen. Each site appears in the year of its earliest real date on
record (``data_center_site_timeline.appear_year``: the US Data Center Registry's announced date, or Epoch AI's first
dated timeline row). A site with no date is counted in ``undated``, never placed at a guessed year (CLAUDE.md, No
Fabricated Data).

A site's phase in a year (the per-year totals and the map's dot colour use the same rule; the page mirrors it in
``web_app/src/utils/siteTimeline.ts``):

* an Epoch AI site with a dated timeline is ``planned`` before its first dated row, ``under_construction`` from it and
  ``operating`` from its first row with a building operational (a year after this one is Epoch's projection);
* every other site keeps its status today (the registry publishes no history), ``status_not_published`` when none.

Years are integers in SQL and 4-digit strings on the wire (CLAUDE.md, Calendar Years). The per-year totals are
computed in SQL, from the first year a site appears to the later of this year and the last
expected operating year. Sites narrow by state only (the story draws a city's state, and says so).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.data_centers import JobClaimScope, SiteStatus, build_scope
from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/data-centers", tags=["data-centers"])
tracer = trace.get_tracer(__name__)

PHASES = ("planned", "under_construction", "operating", "cancelled", "no_longer_listed", "status_not_published")

# One expression, used by the totals: the site's phase in year ``y.year`` (see the module docstring).
PHASE_SQL = (
    "CASE WHEN s.source = 'epoch' AND s.first_report_year IS NOT NULL THEN "
    "CASE WHEN s.operating_year IS NOT NULL AND y.year >= s.operating_year THEN 'operating' "
    "WHEN y.year >= s.first_report_year THEN 'under_construction' ELSE 'planned' END "
    "ELSE coalesce(s.status, 'status_not_published') END"
)


class TimelineSite(BaseModel):
    """One dated data center site; unknown values are null."""

    data_center_site_id: str
    site_name: str
    operator: str | None = None
    owner: str | None = None
    status: SiteStatus | None = Field(None, description="Status today, as on data_center_site.")
    source: str
    source_name: str
    source_url: str | None = None
    state_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    appear_year: str = Field(..., description="Year of the site's earliest real date on record (a 4-digit string).")
    appear_basis: str = Field(..., description="announced (registry) or first_report (Epoch AI's first dated row).")
    appear_precision: str | None = Field(None, description="day, month or year.")
    first_report_year: str | None = None
    operating_year: str | None = None
    operating_is_expected: bool = False
    capacity_mw_operational: float | None = None
    capacity_mw_planned: float | None = None
    it_power_mw: float | None = None


class TimelineYear(BaseModel):
    """Sites on record by a year, by their phase in that year."""

    year: str
    planned: int = 0
    under_construction: int = 0
    operating: int = 0
    cancelled: int = 0
    no_longer_listed: int = 0
    status_not_published: int = 0
    total: int = 0
    is_future: bool = Field(..., description="After this year: Epoch's projected phases only.")


class SitesTimelineResponse(BaseModel):
    scope: JobClaimScope
    city_applied: bool = Field(False, description="Always false: sites narrow by state only.")
    available: bool = Field(..., description="False when the timeline table isn't in the database yet.")
    current_year: str
    first_year: str | None = None
    last_year: str | None = None
    dated: int = Field(0, description="Sites with a date on record (all of them, mapped or not).")
    mapped: int = Field(0, description="Dated sites with coordinates.")
    undated: int = Field(0, description="Sites in scope with no date on record.")
    undated_by_status: dict[str, int] = Field(default_factory=dict)
    sites: list[TimelineSite] = Field(default_factory=list)
    years: list[TimelineYear] = Field(default_factory=list)


_YEAR_FIELDS = ("appear_year", "first_report_year", "operating_year", "year")


def _years_as_text(row: dict[str, Any]) -> dict[str, Any]:
    """Bare years go over the wire as strings (CLAUDE.md, Calendar Years): JSON numbers get locale-formatted."""
    return {k: (str(v) if k in _YEAR_FIELDS and v is not None else v) for k, v in row.items()}


def _scope_where(scope: JobClaimScope, params: list[Any]) -> str:
    if scope.state_code:
        params.append(scope.state_code)
        return f"t.state_code = ${len(params)}"
    return "TRUE"


def build_sites_sql(scope: JobClaimScope) -> tuple[str, list[Any]]:
    """Every dated site in scope (coordinates or not), oldest first."""
    params: list[Any] = []
    where = _scope_where(scope, params)
    sql = (
        "SELECT t.data_center_site_id, ds.site_name, ds.operator, ds.owner, ds.status, ds.source, ds.source_name, "
        "ds.source_url, t.state_code, t.latitude, t.longitude, t.appear_year, t.appear_basis, t.appear_precision, "
        "t.first_report_year, t.operating_year, t.operating_is_expected, ds.capacity_mw_operational, "
        "ds.capacity_mw_planned, ds.it_power_mw "
        "FROM data_center_site_timeline t JOIN data_center_site ds USING (data_center_site_id) "
        f"WHERE t.appear_year IS NOT NULL AND {where} ORDER BY t.appear_year, ds.site_name"
    )
    return sql, params


def build_undated_sql(scope: JobClaimScope) -> tuple[str, list[Any]]:
    """Sites in scope with no date on record, by status today."""
    params: list[Any] = []
    where = _scope_where(scope, params)
    sql = (
        "SELECT coalesce(ds.status, 'status_not_published') AS status, count(*)::int AS n "
        "FROM data_center_site_timeline t JOIN data_center_site ds USING (data_center_site_id) "
        f"WHERE t.appear_year IS NULL AND {where} GROUP BY 1"
    )
    return sql, params


def build_years_sql(scope: JobClaimScope, current_year: int) -> tuple[str, list[Any]]:
    """Per-year totals by phase, from the first year a site appears to max(this year, last expected operating year)."""
    params: list[Any] = [current_year]
    where = _scope_where(scope, params)
    counts = ", ".join(f"count(p.phase) FILTER (WHERE p.phase = '{ph}')::int AS {ph}" for ph in PHASES)
    sql = (
        "WITH s AS ("
        "SELECT t.appear_year, t.first_report_year, t.operating_year, ds.status, ds.source "
        "FROM data_center_site_timeline t JOIN data_center_site ds USING (data_center_site_id) "
        f"WHERE t.appear_year IS NOT NULL AND {where}), "
        "b AS (SELECT min(appear_year) AS lo, greatest($1::int, max(appear_year), coalesce(max(operating_year), 0)) AS hi FROM s), "
        "y AS (SELECT generate_series(b.lo, b.hi) AS year FROM b WHERE b.lo IS NOT NULL), "
        f"p AS (SELECT y.year, {PHASE_SQL} AS phase FROM y JOIN s ON s.appear_year <= y.year) "
        f"SELECT y.year, {counts}, count(p.phase)::int AS total, (y.year > $1::int) AS is_future "
        "FROM y LEFT JOIN p ON p.year = y.year GROUP BY y.year ORDER BY y.year"
    )
    return sql, params


@router.get("/sites-timeline", response_model=SitesTimelineResponse)
async def data_center_sites_timeline(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="Accepted so a page's scope can be passed through; sites narrow by state."),
) -> SitesTimelineResponse:
    """
    Data center sites placed in the year of their earliest real date, with coordinates, and the running total by
    phase per year (Epoch AI and the US Data Center Registry, CC BY 4.0).

    Example:
        GET /api/data-centers/sites-timeline?state=VA
    """
    scope = build_scope(state, city, None)
    applied = JobClaimScope(
        level="state" if scope.state_code else "national", state_code=scope.state_code, state=scope.state
    )
    current_year = date.today().year
    sites_sql, sites_params = build_sites_sql(applied)
    undated_sql, undated_params = build_undated_sql(applied)
    years_sql, years_params = build_years_sql(applied, current_year)
    with tracer.start_as_current_span("data-centers.sites-timeline") as span:
        span.set_attribute("sites_timeline.scope_level", applied.level)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                site_rows = await conn.fetch(sites_sql, *sites_params)
                undated_rows = await conn.fetch(undated_sql, *undated_params)
                year_rows = await conn.fetch(years_sql, *years_params)
        except (asyncpg.exceptions.UndefinedTableError, asyncpg.exceptions.UndefinedColumnError) as e:
            span.set_attribute("sites_timeline.relation_missing", True)
            logger.warning("data-centers: 'data_center_site_timeline' isn't here yet ({}); unavailable", e)
            return SitesTimelineResponse(scope=applied, available=False, current_year=str(current_year))
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers sites-timeline error (scope={}): {}", applied.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load the data center sites timeline")
        sites = [TimelineSite(**_years_as_text(dict(r))) for r in site_rows]
        years = [TimelineYear(**_years_as_text(dict(r))) for r in year_rows]
        undated_by_status = {r["status"]: r["n"] for r in undated_rows if r["n"]}
        span.set_attribute("sites_timeline.dated", len(sites))
        return SitesTimelineResponse(
            scope=applied,
            available=True,
            current_year=str(current_year),
            first_year=years[0].year if years else None,
            last_year=years[-1].year if years else None,
            dated=len(sites),
            mapped=sum(1 for s in sites if s.latitude is not None and s.longitude is not None),
            undated=sum(undated_by_status.values()),
            undated_by_status=undated_by_status,
            sites=sites,
            years=years,
        )
