"""Organization page data (#1015): one organization by master_org_id.

Reads the small company satellites first (``mdm_organization_short_term_rental``, ``mdm_organization_data_center``),
which are on every serving copy, then the full ``mdm_organization`` row where that table exists (the local
warehouse; the hosted copy omits it for size). For a short-term rental platform it also lists where the company is
named (``short_term_rental_company_mention``), newest first, each with its verbatim passage.

``GET /api/organizations/{id}/funding`` (#1073) reads ``company_grant``: the IRS 990 Schedule I grants from the
foundations tied to the companies we track. ``funds`` is what the organization (the company, or the foundation itself)
granted, one entry per grantee; ``funded_by`` is which companies' foundations granted to it. Every dollar figure is a
SQL ``sum`` of the amounts the 990s report; when the table is missing both lists are empty.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool
from api.routes.short_term_rentals import CompanyMention
from api.privacy_redaction import TEXT_FIELDS, redact_response

router = APIRouter(prefix="/api/organizations", tags=["organizations"])
tracer = trace.get_tracer(__name__)


class OrgSource(BaseModel):
    url: str
    excerpt: str
    kind: Optional[str] = None


class OrganizationProfile(BaseModel):
    master_org_id: str
    name: str
    org_type: Optional[str] = None
    org_subtype: Optional[str] = None
    ein: Optional[str] = None
    city: Optional[str] = None
    state_code: Optional[str] = None
    website_url: Optional[str] = None
    first_seen_year: Optional[str] = None
    last_seen_year: Optional[str] = None
    # Registries / datasets the record was built from (mdm name_history), when the full master is available.
    record_sources: List[str] = []
    # Company detail: what kind of company, the brands it is named by, and where that comes from.
    company_roles: List[str] = []
    aliases: List[str] = []
    company_source: Optional[OrgSource] = None
    # Where it is named (short-term rental platforms today).
    mentions_total: int = 0
    meetings: int = 0
    decisions: int = 0
    mentions: List[CompanyMention] = []


async def _table_exists(conn: Any, name: str) -> bool:
    return bool(await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", name))


@router.get("/{master_org_id}", response_model=OrganizationProfile)
async def organization_profile(
    master_org_id: str = Path(..., min_length=1, max_length=64),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> OrganizationProfile:
    with tracer.start_as_current_span("organization.profile") as span:
        span.set_attribute("org.master_org_id", master_org_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                str_row = await conn.fetchrow(
                    "SELECT * FROM mdm_organization_short_term_rental WHERE master_org_id = $1", master_org_id
                ) if await _table_exists(conn, "mdm_organization_short_term_rental") else None
                dc_row = await conn.fetchrow(
                    "SELECT * FROM mdm_organization_data_center WHERE master_org_id = $1", master_org_id
                ) if await _table_exists(conn, "mdm_organization_data_center") else None
                org_row = await conn.fetchrow(
                    "SELECT * FROM mdm_organization WHERE master_org_id = $1", master_org_id
                ) if await _table_exists(conn, "mdm_organization") else None

                if not (str_row or dc_row or org_row):
                    raise HTTPException(status_code=404, detail="Organization not found.")

                counts = {"meetings": 0, "decisions": 0}
                mentions: List[Dict[str, Any]] = []
                if str_row and await _table_exists(conn, "short_term_rental_company_mention"):
                    for r in await conn.fetch(
                        "SELECT mention_kind, count(*) AS n FROM short_term_rental_company_mention "
                        "WHERE master_org_id = $1 GROUP BY mention_kind",
                        master_org_id,
                    ):
                        counts["meetings" if r["mention_kind"] == "meeting" else "decisions"] = int(r["n"])
                    mentions = [
                        dict(r)
                        for r in await conn.fetch(
                            "SELECT mention_kind, title, event_date, jurisdiction_name, state_code, url, evidence "
                            "FROM short_term_rental_company_mention WHERE master_org_id = $1 "
                            "ORDER BY event_date DESC NULLS LAST, mention_id LIMIT $2 OFFSET $3",
                            master_org_id, limit, offset,
                        )
                    ]
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("organization profile failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This organization is unavailable right now.") from exc

        company = str_row or dc_row
        org = dict(org_row) if org_row else {}
        history = org.get("name_history")
        if isinstance(history, str):  # the pool has no jsonb codec: JSONB arrives as text
            try:
                history = json.loads(history)
            except ValueError:
                history = []
        sources = sorted({s for h in (history or []) if isinstance(h, dict) for s in (h.get("sources") or [])})
        roles = sorted(set((str_row["roles"] if str_row else []) or []) | set((dc_row["roles"] if dc_row else []) or []))
        aliases = sorted(set((str_row["aliases"] if str_row else []) or []) | set((dc_row["aliases"] if dc_row else []) or []))
        name = org.get("org_name") or (company["company_name"] if company else master_org_id)
        if company:
            name = company["company_name"]  # the curated company name is the one people use
        return await redact_response(OrganizationProfile(
            master_org_id=master_org_id,
            name=name,
            org_type=org.get("org_type") or ("company" if company else None),
            org_subtype=org.get("org_subtype"),
            ein=org.get("ein"),
            city=(org.get("city_norm") or None),
            state_code=org.get("state_code"),
            website_url=(company["website_url"] if company and company["website_url"] else org.get("website")),
            first_seen_year=str(org["first_seen_year"]) if org.get("first_seen_year") else None,
            last_seen_year=str(org["last_seen_year"]) if org.get("last_seen_year") else None,
            record_sources=sources,
            company_roles=roles,
            aliases=aliases,
            company_source=OrgSource(url=company["source_url"], excerpt=company["source_excerpt"], kind=company["source_kind"]) if company else None,
            mentions_total=counts["meetings"] + counts["decisions"],
            meetings=counts["meetings"],
            decisions=counts["decisions"],
            mentions=[
                CompanyMention(
                    mention_kind=m["mention_kind"],
                    title=m["title"],
                    date=m["event_date"].isoformat() if m["event_date"] else None,
                    jurisdiction_name=m["jurisdiction_name"],
                    state_code=m["state_code"],
                    url=m["url"],
                    evidence=m["evidence"],
                )
                for m in mentions
            ],
        ), TEXT_FIELDS)


# ---------------------------------------------------------------------------------------------------------------
# Funding (#1073)
# ---------------------------------------------------------------------------------------------------------------

TOP_GRANTS = 5


class YearTotal(BaseModel):
    tax_year: Optional[str] = None  # a bare year goes over the wire as a string (CLAUDE.md, Calendar Years)
    amount: Optional[int] = None
    grants: int = 0


class GrantLine(BaseModel):
    grant_id: str
    amount: Optional[int] = None
    purpose: Optional[str] = None
    tax_year: Optional[str] = None
    source_url: Optional[str] = None


class FundsEntry(BaseModel):
    """One grantee of the organization's foundation(s)."""

    grantee_name: str
    grantee_ein: Optional[str] = None
    grantee_master_org_id: Optional[str] = None
    grantee_city: Optional[str] = None
    grantee_state_code: Optional[str] = None
    foundation_name: str
    foundation_ein: str
    total_amount: Optional[int] = None
    grants: int = 0
    by_year: List[YearTotal] = []
    top_grants: List[GrantLine] = []


class FundedByEntry(BaseModel):
    """One company whose foundation granted to the organization."""

    company_key: str
    company_name: str
    master_org_id: str
    foundation_name: str
    foundation_ein: str
    foundation_master_org_id: Optional[str] = None
    relationship: Optional[str] = None
    foundation_source_url: Optional[str] = None
    total_amount: Optional[int] = None
    grants: int = 0
    by_year: List[YearTotal] = []
    top_grants: List[GrantLine] = []


class OrganizationFunding(BaseModel):
    master_org_id: str
    # The foundation(s) behind ``funds`` and the page that ties each to the company.
    foundations: List[Dict[str, Optional[str]]] = []
    funds_total: Optional[int] = None
    funds_grants: int = 0
    funds_by_year: List[YearTotal] = []
    funds: List[FundsEntry] = []
    funded_by: List[FundedByEntry] = []


def _year(v: Any) -> Optional[str]:
    return str(int(v)) if v is not None else None


def _int(v: Any) -> Optional[int]:
    return int(v) if v is not None else None


# A grantee is the resolved master row when there is one, else the name + EIN as filed.
_GRANTEE_KEY = "coalesce(grantee_master_org_id, 'name:' || coalesce(grantee_ein, '') || '|' || upper(grantee_name))"
_FUNDS_WHERE = "(master_org_id = $1 OR foundation_master_org_id = $1)"


@router.get("/{master_org_id}/funding", response_model=OrganizationFunding)
async def organization_funding(
    master_org_id: str = Path(..., min_length=1, max_length=64),
    limit: int = Query(50, ge=1, le=200),
) -> OrganizationFunding:
    with tracer.start_as_current_span("organization.funding") as span:
        span.set_attribute("org.master_org_id", master_org_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                if not await _table_exists(conn, "company_grant"):
                    return OrganizationFunding(master_org_id=master_org_id)
                foundations = await conn.fetch(
                    "SELECT DISTINCT company_key, company_name, foundation_name, foundation_ein, "
                    "foundation_master_org_id, relationship, foundation_source_url "
                    f"FROM company_grant WHERE {_FUNDS_WHERE} ORDER BY foundation_name",
                    master_org_id,
                )
                funds_years = await conn.fetch(
                    "SELECT tax_year, sum(amount) AS amount, count(*) AS grants "
                    f"FROM company_grant WHERE {_FUNDS_WHERE} GROUP BY tax_year ORDER BY tax_year DESC NULLS LAST",
                    master_org_id,
                )
                funds_rows = await conn.fetch(
                    f"WITH g AS (SELECT {_GRANTEE_KEY} AS grantee_key, * FROM company_grant WHERE {_FUNDS_WHERE}), "
                    "t AS (SELECT grantee_key, sum(amount) AS total_amount, count(*) AS grants FROM g GROUP BY grantee_key "
                    "ORDER BY sum(amount) DESC NULLS LAST, grantee_key LIMIT $2), "
                    "latest AS (SELECT DISTINCT ON (grantee_key) grantee_key, grantee_name, grantee_ein, grantee_master_org_id, "
                    "grantee_city, grantee_state_code, foundation_name, foundation_ein FROM g "
                    "ORDER BY grantee_key, tax_year DESC NULLS LAST, grant_id) "
                    "SELECT t.grantee_key, t.total_amount, t.grants, l.grantee_name, l.grantee_ein, l.grantee_master_org_id, "
                    "l.grantee_city, l.grantee_state_code, l.foundation_name, l.foundation_ein "
                    "FROM t JOIN latest AS l USING (grantee_key) ORDER BY t.total_amount DESC NULLS LAST, t.grantee_key",
                    master_org_id, limit,
                )
                keys = [r["grantee_key"] for r in funds_rows]
                funds_by_year = await conn.fetch(
                    f"SELECT {_GRANTEE_KEY} AS grantee_key, tax_year, sum(amount) AS amount, count(*) AS grants "
                    f"FROM company_grant WHERE {_FUNDS_WHERE} AND {_GRANTEE_KEY} = ANY($2::text[]) "
                    "GROUP BY 1, 2 ORDER BY 1, 2 DESC NULLS LAST",
                    master_org_id, keys,
                ) if keys else []
                funds_top = await conn.fetch(
                    "SELECT grantee_key, grant_id, amount, purpose, tax_year, source_url FROM ("
                    f"SELECT {_GRANTEE_KEY} AS grantee_key, grant_id, amount, purpose, tax_year, source_url, "
                    f"row_number() OVER (PARTITION BY {_GRANTEE_KEY} ORDER BY amount DESC NULLS LAST, grant_id) AS rn "
                    f"FROM company_grant WHERE {_FUNDS_WHERE} AND {_GRANTEE_KEY} = ANY($2::text[])) AS x "
                    f"WHERE rn <= {TOP_GRANTS} ORDER BY grantee_key, rn",
                    master_org_id, keys,
                ) if keys else []

                funded_rows = await conn.fetch(
                    "SELECT company_key, company_name, master_org_id, foundation_name, foundation_ein, "
                    "foundation_master_org_id, relationship, foundation_source_url, "
                    "sum(amount) AS total_amount, count(*) AS grants "
                    "FROM company_grant WHERE grantee_master_org_id = $1 "
                    "GROUP BY 1, 2, 3, 4, 5, 6, 7, 8 ORDER BY sum(amount) DESC NULLS LAST, company_key",
                    master_org_id,
                )
                funded_by_year = await conn.fetch(
                    "SELECT foundation_ein, tax_year, sum(amount) AS amount, count(*) AS grants "
                    "FROM company_grant WHERE grantee_master_org_id = $1 GROUP BY 1, 2 ORDER BY 1, 2 DESC NULLS LAST",
                    master_org_id,
                ) if funded_rows else []
                funded_top = await conn.fetch(
                    "SELECT foundation_ein, grant_id, amount, purpose, tax_year, source_url FROM ("
                    "SELECT foundation_ein, grant_id, amount, purpose, tax_year, source_url, "
                    "row_number() OVER (PARTITION BY foundation_ein ORDER BY amount DESC NULLS LAST, grant_id) AS rn "
                    f"FROM company_grant WHERE grantee_master_org_id = $1) AS x WHERE rn <= {TOP_GRANTS} "
                    "ORDER BY foundation_ein, rn",
                    master_org_id,
                ) if funded_rows else []
        except Exception as exc:  # noqa: BLE001
            logger.exception("organization funding failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="Funding for this organization is unavailable right now.") from exc

        def years(rows: Any, key: str, value: Any) -> List[YearTotal]:
            return [
                YearTotal(tax_year=_year(r["tax_year"]), amount=_int(r["amount"]), grants=int(r["grants"]))
                for r in rows
                if r[key] == value
            ]

        def tops(rows: Any, key: str, value: Any) -> List[GrantLine]:
            return [
                GrantLine(
                    grant_id=r["grant_id"], amount=_int(r["amount"]), purpose=r["purpose"],
                    tax_year=_year(r["tax_year"]), source_url=r["source_url"],
                )
                for r in rows
                if r[key] == value
            ]

        funds_total_rows = [r for r in funds_years if r["amount"] is not None]
        span.set_attribute("org.funds", len(funds_rows))
        span.set_attribute("org.funded_by", len(funded_rows))
        return OrganizationFunding(
            master_org_id=master_org_id,
            foundations=[
                {k: f[k] for k in ("company_key", "company_name", "foundation_name", "foundation_ein",
                                   "foundation_master_org_id", "relationship", "foundation_source_url")}
                for f in foundations
            ],
            funds_total=sum(int(r["amount"]) for r in funds_total_rows) if funds_total_rows else None,
            funds_grants=sum(int(r["grants"]) for r in funds_years),
            funds_by_year=[
                YearTotal(tax_year=_year(r["tax_year"]), amount=_int(r["amount"]), grants=int(r["grants"]))
                for r in funds_years
            ],
            funds=[
                FundsEntry(
                    grantee_name=r["grantee_name"], grantee_ein=r["grantee_ein"],
                    grantee_master_org_id=r["grantee_master_org_id"], grantee_city=r["grantee_city"],
                    grantee_state_code=r["grantee_state_code"], foundation_name=r["foundation_name"],
                    foundation_ein=r["foundation_ein"], total_amount=_int(r["total_amount"]), grants=int(r["grants"]),
                    by_year=years(funds_by_year, "grantee_key", r["grantee_key"]),
                    top_grants=tops(funds_top, "grantee_key", r["grantee_key"]),
                )
                for r in funds_rows
            ],
            funded_by=[
                FundedByEntry(
                    company_key=r["company_key"], company_name=r["company_name"], master_org_id=r["master_org_id"],
                    foundation_name=r["foundation_name"], foundation_ein=r["foundation_ein"],
                    foundation_master_org_id=r["foundation_master_org_id"], relationship=r["relationship"],
                    foundation_source_url=r["foundation_source_url"], total_amount=_int(r["total_amount"]),
                    grants=int(r["grants"]),
                    by_year=years(funded_by_year, "foundation_ein", r["foundation_ein"]),
                    top_grants=tops(funded_top, "foundation_ein", r["foundation_ein"]),
                )
                for r in funded_rows
            ],
        )
