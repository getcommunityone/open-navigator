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

from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from opentelemetry import trace

from api.routes.search_postgres import STATE_NAME_TO_CODE, get_db_pool

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
