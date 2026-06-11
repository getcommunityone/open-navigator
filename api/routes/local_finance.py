"""
Local-government finance for the homepage "where your tax money goes" modal —
GET /api/local-finance.

Serves REAL U.S. Census Bureau / Tax Policy Center finance figures for the
government that best matches the requested state + (optional) city/county. Per
CLAUDE.md's no-fabricated-data rule, missing dollar figures pass through as JSON
null (never 0), and a missing city/county gracefully falls back to the state
row with `matched=false` rather than inventing a place.

Source: public.jurisdiction_finance (one row per government, latest fiscal year)
and public.jurisdiction_finance_category (tidy/long, one row per government ×
spending category). Both are resolved unqualified via the connection
search_path (public in dev / gold in prod), matching the other serving routes
(e.g. money_and_talk).

Resolution order: city → county → state. Each level tries an exact
case-insensitive name match first, then a tolerant prefix/suffix match to
absorb Census generic suffixes ("Tuscaloosa city", "<name> County"). The level
actually returned is reported in `level`, with `matched` distinguishing a real
city/county hit from a state fallback.

fiscal_year is serialized as a STRING (CLAUDE.md calendar-year wire rule:
integer in SQL, string in JSON).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool, normalize_state_input

router = APIRouter(prefix="/api/local-finance", tags=["local-finance"])
tracer = trace.get_tracer(__name__)

_SOURCE = (
    "U.S. Census Bureau, Annual Survey of State & Local Government Finances / "
    "Census of Governments (via the Tax Policy Center)"
)

# Wide-row columns we serve. fiscal_year is selected as-is (integer) and
# stringified at the wire boundary; dollar columns stay bigint -> int/None.
_FINANCE_COLS = """
    jurisdiction_finance_id,
    jurisdiction_name,
    gov_type,
    state_code,
    state,
    fiscal_year,
    population,
    total_taxes,
    property_tax,
    sales_tax,
    other_taxes,
    taxes_per_capita,
    total_expenditure,
    direct_expenditure
"""

# City lookup: exact case-insensitive match first, then a tolerant prefix match
# so "Tuscaloosa" absorbs a stored "Tuscaloosa city". Latest row wins on the
# off chance of duplicates.
_CITY_SQL = f"""
    SELECT {_FINANCE_COLS}
    FROM jurisdiction_finance
    WHERE gov_type = 'city'
      AND state_code = $1
      AND (lower(jurisdiction_name) = lower($2)
           OR jurisdiction_name ILIKE $2 || '%')
    ORDER BY (lower(jurisdiction_name) = lower($2)) DESC,
             fiscal_year DESC
    LIMIT 1
"""

# County lookup: exact match first, then tolerant of a trailing " County".
_COUNTY_SQL = f"""
    SELECT {_FINANCE_COLS}
    FROM jurisdiction_finance
    WHERE gov_type = 'county'
      AND state_code = $1
      AND (lower(jurisdiction_name) = lower($2)
           OR jurisdiction_name ILIKE $2 || '%'
           OR jurisdiction_name ILIKE $2 || ' County%')
    ORDER BY (lower(jurisdiction_name) = lower($2)) DESC,
             fiscal_year DESC
    LIMIT 1
"""

# State fallback: clean single-row lookup.
_STATE_SQL = f"""
    SELECT {_FINANCE_COLS}
    FROM jurisdiction_finance
    WHERE gov_type = 'state'
      AND state_code = $1
    ORDER BY fiscal_year DESC
    LIMIT 1
"""

# Last-resort fallback: state-level governments like Washington, DC are stored
# as a single non-'state' row (DC's is gov_type='city'), so the state lookup
# above misses them. Fall back to the largest single government for the state so
# these resolve to real data instead of 404ing. Only reached when city, county,
# AND state lookups all came up empty, so it never overrides a real state row.
_ANY_SQL = f"""
    SELECT {_FINANCE_COLS}
    FROM jurisdiction_finance
    WHERE state_code = $1
    ORDER BY direct_expenditure DESC NULLS LAST, fiscal_year DESC
    LIMIT 1
"""

# Spending categories for the matched government, sorted by amount desc.
# amount is NOT NULL in the mart, but we drop any NULL defensively at the model
# layer rather than fabricate a 0.
_CATEGORY_SQL = """
    SELECT category, amount, share_pct
    FROM jurisdiction_finance_category
    WHERE jurisdiction_finance_id = $1
      AND amount IS NOT NULL
    ORDER BY amount DESC
"""


class FinanceCategory(BaseModel):
    category: str
    amount: int  # whole dollars
    share_pct: Optional[float] = None  # mart's own % of direct_expenditure


class LocalFinanceResponse(BaseModel):
    level: str  # "city" | "county" | "state"
    matched: bool  # False when a requested city/county fell back to state
    jurisdiction_name: str
    gov_type: str
    state_code: str
    state: str
    fiscal_year: str  # STRING at the wire
    population: Optional[int] = None
    total_taxes: Optional[int] = None
    property_tax: Optional[int] = None
    sales_tax: Optional[int] = None
    other_taxes: Optional[int] = None
    taxes_per_capita: Optional[float] = None
    total_expenditure: Optional[int] = None
    direct_expenditure: Optional[int] = None  # the pie denominator
    categories: List[FinanceCategory] = []
    source: str = _SOURCE
    note: str = ""


# ---------------------------------------------------------------------------
# Effective property-tax rate (ACS B25103 / B25077), for the money modal's
# personal "your tax bill" estimate. Grain: Census place + county (no state
# row), so resolution is place → county only; a miss is a 404 (the frontend
# simply hides the card — no fabricated rate). effective_property_tax_rate is
# median_real_estate_taxes_paid / median_home_value, both REAL ACS medians.
# ---------------------------------------------------------------------------
_PROPTAX_SOURCE = (
    "U.S. Census Bureau, American Community Survey (ACS) 5-year — median real "
    "estate taxes paid (B25103) ÷ median home value (B25077)"
)

_PROPTAX_COLS = """
    name,
    state_code,
    state,
    geography_type,
    acs_vintage_year,
    median_real_estate_taxes_paid,
    median_home_value,
    effective_property_tax_rate
"""

# Place (city) lookup: exact name-stem match first, then tolerant of the stored
# Census suffix ("Tuscaloosa city, Alabama"). Only rows with a real rate.
_PROPTAX_PLACE_SQL = f"""
    SELECT {_PROPTAX_COLS}
    FROM jurisdiction_property_tax_rate
    WHERE geography_type = 'place'
      AND state_code = $1
      AND effective_property_tax_rate IS NOT NULL
      AND (lower(name) = lower($2)
           OR name ILIKE $2 || ' city,%'
           OR name ILIKE $2 || '%')
    ORDER BY (name ILIKE $2 || ' city,%') DESC,
             median_home_value DESC NULLS LAST
    LIMIT 1
"""

# County lookup: exact stem, then tolerant of a trailing " County".
_PROPTAX_COUNTY_SQL = f"""
    SELECT {_PROPTAX_COLS}
    FROM jurisdiction_property_tax_rate
    WHERE geography_type = 'county'
      AND state_code = $1
      AND effective_property_tax_rate IS NOT NULL
      AND (lower(name) = lower($2)
           OR name ILIKE $2 || ' County,%'
           OR name ILIKE $2 || '%')
    ORDER BY (name ILIKE $2 || ' County,%') DESC,
             median_home_value DESC NULLS LAST
    LIMIT 1
"""


class PropertyTaxRateResponse(BaseModel):
    level: str  # "place" | "county"
    matched: bool  # always True on a 200 (a miss is a 404, never a placeholder)
    jurisdiction_name: str
    state_code: str
    state: str
    acs_vintage_year: Optional[int] = None
    # Effective rate as a fraction (e.g. 0.004746 = 0.47%); multiply home value.
    effective_property_tax_rate: Optional[float] = None
    median_home_value: Optional[int] = None  # ACS median, a sensible slider default
    median_real_estate_taxes_paid: Optional[int] = None
    source: str = _PROPTAX_SOURCE
    note: str = ""


@router.get("/property-tax-rate", response_model=PropertyTaxRateResponse)
async def get_property_tax_rate(
    state: str = Query(..., description="2-letter state code (full names accepted)."),
    city: Optional[str] = Query(None, description="City name (Census place)."),
    county: Optional[str] = Query(None, description="County name."),
) -> PropertyTaxRateResponse:
    """Real effective property-tax rate + median home value for the best place/county.

    Resolution: place (city) → county. Used to estimate a household property-tax
    bill from a home value. No state-level row exists, so a state-only request
    (or an unmatched city/county) is a 404 — the caller hides the estimate
    rather than show an invented rate.
    """
    state_code = normalize_state_input(state)
    if not state_code:
        raise HTTPException(status_code=400, detail="A valid state code is required.")

    with tracer.start_as_current_span("property-tax-rate") as span:
        span.set_attribute("property_tax_rate.state_code", state_code)
        span.set_attribute("property_tax_rate.city", city or "")
        span.set_attribute("property_tax_rate.county", county or "")

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = None
                level = "county"

                if city:
                    with tracer.start_as_current_span("property-tax-rate-place"):
                        row = await conn.fetchrow(_PROPTAX_PLACE_SQL, state_code, city)
                    if row is not None:
                        level = "place"

                if row is None and county:
                    with tracer.start_as_current_span("property-tax-rate-county"):
                        row = await conn.fetchrow(
                            _PROPTAX_COUNTY_SQL, state_code, county
                        )
                    if row is not None:
                        level = "county"

                if row is None:
                    span.set_attribute("property_tax_rate.found", False)
                    raise HTTPException(
                        status_code=404,
                        detail="No property-tax rate available for this location.",
                    )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("property-tax-rate query failed")
            span.record_exception(exc)
            raise HTTPException(
                status_code=500, detail="Failed to load property-tax rate."
            ) from exc

        vintage = _int_or_none(row["acs_vintage_year"])
        note = (
            f"Effective rate is the ACS median real-estate tax ÷ median home value"
            + (f" (ACS {vintage} 5-year)." if vintage else ".")
        )
        span.set_attribute("property_tax_rate.level", level)

        return PropertyTaxRateResponse(
            level=level,
            matched=True,
            jurisdiction_name=row["name"],
            state_code=row["state_code"],
            state=row["state"],
            acs_vintage_year=vintage,
            effective_property_tax_rate=_float_or_none(
                row["effective_property_tax_rate"]
            ),
            median_home_value=_int_or_none(row["median_home_value"]),
            median_real_estate_taxes_paid=_int_or_none(
                row["median_real_estate_taxes_paid"]
            ),
            source=_PROPTAX_SOURCE,
            note=note,
        )


# ---------------------------------------------------------------------------
# Combined state + average-local sales-tax rate (Tax Foundation), for the money
# modal's "your bill" sales-tax line. Grain: state. Real percentages, never a
# hard-coded rate.
# ---------------------------------------------------------------------------
_SALESTAX_SQL = """
    SELECT state_code, state, state_sales_tax_rate_pct,
           avg_local_sales_tax_rate_pct, combined_sales_tax_rate_pct,
           as_of_date, source
    FROM state_sales_tax_rate
    WHERE state_code = $1
    ORDER BY as_of_date DESC NULLS LAST
    LIMIT 1
"""


class SalesTaxRateResponse(BaseModel):
    state_code: str
    state: str
    # Percentages (9.46 = 9.46%), as published.
    state_sales_tax_rate_pct: Optional[float] = None
    avg_local_sales_tax_rate_pct: Optional[float] = None
    combined_sales_tax_rate_pct: Optional[float] = None
    as_of_date: Optional[str] = None
    source: str = "Tax Foundation, State & Local Sales Tax Rates"


@router.get("/sales-tax-rate", response_model=SalesTaxRateResponse)
async def get_sales_tax_rate(
    state: str = Query(..., description="2-letter state code (full names accepted)."),
) -> SalesTaxRateResponse:
    """Real combined state + average-local sales-tax rate for a state.

    The combined rate is the state's own rate plus the population-weighted
    average of local rates (Tax Foundation). Applied to taxable spending in the
    money modal — a real percentage, not the prototype's invented 4%.
    """
    state_code = normalize_state_input(state)
    if not state_code:
        raise HTTPException(status_code=400, detail="A valid state code is required.")

    with tracer.start_as_current_span("sales-tax-rate") as span:
        span.set_attribute("sales_tax_rate.state_code", state_code)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(_SALESTAX_SQL, state_code)
        except Exception as exc:  # noqa: BLE001
            logger.exception("sales-tax-rate query failed")
            span.record_exception(exc)
            raise HTTPException(
                status_code=500, detail="Failed to load sales-tax rate."
            ) from exc

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No sales-tax rate available for state '{state_code}'.",
            )

        as_of = row["as_of_date"]
        return SalesTaxRateResponse(
            state_code=row["state_code"],
            state=row["state"],
            state_sales_tax_rate_pct=_float_or_none(row["state_sales_tax_rate_pct"]),
            avg_local_sales_tax_rate_pct=_float_or_none(
                row["avg_local_sales_tax_rate_pct"]
            ),
            combined_sales_tax_rate_pct=_float_or_none(
                row["combined_sales_tax_rate_pct"]
            ),
            as_of_date=as_of.isoformat() if as_of is not None else None,
            source=row["source"] or "Tax Foundation, State & Local Sales Tax Rates",
        )


def _int_or_none(value: object) -> Optional[int]:
    """bigint -> int, pass NULL through (never fabricate 0)."""
    return None if value is None else int(value)


def _float_or_none(value: object) -> Optional[float]:
    """numeric (asyncpg Decimal) -> float, pass NULL through."""
    return None if value is None else float(value)


@router.get("", response_model=LocalFinanceResponse)
async def get_local_finance(
    state: str = Query(..., description="2-letter state code (full names accepted)."),
    city: Optional[str] = Query(None, description="City name (Census place)."),
    county: Optional[str] = Query(None, description="County name."),
) -> LocalFinanceResponse:
    """Return real finance figures for the best-matching government.

    Resolution: city → county → state. A requested city/county that isn't found
    falls back to the state row with `matched=false`; nothing found even at
    state level is a 404 (no placeholder numbers).
    """
    state_code = normalize_state_input(state)
    if not state_code:
        raise HTTPException(status_code=400, detail="A valid state code is required.")

    with tracer.start_as_current_span("local-finance") as span:
        span.set_attribute("local_finance.state_code", state_code)
        span.set_attribute("local_finance.city", city or "")
        span.set_attribute("local_finance.county", county or "")

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = None
                level = "state"
                matched = False

                if city:
                    with tracer.start_as_current_span("local-finance-city"):
                        row = await conn.fetchrow(_CITY_SQL, state_code, city)
                    if row is not None:
                        level, matched = "city", True

                if row is None and county:
                    with tracer.start_as_current_span("local-finance-county"):
                        row = await conn.fetchrow(_COUNTY_SQL, state_code, county)
                    if row is not None:
                        level, matched = "county", True

                if row is None:
                    with tracer.start_as_current_span("local-finance-state"):
                        row = await conn.fetchrow(_STATE_SQL, state_code)
                    # matched stays False here: either no city/county was asked
                    # for, or the requested one wasn't found and we fell back.
                    level = "state"

                if row is None:
                    # Catch state-level governments stored under a non-'state'
                    # gov_type (e.g. Washington, DC). matched stays False.
                    with tracer.start_as_current_span("local-finance-any"):
                        row = await conn.fetchrow(_ANY_SQL, state_code)
                    if row is not None:
                        level = row["gov_type"]

                if row is None:
                    span.set_attribute("local_finance.found", False)
                    raise HTTPException(
                        status_code=404,
                        detail=f"No finance data available for state '{state_code}'.",
                    )

                with tracer.start_as_current_span("local-finance-categories"):
                    cat_rows = await conn.fetch(
                        _CATEGORY_SQL, row["jurisdiction_finance_id"]
                    )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("local-finance query failed")
            span.record_exception(exc)
            raise HTTPException(
                status_code=500, detail="Failed to load local finance data."
            ) from exc

        categories = [
            FinanceCategory(
                category=c["category"],
                amount=int(c["amount"]),
                share_pct=(
                    round(float(c["share_pct"]), 1)
                    if c["share_pct"] is not None
                    else None
                ),
            )
            for c in cat_rows
            if c["amount"] is not None
        ]

        fiscal_year = row["fiscal_year"]
        note = (
            f"Latest available data: fiscal year {fiscal_year}. "
            "Figures are the government's own reported revenue and spending."
        )

        span.set_attribute("local_finance.level", level)
        span.set_attribute("local_finance.matched", matched)
        span.set_attribute("local_finance.category_count", len(categories))

        return LocalFinanceResponse(
            level=level,
            matched=matched,
            jurisdiction_name=row["jurisdiction_name"],
            gov_type=row["gov_type"],
            state_code=row["state_code"],
            state=row["state"],
            fiscal_year=str(fiscal_year),
            population=_int_or_none(row["population"]),
            total_taxes=_int_or_none(row["total_taxes"]),
            property_tax=_int_or_none(row["property_tax"]),
            sales_tax=_int_or_none(row["sales_tax"]),
            other_taxes=_int_or_none(row["other_taxes"]),
            taxes_per_capita=_float_or_none(row["taxes_per_capita"]),
            total_expenditure=_int_or_none(row["total_expenditure"]),
            direct_expenditure=_int_or_none(row["direct_expenditure"]),
            categories=categories,
            source=_SOURCE,
            note=note,
        )
