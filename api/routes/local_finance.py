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
