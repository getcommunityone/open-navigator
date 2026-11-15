"""
Data-center job claims, split by phase (issue #246, DC-1.1).

Backed by the dbt mart ``job_claim`` (published to ``public``): one row per
jobs claim a speaker made in a meeting, tagged ``construction`` or
``operations``. This route only reads the modeled relation; all extraction and
shaping lives in dbt.

``GET /api/data-centers/job-claims`` filters to ``project_type = 'data_center'``
and narrows by ``state`` (2-letter code, or a full name normalized to one),
``city`` (case-insensitive match on ``jurisdiction_name``) and/or
``jurisdiction_id`` (exact). The response echoes the applied filters as
``scope`` so the UI label always matches the data (CLAUDE.md, scope label rule).

Unknown values stay ``null``; nothing is defaulted to 0 (CLAUDE.md, No
Fabricated Data). When ``job_claim`` isn't in the database yet (the mart is
new), the route returns the scope with an empty ``items`` list instead of a 500.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.search_postgres import (
    STATE_NAME_TO_CODE,
    get_db_pool,
    normalize_state_input,
)

router = APIRouter(prefix="/data-centers", tags=["data-centers"])

tracer = trace.get_tracer(__name__)

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

_STATE_CODE_TO_NAME: dict[str, str] = {
    code: name for name, code in STATE_NAME_TO_CODE.items()
}

ScopeLevel = Literal["national", "state", "city", "jurisdiction"]


class JobClaimScope(BaseModel):
    """The filters actually applied to ``items``; ``level='national'`` when none."""

    level: ScopeLevel
    state_code: str | None = Field(
        None, description="2-letter state code filter, if any."
    )
    state: str | None = Field(
        None, description="Full state name for state_code, if known."
    )
    city: str | None = Field(
        None, description="City filter (matched on jurisdiction_name)."
    )
    jurisdiction_id: str | None = Field(
        None, description="Exact jurisdiction_id filter."
    )


class JobClaim(BaseModel):
    """One jobs claim from a meeting; unknown values are null, never 0."""

    job_claim_id: str
    phase: Literal["construction", "operations"] = Field(
        ..., description="Never combined: one row per phase (the mart's CHECK)."
    )
    headcount_low: int | None = None
    headcount_high: int | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    project_name: str | None = None
    quote: str = Field(
        ..., description="Verbatim words of the claim; the mart drops rows without one."
    )
    speaker_name: str | None = None
    person_id: str | None = None
    event_meeting_id: int = Field(
        ..., description="FK to event_meeting (the mart's NOT NULL integer key)."
    )
    meeting_date: date | None = None
    video_id: str | None = None
    start_seconds: float | None = None


class JobClaimTotals(BaseModel):
    """Claims per phase for the whole scope, before ``limit``: real counts, so 0 means none."""

    construction: int = 0
    operations: int = 0


class JobClaimsResponse(BaseModel):
    scope: JobClaimScope
    totals: JobClaimTotals = Field(default_factory=JobClaimTotals)
    items: list[JobClaim]


_SELECT_SQL = """
    SELECT
        job_claim_id,
        phase,
        headcount_low,
        headcount_high,
        starts_on,
        ends_on,
        project_name,
        quote,
        speaker_name,
        person_id,
        event_meeting_id,
        meeting_date,
        video_id,
        start_seconds
    FROM job_claim
"""


def _clean(value: str | None) -> str | None:
    """Strip a query value; blank becomes None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def build_scope(
    state: str | None, city: str | None, jurisdiction_id: str | None
) -> JobClaimScope:
    """Normalize the raw query params into the scope that the query applies."""
    state_code = normalize_state_input(_clean(state))
    city_clean = _clean(city)
    jurisdiction_clean = _clean(jurisdiction_id)

    level: ScopeLevel = "national"
    if jurisdiction_clean:
        level = "jurisdiction"
    elif city_clean:
        level = "city"
    elif state_code:
        level = "state"

    return JobClaimScope(
        level=level,
        state_code=state_code,
        state=_STATE_CODE_TO_NAME.get(state_code) if state_code else None,
        city=city_clean,
        jurisdiction_id=jurisdiction_clean,
    )


def _scope_where(scope: JobClaimScope) -> tuple[list[str], list[Any]]:
    """WHERE clauses + params for the scope. ``city`` matches like the browse routes
    (meeting_browse, decision_browse): a substring of the city or the jurisdiction name,
    so a scope carried over from another page finds the same place."""
    clauses: list[str] = ["project_type = 'data_center'"]
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        clauses.append(f"state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        clauses.append(
            f"(city ILIKE ${len(params)} OR jurisdiction_name ILIKE ${len(params)})"
        )
    if scope.jurisdiction_id:
        params.append(scope.jurisdiction_id)
        clauses.append(f"jurisdiction_id = ${len(params)}")
    return clauses, params


def build_job_claims_totals_query(scope: JobClaimScope) -> tuple[str, list[Any]]:
    """Claims per phase for the whole scope (no limit)."""
    clauses, params = _scope_where(scope)
    sql = (
        "    SELECT phase, count(*)::int AS claim_count\n"
        "    FROM job_claim\n"
        f"    WHERE {' AND '.join(clauses)}\n"
        "    GROUP BY phase\n"
    )
    return sql, params


def build_job_claims_query(scope: JobClaimScope, limit: int) -> tuple[str, list[Any]]:
    """SQL + positional params for the scope. Values are always bound, never inlined."""
    clauses, params = _scope_where(scope)
    params.append(limit)
    sql = (
        f"{_SELECT_SQL}"
        f"    WHERE {' AND '.join(clauses)}\n"
        "    ORDER BY meeting_date DESC NULLS LAST, start_seconds ASC NULLS LAST, job_claim_id\n"
        f"    LIMIT ${len(params)}\n"
    )
    return sql, params


@router.get("/job-claims", response_model=JobClaimsResponse)
async def list_job_claims(
    state: str | None = Query(
        None,
        description="2-letter state code (a full state name is normalized to one).",
    ),
    city: str | None = Query(
        None,
        description="City name; case-insensitive substring of city or jurisdiction_name.",
    ),
    jurisdiction_id: str | None = Query(None, description="Exact jurisdiction_id."),
    limit: int = Query(
        DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows (1..500)."
    ),
) -> JobClaimsResponse:
    """
    Data-center jobs claims from meetings, split by phase (construction / operations).

    Example:
        GET /api/data-centers/job-claims?state=AL&city=Tuscaloosa&limit=100
    """
    scope = build_scope(state, city, jurisdiction_id)
    sql, params = build_job_claims_query(scope, limit)
    totals_sql, totals_params = build_job_claims_totals_query(scope)

    with tracer.start_as_current_span("data-centers.job-claims") as span:
        span.set_attribute("job_claims.scope_level", scope.level)
        span.set_attribute("job_claims.state_code", scope.state_code or "")
        span.set_attribute("job_claims.city", scope.city or "")
        span.set_attribute("job_claims.jurisdiction_id", scope.jurisdiction_id or "")
        span.set_attribute("job_claims.limit", limit)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("data-centers.job-claims.query"):
                    rows = await conn.fetch(sql, *params)
                    total_rows = await conn.fetch(totals_sql, *totals_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            span.set_attribute("job_claims.relation_missing", True)
            logger.warning(
                "data-centers: relation 'job_claim' isn't in this database yet ({}); "
                "returning an empty list",
                e,
            )
            return JobClaimsResponse(scope=scope, items=[])
        except Exception as e:  # noqa: BLE001 - any other DB failure is a 500
            span.record_exception(e)
            logger.error(
                "data-centers job-claims error (scope={}): {}", scope.model_dump(), e
            )
            raise HTTPException(status_code=500, detail="Failed to load job claims")

        items = [JobClaim(**dict(row)) for row in rows]
        totals = JobClaimTotals(
            **{
                r["phase"]: r["claim_count"]
                for r in total_rows
                if r["phase"] in ("construction", "operations")
            }
        )
        span.set_attribute("job_claims.count", len(items))
        logger.info(
            "🏗️ Data-center job claims -> {} rows (scope={})", len(items), scope.level
        )
        return JobClaimsResponse(scope=scope, totals=totals, items=items)
