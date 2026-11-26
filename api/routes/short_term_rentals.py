"""Short-term rental platform companies and where they are named (#1015).

Reads ``short_term_rental_company_mention`` (one row per company x meeting / decision, verbatim evidence) and
``mdm_organization_short_term_rental`` (the companies, each a master organization). Counts are distinct meetings
and decisions; nothing is estimated.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/api/short-term-rentals", tags=["short-term-rentals"])
tracer = trace.get_tracer(__name__)


class CompanyMention(BaseModel):
    mention_kind: str
    title: Optional[str] = None
    # Bare ISO date (YYYY-MM-DD) or None.
    date: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    state_code: Optional[str] = None
    url: Optional[str] = None
    # Verbatim passage with the matched words in <mark>; render with highlightSnippet, never as raw HTML.
    evidence: Optional[str] = None


class PlatformCompany(BaseModel):
    master_org_id: str
    company_key: str
    company_name: str
    aliases: List[str] = []
    website_url: Optional[str] = None
    meetings: int
    decisions: int
    newest: Optional[CompanyMention] = None


class PlatformCompanies(BaseModel):
    companies: List[PlatformCompany]


_COMPANIES_SQL = """
    WITH m AS (
        SELECT * FROM short_term_rental_company_mention
        WHERE ($1::text IS NULL OR state_code = $1::text)
    ),
    counts AS (
        SELECT master_org_id,
               count(*) FILTER (WHERE mention_kind = 'meeting')  AS meetings,
               count(*) FILTER (WHERE mention_kind = 'decision') AS decisions
        FROM m GROUP BY master_org_id
    ),
    newest AS (
        SELECT DISTINCT ON (master_org_id) *
        FROM m
        ORDER BY master_org_id, event_date DESC NULLS LAST, mention_kind DESC
    )
    SELECT c.master_org_id, c.company_key, c.company_name, c.aliases, c.website_url,
           coalesce(k.meetings, 0) AS meetings, coalesce(k.decisions, 0) AS decisions,
           n.mention_kind, n.title, n.event_date, n.jurisdiction_name, n.state_code, n.url, n.evidence
    FROM mdm_organization_short_term_rental c
    LEFT JOIN counts k ON k.master_org_id = c.master_org_id
    LEFT JOIN newest n ON n.master_org_id = c.master_org_id
    ORDER BY coalesce(k.meetings, 0) + coalesce(k.decisions, 0) DESC, c.company_name
"""


@router.get("/companies", response_model=PlatformCompanies)
async def platform_companies(
    state: Optional[str] = Query(None, description="Optional 2-letter state code."),
) -> PlatformCompanies:
    """Each short-term rental platform company with the number of meetings and decisions that name it, and its
    newest mention (verbatim). A company with no mention in scope has zero counts and no newest."""
    with tracer.start_as_current_span("short-term-rentals.companies") as span:
        state_code = state.strip().upper() if state and state.strip() else None
        span.set_attribute("str.state", state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(_COMPANIES_SQL, state_code)
        except Exception as exc:  # noqa: BLE001
            logger.exception("short-term rental companies failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="Companies are unavailable right now.") from exc
        span.set_attribute("str.companies", len(rows))
        return PlatformCompanies(
            companies=[
                PlatformCompany(
                    master_org_id=r["master_org_id"],
                    company_key=r["company_key"],
                    company_name=r["company_name"],
                    aliases=list(r["aliases"] or []),
                    website_url=r["website_url"],
                    meetings=int(r["meetings"]),
                    decisions=int(r["decisions"]),
                    newest=(
                        CompanyMention(
                            mention_kind=r["mention_kind"],
                            title=r["title"],
                            date=r["event_date"].isoformat() if r["event_date"] else None,
                            jurisdiction_name=r["jurisdiction_name"],
                            state_code=r["state_code"],
                            url=r["url"],
                            evidence=r["evidence"],
                        )
                        if r["mention_kind"]
                        else None
                    ),
                )
                for r in rows
            ]
        )
