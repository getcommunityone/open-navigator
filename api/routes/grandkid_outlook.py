"""
"Grandkid outlook" intergenerational-mobility lookup — GET /api/grandkid-outlook.

Serves Opportunity Atlas (Opportunity Insights) mobility figures for a home-page
slopegraph that compares a local commuting zone (CZ) against the United States:
for children raised at a given parent income bracket, what adult income rank did
they reach on average.

Source (read-only, never transformed here — dbt owns the modeling):
- public.opportunity_atlas_mobility           (grain: cz × race × gender × parent_income_level)
- public.opportunity_atlas_mobility_national  (grain: race × gender × parent_income_level)

Per CLAUDE.md no-fabricated-data: child_income_rank/child_percentile are legitimately
NULL when the source had too few people for a race×gender cell in a CZ. That is an
explicit "not enough data" state (available=false), NOT an error, and the `note`
prose is always generated from the REAL returned numbers — never a hard-coded figure.

The serving search_path (public in dev / gold in prod) is set per-connection on the
shared pool, so tables are referenced unqualified like the other serving routes.
asyncpg returns NUMERIC as Decimal; we cast to float at the JSON boundary.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/api/grandkid-outlook", tags=["grandkid-outlook"])
tracer = trace.get_tracer(__name__)

_SOURCE = "Opportunity Insights — Opportunity Atlas (Chetty, Hendren, Jones & Porter, 2018)"
_SOURCE_URL = "https://www.opportunityatlas.org/"

# parent_income_level -> parent_percentile (matches the modeled domain 25/50/75).
_PARENT_PERCENTILE = {"low": 25, "middle": 50, "high": 75}


class RaceEnum(str, Enum):
    pooled = "pooled"
    white = "white"
    black = "black"
    hisp = "hisp"
    asian = "asian"
    natam = "natam"
    other = "other"


class GenderEnum(str, Enum):
    pooled = "pooled"
    male = "male"
    female = "female"


class ParentIncomeEnum(str, Enum):
    low = "low"
    middle = "middle"
    high = "high"


class OutlookQuery(BaseModel):
    """Validated query params — out-of-domain race/gender/parent_income -> 422."""

    state: Optional[str] = None
    city: Optional[str] = None
    race: RaceEnum = RaceEnum.pooled
    gender: GenderEnum = GenderEnum.pooled
    parent_income: ParentIncomeEnum = ParentIncomeEnum.low


class LocalCell(BaseModel):
    available: bool
    child_income_rank: Optional[float] = None
    child_percentile: Optional[float] = None
    n: Optional[float] = None


class NationalCell(BaseModel):
    available: bool
    child_income_rank: Optional[float] = None
    child_percentile: Optional[float] = None
    total_n: Optional[float] = None


class GrandkidOutlookResponse(BaseModel):
    race: str
    gender: str
    parent_income_level: str
    parent_percentile: int
    resolved: bool
    cz_name: Optional[str] = None
    scope_label: str
    local: Optional[LocalCell] = None
    national: NationalCell
    note: str
    source: str = _SOURCE
    source_url: str = _SOURCE_URL


# Principal CZ for a place name: czname is not unique, so pick the (pooled,pooled)
# row with the largest n. State is not CZ-keyed; accepted but unused for selection.
_RESOLVE_CZ_SQL = """
    SELECT cz, czname, n
    FROM opportunity_atlas_mobility
    WHERE lower(czname) = lower($1)
      AND race = 'pooled'
      AND gender = 'pooled'
    ORDER BY n DESC NULLS LAST
    LIMIT 1
"""

_LOCAL_SQL = """
    SELECT child_income_rank, child_percentile, n
    FROM opportunity_atlas_mobility
    WHERE cz = $1
      AND race = $2
      AND gender = $3
      AND parent_income_level = $4
    LIMIT 1
"""

_NATIONAL_SQL = """
    SELECT child_income_rank, child_percentile, total_n
    FROM opportunity_atlas_mobility_national
    WHERE race = $1
      AND gender = $2
      AND parent_income_level = $3
    LIMIT 1
"""


def _f(value) -> Optional[float]:
    """Decimal/None -> float/None for the JSON wire."""
    return None if value is None else float(value)


def _parent_phrase(parent_percentile: int) -> str:
    """Human phrasing for the parent income bracket, keyed off the percentile."""
    if parent_percentile == 25:
        return "the 25th income percentile (lower-income)"
    if parent_percentile == 50:
        return "the middle (50th income percentile)"
    return "the 75th income percentile (higher-income)"


def _ordinal_percentile(pct: float) -> str:
    """Render a percentile for prose from the REAL number, rounded to 1 dp.

    A whole value gets an English ordinal suffix ("35th percentile"); a value
    with a fractional part reads "the 35.1 percentile" (no awkward "35.1th").
    """
    rounded = round(pct, 1)
    if rounded == int(rounded):
        n = int(rounded)
        if 10 <= n % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"the {n}{suffix} percentile"
    return f"the {rounded:g} percentile"


def _build_note(
    *,
    parent_percentile: int,
    scope_label: str,
    local: Optional[LocalCell],
    national: NationalCell,
) -> str:
    """Prose generated from REAL returned numbers (never hard-coded).

    Prefer the local figure; fall back to the U.S. national number when the local
    cell is missing or unavailable (too few people for this group in that CZ).
    """
    bracket = _parent_phrase(parent_percentile)

    if local is not None and local.available and local.child_percentile is not None:
        child = _ordinal_percentile(local.child_percentile)
        return (
            f"Children whose parents earned at {bracket} grew up to reach about "
            f"{child}, on average, in {scope_label}."
        )

    if national.available and national.child_percentile is not None:
        child = _ordinal_percentile(national.child_percentile)
        # Distinguish "we matched a place but it lacks data for this group" from
        # "no place / national-only" so the UI copy is honest either way.
        if local is not None and not local.available:
            return (
                f"There isn't enough data for this group in {scope_label}. "
                f"Nationally, children whose parents earned at {bracket} grew up to "
                f"reach about {child}, on average."
            )
        return (
            f"Children whose parents earned at {bracket} grew up to reach about "
            f"{child}, on average, in the United States."
        )

    return "Not enough data is available for this group."


@router.get("", response_model=GrandkidOutlookResponse)
async def get_grandkid_outlook(
    params: OutlookQuery = Depends(),
) -> GrandkidOutlookResponse:
    """Local-vs-national intergenerational mobility for a place and demographic group.

    Resolution: a `city` is matched case-insensitively to its principal commuting
    zone (largest-n pooled/pooled row). The national row is always returned so the
    slopegraph has a baseline even when the place doesn't match or lacks data.
    """
    race = params.race.value
    gender = params.gender.value
    parent_income = params.parent_income.value
    parent_percentile = _PARENT_PERCENTILE[parent_income]
    city = params.city.strip() if params.city else None

    with tracer.start_as_current_span("grandkid-outlook") as span:
        span.set_attribute("grandkid_outlook.city", city or "")
        span.set_attribute("grandkid_outlook.state", params.state or "")
        span.set_attribute("grandkid_outlook.race", race)
        span.set_attribute("grandkid_outlook.gender", gender)
        span.set_attribute("grandkid_outlook.parent_income", parent_income)

        cz: Optional[int] = None
        cz_name: Optional[str] = None
        local: Optional[LocalCell] = None
        national = NationalCell(available=False)

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                if city:
                    with tracer.start_as_current_span("grandkid-outlook-resolve-cz"):
                        cz_row = await conn.fetchrow(_RESOLVE_CZ_SQL, city)
                    if cz_row is not None:
                        cz = cz_row["cz"]
                        cz_name = cz_row["czname"]

                if cz is not None:
                    with tracer.start_as_current_span("grandkid-outlook-local"):
                        local_row = await conn.fetchrow(
                            _LOCAL_SQL, cz, race, gender, parent_income
                        )
                    if local_row is None:
                        # CZ matched (pooled/pooled) but this demographic cell is
                        # entirely absent — treat as not-enough-data, not an error.
                        local = LocalCell(available=False)
                    else:
                        rank = local_row["child_income_rank"]
                        local = LocalCell(
                            available=rank is not None,
                            child_income_rank=_f(rank),
                            child_percentile=_f(local_row["child_percentile"]),
                            n=_f(local_row["n"]),
                        )

                with tracer.start_as_current_span("grandkid-outlook-national"):
                    nat_row = await conn.fetchrow(
                        _NATIONAL_SQL, race, gender, parent_income
                    )
                if nat_row is not None:
                    nat_rank = nat_row["child_income_rank"]
                    national = NationalCell(
                        available=nat_rank is not None,
                        child_income_rank=_f(nat_rank),
                        child_percentile=_f(nat_row["child_percentile"]),
                        total_n=_f(nat_row["total_n"]),
                    )
        except Exception as exc:  # noqa: BLE001
            logger.exception("grandkid-outlook query failed")
            span.record_exception(exc)
            # Honest degraded response rather than a fabricated number.
            scope_label = (
                f"the {cz_name} commuting zone" if cz_name else "the United States"
            )
            return GrandkidOutlookResponse(
                race=race,
                gender=gender,
                parent_income_level=parent_income,
                parent_percentile=parent_percentile,
                resolved=cz is not None,
                cz_name=cz_name,
                scope_label=scope_label,
                local=None,
                national=NationalCell(available=False),
                note="Not enough data is available for this group.",
            )

        resolved = cz is not None
        scope_label = (
            f"the {cz_name} commuting zone" if resolved and cz_name else "the United States"
        )

        note = _build_note(
            parent_percentile=parent_percentile,
            scope_label=scope_label,
            local=local,
            national=national,
        )

        span.set_attribute("grandkid_outlook.resolved", resolved)
        span.set_attribute(
            "grandkid_outlook.local_available", bool(local and local.available)
        )
        span.set_attribute("grandkid_outlook.national_available", national.available)

        return GrandkidOutlookResponse(
            race=race,
            gender=gender,
            parent_income_level=parent_income,
            parent_percentile=parent_percentile,
            resolved=resolved,
            cz_name=cz_name if resolved else None,
            scope_label=scope_label,
            local=local,
            national=national,
            note=note,
        )
