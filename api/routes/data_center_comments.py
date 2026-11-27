"""Comment-level data-center metrics from our own transcripts (#1233, epic #1232).

``GET /api/data-centers/comment-metrics?year=2026&state=AL&city=`` returns the free numbers
that ``public.data_center_comment`` (dbt) supports: how many public comments, at how many local
governments and meetings, the concerns they raise (multi-label), the companies and public
figures they name, how many mention AI, how speakers describe themselves, the places they
name, and data-center mentions per meeting by quarter.

Metrics that need a per-comment stance (opposed / in favor / question) are returned as
``null`` with a reason: stance needs the classifier pass that is on hold (epic #1232, phase 2).
Nothing is defaulted to 0 or invented (CLAUDE.md, No Fabricated Data). The response echoes the
applied scope so the UI label matches the data (CLAUDE.md, scope label rule).

All shaping lives in dbt; this route only counts rows of the served marts.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.data_centers import JobClaimScope, build_scope
from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/data-centers", tags=["data-centers"])
tracer = trace.get_tracer(__name__)

STANCE_REASON = (
    "Needs a per-comment stance (opposed / in favor / question). That classifier pass is on hold "
    "by the owner (epic #1232, phase 2); until it runs, this number is unknown."
)
BASIS = (
    "Public comments segmented from our own meeting captions (self-introductions and the chair calling "
    "speakers), kept when the speaker isn't staff or the applicant and the comment is about a data center. "
    "Concerns, companies, people, AI and roles are keyword matches (dbt seeds), not a model's reading."
)


class CountItem(BaseModel):
    key: str
    label: str
    count: int
    share: float | None = Field(None, description="count / comments; null when there are no comments.")


class QuarterItem(BaseModel):
    quarter: str = Field(..., description="e.g. '2026-Q1' (a string, not a number).")
    meetings_with_mention: int = Field(..., description="Meetings whose captions say 'data center'.")
    mention_passages: int = Field(..., description="3-minute caption passages that say it.")
    passages_per_meeting: float | None
    comments: int = Field(..., description="Data-center public comments segmented in those meetings.")


class CommentMetricsResponse(BaseModel):
    year: str | None = Field(None, description="Calendar year filter as a string; null for all years.")
    scope: JobClaimScope
    comments: int
    governments: int
    meetings: int
    meetings_segmented: int = Field(..., description="Meetings in scope with any segmented comment (all topics).")
    meetings_with_no_supporters: int | None = None
    no_supporters_reason: str = STANCE_REASON
    positions: dict[str, int] | None = None
    positions_reason: str = STANCE_REASON
    concerns: list[CountItem]
    multi_concern_share: float | None = Field(
        None, description="Share of comments raising 2+ concerns on the reference list."
    )
    companies: list[CountItem]
    people: list[CountItem]
    ai_mentions: CountItem | None
    roles: list[CountItem]
    places: list[CountItem] = Field(default_factory=list, description="Place kinds named (roads, schools, ...).")
    mentions_per_meeting_by_quarter: list[QuarterItem] = Field(
        ..., description="The trend since 2022-Q1 for the place scope; it ignores `year` on purpose (it is a trend)."
    )
    basis: str = BASIS


def _where(scope: JobClaimScope, year: int | None, alias: str = "") -> tuple[str, list[Any]]:
    a = f"{alias}." if alias else ""
    clauses: list[str] = []
    params: list[Any] = []
    if year is not None:
        params.append(year)
        n = len(params)
        # A range on the date (not extract(year ...)) so the (state_code, meeting_date) index applies.
        clauses.append(f"{a}meeting_date >= make_date(${n}, 1, 1) AND {a}meeting_date < make_date(${n} + 1, 1, 1)")
    if scope.state_code:
        params.append(scope.state_code)
        clauses.append(f"{a}state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        clauses.append(f"{a}jurisdiction_name ILIKE ${len(params)}")
    if scope.jurisdiction_id:
        params.append(scope.jurisdiction_id)
        clauses.append(f"{a}jurisdiction_id = ${len(params)}")
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def build_metric_queries(scope: JobClaimScope, year: int | None) -> dict[str, tuple[str, list[Any]]]:
    """SQL per metric block. Every query reads only served relations."""
    where, params = _where(scope, year)
    where_d, params_d = _where(scope, year, "d")
    totals = (
        "SELECT count(*) AS comments, count(DISTINCT jurisdiction_id) AS governments, "
        "count(DISTINCT video_id) AS meetings, "
        "count(*) FILTER (WHERE reference_concern_count >= 2) AS multi_concern, "
        "count(*) FILTER (WHERE mentions_ai) AS ai "
        f"FROM data_center_comment{where}"
    )
    unnest_sql = (
        "SELECT k AS key, count(*) AS n FROM data_center_comment, unnest({col}) AS k"
        f"{where} GROUP BY k ORDER BY n DESC, k"
    )
    places = (
        "SELECT p.place_kind AS key, count(DISTINCT p.data_center_comment_id) AS n "
        "FROM data_center_comment_place p JOIN data_center_comment d "
        f"ON d.data_center_comment_id = p.data_center_comment_id{where_d} GROUP BY 1 ORDER BY 2 DESC"
    )
    seg_where, seg_params = _where(scope, year)
    segmented = f"SELECT count(*) AS n FROM segmented_meeting{seg_where}"
    q_where, q_params = _where(scope, None)
    q_extra = " AND " if q_where else " WHERE "
    quarters = (
        "WITH m AS (SELECT video_id, meeting_date FROM data_center_meeting_mention"
        f"{q_where}{q_extra}meeting_date >= DATE '2022-01-01'), "
        "q AS (SELECT to_char(meeting_date, 'YYYY') || '-Q' || extract(quarter FROM meeting_date)::int AS quarter, "
        "count(DISTINCT video_id) AS meetings, count(*) AS passages FROM m GROUP BY 1), "
        "c AS (SELECT to_char(meeting_date, 'YYYY') || '-Q' || extract(quarter FROM meeting_date)::int AS quarter, "
        f"count(*) AS comments FROM data_center_comment{q_where}{q_extra}meeting_date >= DATE '2022-01-01' GROUP BY 1) "
        "SELECT q.quarter, q.meetings, q.passages, coalesce(c.comments, 0) AS comments "
        "FROM q LEFT JOIN c USING (quarter) ORDER BY q.quarter"
    )
    return {
        "totals": (totals, params),
        "concerns": (unnest_sql.format(col="concern_keys"), params),
        "companies": (unnest_sql.format(col="company_keys"), params),
        "people": (unnest_sql.format(col="person_keys"), params),
        "roles": (unnest_sql.format(col="role_keys"), params),
        "places": (places, params_d),
        "segmented": (segmented, seg_params),
        "quarters": (quarters, q_params),
    }


# Labels mirror the dbt seeds (comment_concern_terms, comment_entity_terms, comment_role_terms);
# an unknown key falls back to the key itself, never to an invented label.
CONCERN_LABELS = {
    "water_use": "Water use", "quality_of_life": "Quality of life", "lack_of_transparency": "Lack of transparency",
    "company_distrust": "Company distrust", "rushed_review": "Rushed review",
    "limited_community_benefit": "Limited community benefit", "few_jobs": "Few jobs",
    "taxpayer_subsidies": "Taxpayer subsidies", "community_character": "Community character",
    "farmland_wildlife_loss": "Farmland / wildlife loss", "property_rights": "Property rights",
    "energy_costs_grid": "Electricity costs / grid",
}
ENTITY_LABELS = {
    "google": "Google / Alphabet", "amazon": "Amazon / AWS", "meta": "Meta / Facebook", "microsoft": "Microsoft",
    "openai": "OpenAI / ChatGPT", "xai": "xAI / Grok", "anthropic": "Anthropic / Claude", "nvidia": "Nvidia",
    "oracle": "Oracle", "apple": "Apple", "tesla": "Tesla", "blackstone_qts": "Blackstone / QTS",
    "coreweave": "CoreWeave", "elon_musk": "Elon Musk", "sam_altman": "Sam Altman", "peter_thiel": "Peter Thiel",
    "mark_zuckerberg": "Mark Zuckerberg", "jeff_bezos": "Jeff Bezos", "bill_gates": "Bill Gates",
    "kevin_oleary": "Kevin O'Leary", "jensen_huang": "Jensen Huang", "larry_ellison": "Larry Ellison",
    "sundar_pichai": "Sundar Pichai", "satya_nadella": "Satya Nadella",
}
ROLE_LABELS = {
    "resident": "Resident", "property_owner": "Property owner", "union_worker": "Union worker",
    "business": "Business owner / chamber", "farmer": "Farmer", "advocacy_group": "Advocacy or community group",
    "elected_official": "Elected official",
}
PLACE_LABELS = {
    "road": "Roads and routes", "school": "Schools", "county": "Counties and townships",
    "neighborhood": "Neighborhoods", "district": "Districts and wards", "site": "Named sites",
    "jurisdiction": "Towns and cities", "project": "Tracked data center projects",
}


def _items(rows: list[Any], labels: dict[str, str], total: int) -> list[CountItem]:
    return [
        CountItem(
            key=r["key"],
            label=labels.get(r["key"], r["key"]),
            count=int(r["n"]),
            share=round(int(r["n"]) / total, 4) if total else None,
        )
        for r in rows
    ]


def shape_response(
    year: int | None, scope: JobClaimScope, results: dict[str, list[Any]]
) -> CommentMetricsResponse:
    t = results["totals"][0] if results["totals"] else {}
    total = int(t.get("comments") or 0)
    quarters = [
        QuarterItem(
            quarter=r["quarter"],
            meetings_with_mention=int(r["meetings"]),
            mention_passages=int(r["passages"]),
            passages_per_meeting=round(int(r["passages"]) / int(r["meetings"]), 2) if r["meetings"] else None,
            comments=int(r["comments"]),
        )
        for r in results["quarters"]
    ]
    return CommentMetricsResponse(
        year=str(year) if year is not None else None,
        scope=scope,
        comments=total,
        governments=int(t.get("governments") or 0),
        meetings=int(t.get("meetings") or 0),
        meetings_segmented=int(results["segmented"][0]["n"]) if results["segmented"] else 0,
        concerns=_items(results["concerns"], CONCERN_LABELS, total),
        multi_concern_share=round(int(t["multi_concern"]) / total, 4) if total else None,
        companies=_items(results["companies"], ENTITY_LABELS, total),
        people=_items(results["people"], ENTITY_LABELS, total),
        ai_mentions=(
            CountItem(key="ai", label="Any mention of AI", count=int(t["ai"]), share=round(int(t["ai"]) / total, 4))
            if total
            else None
        ),
        roles=_items(results["roles"], ROLE_LABELS, total),
        places=_items(results["places"], PLACE_LABELS, total),
        mentions_per_meeting_by_quarter=quarters,
    )


@router.get("/comment-metrics", response_model=CommentMetricsResponse)
async def data_center_comment_metrics(
    year: int = Query(2026, ge=0, le=2100, description="Meeting year (default 2026); 0 for all years."),
    state: str | None = Query(None, description="2-letter code or full state name."),
    city: str | None = Query(None, description="City / jurisdiction name (substring)."),
    jurisdiction_id: str | None = Query(None),
) -> CommentMetricsResponse:
    scope = build_scope(state, city, jurisdiction_id)
    year_filter = year or None
    queries = build_metric_queries(scope, year_filter)
    with tracer.start_as_current_span("data_center_comment_metrics") as span:
        span.set_attribute("scope.level", scope.level)
        pool = await get_db_pool()
        results: dict[str, list[Any]] = {}
        try:
            async with pool.acquire() as conn:
                for name, (sql, params) in queries.items():
                    results[name] = [dict(r) for r in await conn.fetch(sql, *params)]
        except asyncpg.UndefinedTableError as exc:
            # The marts are new; before the first dbt build there is nothing to count.
            logger.warning("comment-metrics: {}", exc)
            raise HTTPException(status_code=503, detail="Comment-level data isn't built yet.") from exc
    return shape_response(year_filter, scope, results)
