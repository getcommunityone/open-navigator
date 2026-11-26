"""Organization page data (#1015): one organization by master_org_id.

Reads the small company satellites first (``mdm_organization_short_term_rental``, ``mdm_organization_data_center``),
which are on every serving copy, then the full ``mdm_organization`` row where that table exists (the local
warehouse; the hosted copy omits it for size). For a short-term rental platform it also lists where the company is
named (``short_term_rental_company_mention``), newest first, each with its verbatim passage.
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
        return OrganizationProfile(
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
        )
