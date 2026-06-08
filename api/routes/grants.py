"""
Grant-detail endpoint, backed by the nonprofit grant mart (public."grant").

Serves a single grant by its text PK (grant_id), which the /search grant results
link to (url=/grants/{grant_id}). The frontend grant detail page calls
GET /api/grants/{grant_id} (router prefix "/grants" + app-level "/api" prefix).

NOTE: `grant` is a SQL reserved word — it is ALWAYS double-quoted in SQL here.

Naming contract (CLAUDE.md): expose BOTH the 2-letter `*_state_code` and the full
`*_state` name for grantor and grantee. The full name is recovered in Python from
STATE_NAME_TO_CODE (reused from search_postgres) so the two never drift.

Calendar-year rule (CLAUDE.md): `tax_year` is an integer column in storage but is
serialized as a STRING at the JSON boundary (UI clients locale-format bare JSON
numbers, e.g. 2,024). Dollar amounts stay numeric.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from opentelemetry import trace

from api.routes.lenses import money_fmt
from api.routes.search_postgres import (
    STATE_NAME_TO_CODE,
    get_db_pool,
    normalize_state_input,
)

router = APIRouter(prefix="/grants", tags=["grants"])

tracer = trace.get_tracer(__name__)

# Reverse of STATE_NAME_TO_CODE: 2-letter code -> full state name, so a grant row
# (which carries only *_state_code) can expose the full `*_state` per the naming
# contract. Derived from the canonical dict so the two never drift.
_CODE_TO_STATE_NAME: Dict[str, str] = {
    code: name for name, code in STATE_NAME_TO_CODE.items()
}


def _state_name(state_code: Optional[str]) -> Optional[str]:
    """Full state name for a 2-letter code, or None if unknown/missing."""
    if not state_code:
        return None
    return _CODE_TO_STATE_NAME.get(state_code.upper())


class GrantDetail(BaseModel):
    """A single nonprofit grant (990 Schedule I grant line), keyed by grant_id."""
    grant_id: str

    # Grantor (the org making the grant).
    grantor_master_org_id: Optional[str] = None
    grantor_ein: Optional[str] = None
    grantor_name: Optional[str] = None
    grantor_state_code: Optional[str] = None
    grantor_state: Optional[str] = None
    grantor_city: Optional[str] = None

    # Grantee (the org receiving the grant).
    grantee_master_org_id: Optional[str] = None
    grantee_ein: Optional[str] = None
    grantee_name: Optional[str] = None
    grantee_state_code: Optional[str] = None
    grantee_state: Optional[str] = None
    grantee_city: Optional[str] = None
    grantee_zip: Optional[str] = None

    # Grant terms.
    irc_section: Optional[str] = None
    amount: Optional[int] = None  # cash grant (bigint), numeric on the wire
    noncash_assistance_amount: Optional[int] = None  # bigint, numeric on the wire
    valuation_method: Optional[str] = None
    noncash_description: Optional[str] = None
    purpose: Optional[str] = None

    # tax_year is an integer column but is serialized as a STRING (calendar-year rule).
    tax_year: Optional[str] = None
    source_url: Optional[str] = None


# Single grant row by its text PK. `grant` is reserved -> double-quoted.
_GRANT_SQL = """
    SELECT
        grant_id,
        grantor_master_org_id,
        grantor_ein,
        grantor_name,
        grantor_state_code,
        grantor_city_norm,
        grantee_master_org_id,
        grantee_ein,
        grantee_name,
        grantee_state_code,
        grantee_city,
        grantee_zip,
        irc_section,
        amount,
        noncash_assistance_amount,
        valuation_method,
        noncash_description,
        purpose,
        tax_year,
        source_url
    FROM "grant"
    WHERE grant_id = $1
"""


class TopGrant(BaseModel):
    """A single grant row for the homepage "Grants" card (largest by amount)."""
    grant_id: str
    grantor_name: Optional[str] = None
    grantee_name: Optional[str] = None
    amount: int
    amount_label: str  # compact $ (e.g. "$2.9M")
    jurisdiction_label: Optional[str] = None  # "Tuscaloosa, AL" from grantor geo
    # tax_year is an integer column but is serialized as a STRING (calendar-year rule).
    tax_year: Optional[str] = None
    url: str


class TopGrantsResponse(BaseModel):
    """Top grants by amount, scoped to a grantor geography, for the Grants card."""
    grants: List[TopGrant]
    location_label: str


def _jurisdiction_label(
    city_norm: Optional[str], state_code: Optional[str]
) -> Optional[str]:
    """
    Display label from a grantor's normalized city + 2-letter state.

    grantor_city_norm is lowercase normalized (e.g. "tuscaloosa"); title-case it.
    Returns "City, ST", state-only ("ST") if no city, or None if neither.
    """
    city = city_norm.strip() if city_norm else None
    state = state_code.strip().upper() if state_code else None
    if city and state:
        return f"{city.title()}, {state}"
    if state:
        return state
    if city:
        return city.title()
    return None


# Top grants by amount, scoped on GRANTOR geography. `grant` is reserved -> quoted.
# Mirrors the grantor-location scope of search_grants_pg (search_postgres.py).
@router.get("/top", response_model=TopGrantsResponse)
async def get_top_grants(
    state: Optional[str] = Query(None, description="2-letter code or full state name"),
    city: Optional[str] = Query(None, description="Grantor city"),
    jurisdiction_id: Optional[int] = Query(None, description="Grantor jurisdiction id"),
    limit: int = Query(6, description="Max grants (clamped 1..20)"),
) -> TopGrantsResponse:
    """
    Return the largest grants (by amount) for a grantor geography.

    Scope mirrors search_grants_pg's grantor-location filter exactly:
    jurisdiction_id (via the org bridge) wins; otherwise grantor_state_code and/or
    grantor_city_norm. Always requires amount IS NOT NULL AND amount > 0. Backs the
    homepage "Grants" card. Returns an empty list (never fabricated rows) when the
    scoped query finds nothing.
    """
    limit = max(1, min(20, limit))
    state_code = normalize_state_input(state)

    with tracer.start_as_current_span("grants-top") as span:
        span.set_attribute("grants.limit", limit)
        if jurisdiction_id:
            span.set_attribute("grants.jurisdiction_id", jurisdiction_id)
        if state_code:
            span.set_attribute("grants.state_code", state_code)
        if city:
            span.set_attribute("grants.city", city)

        # Scope label for the card header ("United States" when unscoped).
        if city and state_code:
            location_label = f"{city.strip().title()}, {state_code}"
        elif state_code:
            location_label = _state_name(state_code) or state_code
        elif city:
            location_label = city.strip().title()
        else:
            location_label = "United States"

        try:
            where_clauses: List[str] = []
            params: List[object] = []
            param_idx = 1

            # Grantor-location scope (mirrors search_grants_pg).
            if jurisdiction_id:
                where_clauses.append(
                    f"grantor_master_org_id IN ("
                    f"SELECT master_org_id FROM mdm_bridge_org_jurisdiction "
                    f"WHERE jurisdiction_id = ${param_idx})"
                )
                params.append(jurisdiction_id)
                param_idx += 1
            else:
                if state_code:
                    where_clauses.append(f"grantor_state_code = ${param_idx}")
                    params.append(state_code.upper())
                    param_idx += 1
                if city:
                    where_clauses.append(
                        f"lower(grantor_city_norm) = lower(${param_idx})"
                    )
                    params.append(city.strip())
                    param_idx += 1

            # Always: only real, positive amounts.
            where_clauses.append("amount IS NOT NULL AND amount > 0")
            where_sql = " AND ".join(where_clauses)

            sql = f"""
                SELECT
                    grant_id,
                    grantor_name,
                    grantee_name,
                    amount,
                    grantor_state_code,
                    grantor_city_norm,
                    tax_year
                FROM "grant"
                WHERE {where_sql}
                ORDER BY amount DESC NULLS LAST
                LIMIT ${param_idx}
            """
            params.append(limit)

            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("grants-top.query"):
                    rows = await conn.fetch(sql, *params)

            span.set_attribute("grants.row_count", len(rows))

            grants = [
                TopGrant(
                    grant_id=row["grant_id"],
                    grantor_name=row["grantor_name"],
                    grantee_name=row["grantee_name"],
                    amount=row["amount"],
                    amount_label=money_fmt(row["amount"]),
                    jurisdiction_label=_jurisdiction_label(
                        row["grantor_city_norm"], row["grantor_state_code"]
                    ),
                    tax_year=(
                        str(row["tax_year"])
                        if row["tax_year"] is not None
                        else None
                    ),
                    url=f"/grants/{row['grant_id']}",
                )
                for row in rows
            ]

            logger.info(
                "💰 Top grants ({}): {} row(s)", location_label, len(grants)
            )

            return TopGrantsResponse(grants=grants, location_label=location_label)

        except Exception as e:
            span.record_exception(e)
            logger.error("Top grants error ({}): {}", location_label, e)
            raise HTTPException(status_code=500, detail="Failed to load top grants")


@router.get("/{grant_id}", response_model=GrantDetail)
async def get_grant(grant_id: str) -> GrantDetail:
    """
    Return a single nonprofit grant by grant_id. 404 if no grant row matches.
    """
    with tracer.start_as_current_span("grant-detail") as span:
        span.set_attribute("grant.grant_id", grant_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("grant-detail.query-grant"):
                    row = await conn.fetchrow(_GRANT_SQL, grant_id)

            if row is None:
                span.set_attribute("grant.found", False)
                raise HTTPException(
                    status_code=404,
                    detail=f"No grant found for grant_id '{grant_id}'",
                )
            span.set_attribute("grant.found", True)

            tax_year = (
                str(row["tax_year"]) if row["tax_year"] is not None else None
            )

            logger.info(
                "💰 Grant detail {} ({} → {})",
                grant_id,
                row["grantor_name"] or "Unknown grantor",
                row["grantee_name"] or "Unknown grantee",
            )

            return GrantDetail(
                grant_id=row["grant_id"],
                grantor_master_org_id=row["grantor_master_org_id"],
                grantor_ein=row["grantor_ein"],
                grantor_name=row["grantor_name"],
                grantor_state_code=row["grantor_state_code"],
                grantor_state=_state_name(row["grantor_state_code"]),
                grantor_city=row["grantor_city_norm"],
                grantee_master_org_id=row["grantee_master_org_id"],
                grantee_ein=row["grantee_ein"],
                grantee_name=row["grantee_name"],
                grantee_state_code=row["grantee_state_code"],
                grantee_state=_state_name(row["grantee_state_code"]),
                grantee_city=row["grantee_city"],
                grantee_zip=row["grantee_zip"],
                irc_section=row["irc_section"],
                amount=row["amount"],
                noncash_assistance_amount=row["noncash_assistance_amount"],
                valuation_method=row["valuation_method"],
                noncash_description=row["noncash_description"],
                purpose=row["purpose"],
                tax_year=tax_year,
                source_url=row["source_url"],
            )

        except HTTPException:
            raise
        except Exception as e:
            span.record_exception(e)
            logger.error("Grant detail error for {}: {}", grant_id, e)
            raise HTTPException(status_code=500, detail="Failed to load grant detail")
