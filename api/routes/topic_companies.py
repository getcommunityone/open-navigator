"""Companies named for a topic (#1052): data centers, short-term rentals, license-plate readers, guns.

Reads ``topic_company`` (the companies each curated topic names) and ``topic_company_mention`` (one row per company x
meeting / decision, with a verbatim excerpt). Counts are distinct meetings and decisions in scope; nothing is estimated.
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.search_postgres import get_db_pool
from api.privacy_redaction import TEXT_FIELDS, redact_response

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)


class TopicCompanyMention(BaseModel):
    mention_kind: str
    title: str | None = None
    date: str | None = Field(None, description="Bare ISO date (YYYY-MM-DD) or null.")
    jurisdiction_name: str | None = None
    state_code: str | None = None
    url: str | None = None
    evidence: str | None = Field(
        None, description="Verbatim excerpt with the matched words in <mark>; render with highlightSnippet."
    )


class TopicCompany(BaseModel):
    company_key: str
    company_name: str
    aliases: list[str] = []
    website_url: str | None = None
    master_org_id: str | None = Field(None, description="The organization page id, when the company is in MDM.")
    meetings: int
    decisions: int
    newest: TopicCompanyMention | None = None


class TopicCompaniesScope(BaseModel):
    level: str
    state_code: str | None = None
    city: str | None = None


class TopicCompanies(BaseModel):
    topic_query_id: str
    scope: TopicCompaniesScope
    companies: list[TopicCompany]


def build_companies_query(query_id: str, state_code: str | None, city: str | None) -> tuple[str, list]:
    """SQL and params: every company of the topic, with its counts and newest mention in scope (busiest first)."""
    params: list = [query_id, state_code, f"%{city}%" if city else None]
    sql = """
    WITH c AS (SELECT * FROM topic_company WHERE topic_query_id = $1::text),
    m AS (
        SELECT x.* FROM topic_company_mention x
        JOIN c ON c.topic_company_id = x.topic_company_id
        WHERE ($2::text IS NULL OR x.state_code = $2::text)
          AND ($3::text IS NULL OR x.jurisdiction_name ILIKE $3::text)
    ),
    counts AS (
        SELECT topic_company_id,
               count(*) FILTER (WHERE mention_kind = 'meeting')  AS meetings,
               count(*) FILTER (WHERE mention_kind = 'decision') AS decisions
        FROM m GROUP BY topic_company_id
    ),
    newest AS (
        SELECT DISTINCT ON (topic_company_id) *
        FROM m ORDER BY topic_company_id, event_date DESC NULLS LAST, mention_kind DESC
    )
    SELECT c.company_key, c.company_name, c.aliases, c.website_url, c.master_org_id,
           coalesce(k.meetings, 0) AS meetings, coalesce(k.decisions, 0) AS decisions,
           n.mention_kind, n.title, n.event_date, n.jurisdiction_name, n.state_code, n.url, n.evidence
    FROM c
    LEFT JOIN counts k ON k.topic_company_id = c.topic_company_id
    LEFT JOIN newest n ON n.topic_company_id = c.topic_company_id
    ORDER BY coalesce(k.meetings, 0) + coalesce(k.decisions, 0) DESC, c.company_name
    """
    return sql, params


@router.get("/{query_id}/companies", response_model=TopicCompanies)
async def topic_companies(
    query_id: str,
    state: str | None = Query(None, description="Optional 2-letter state code."),
    city: str | None = Query(None, description="Optional city; case-insensitive substring of the place name."),
) -> TopicCompanies:
    """Each company a topic names, with the meetings and decisions that name it in scope and its newest mention
    (verbatim). A company with no mention in scope has zero counts and no newest; an unknown topic returns none.

    Example:
        GET /api/topics/guns/companies?state=AL
    """
    qid = query_id.strip().lower()
    state_code = state.strip().upper() if state and state.strip() else None
    city_clean = city.strip() if city and city.strip() else None
    scope = TopicCompaniesScope(
        level="city" if city_clean else ("state" if state_code else "national"), state_code=state_code, city=city_clean
    )
    with tracer.start_as_current_span("topics.companies") as span:
        span.set_attribute("topic_companies.topic", qid)
        span.set_attribute("topic_companies.scope_level", scope.level)
        sql, params = build_companies_query(qid, state_code, city_clean)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
        except asyncpg.exceptions.UndefinedTableError:
            span.set_attribute("topic_companies.relation_missing", True)
            return await redact_response(TopicCompanies(topic_query_id=qid, scope=scope, companies=[]), TEXT_FIELDS)
        except Exception as exc:
            logger.exception("topic companies failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="Companies are unavailable right now.") from exc
        span.set_attribute("topic_companies.companies", len(rows))
        return await redact_response(TopicCompanies(
            topic_query_id=qid,
            scope=scope,
            companies=[
                TopicCompany(
                    company_key=r["company_key"],
                    company_name=r["company_name"],
                    aliases=list(r["aliases"] or []),
                    website_url=r["website_url"],
                    master_org_id=r["master_org_id"],
                    meetings=int(r["meetings"]),
                    decisions=int(r["decisions"]),
                    newest=(
                        TopicCompanyMention(
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
            ],
        ), TEXT_FIELDS)
