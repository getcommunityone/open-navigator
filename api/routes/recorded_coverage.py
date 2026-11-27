"""How much of a place our meeting recordings cover (#1348): ``GET /api/coverage/recorded-meetings``.

A story's counts ("data centers came up in 10 meetings") are counts of *our recordings*. This endpoint says how many
local governments and recorded meetings sit behind them for the scope, from ``recorded_meeting_year`` (one row per
government per year), so the page can state its coverage next to the count. Every number is a real count; when the table
is missing the response says ``available: false`` and every count is null, never zero (CLAUDE.md, No Fabricated Data).

There is deliberately no "of N governments" denominator: the ``jurisdictions`` mart counts census places (census-
designated places included) as cities, so it is not a reliable count of local governments
(web_docs/docs/guides/data-stories.md, "Recording coverage").
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

router = APIRouter(prefix="/coverage", tags=["coverage"])
tracer = trace.get_tracer(__name__)


class RecordedCoverageResponse(BaseModel):
    scope: JobClaimScope
    available: bool = Field(..., description="False when recorded_meeting_year can't be read: every count is null.")
    governments: int | None = Field(None, description="Local governments with at least one recorded meeting in scope.")
    meetings: int | None = Field(None, description="Recorded meetings in scope, all years.")
    states: int | None = Field(None, description="States those governments are in.")


def build_coverage_sql(scope: JobClaimScope) -> tuple[str, list[Any]]:
    """Governments, meetings and states in scope. A city matches like the story's other city filters: a substring of
    the government's name (so "Tuscaloosa" counts the city and the Tuscaloosa City School District)."""
    where: list[str] = []
    params: list[Any] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"state_code = ${len(params)}")
        if scope.city:
            params.append(f"%{scope.city}%")
            where.append(f"jurisdiction_name ILIKE ${len(params)}")
    sql = (
        "SELECT count(DISTINCT jurisdiction_id)::int AS governments, coalesce(sum(recorded_meetings), 0)::int AS meetings, "
        "count(DISTINCT state_code)::int AS states FROM recorded_meeting_year "
        f"WHERE {' AND '.join(where) or 'TRUE'}"
    )
    return sql, params


@router.get("/recorded-meetings", response_model=RecordedCoverageResponse)
async def recorded_meetings_coverage(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City or government name within the state."),
) -> RecordedCoverageResponse:
    """
    The local governments and recorded meetings behind a story's counts for the scope.

    Example:
        GET /api/coverage/recorded-meetings?state=FL
    """
    raw = build_scope(state, city, None)
    scope = JobClaimScope(
        level="city" if raw.state_code and raw.city else "state" if raw.state_code else "national",
        state_code=raw.state_code,
        state=raw.state,
        city=raw.city if raw.state_code else None,
    )
    sql, params = build_coverage_sql(scope)
    with tracer.start_as_current_span("coverage.recorded-meetings") as span:
        span.set_attribute("coverage.scope_level", scope.level)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(sql, *params)
        except (asyncpg.exceptions.UndefinedTableError, asyncpg.exceptions.UndefinedColumnError) as e:
            span.set_attribute("coverage.relation_missing", True)
            logger.warning("coverage: 'recorded_meeting_year' isn't here yet ({}); unavailable", e)
            return RecordedCoverageResponse(scope=scope, available=False)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("coverage error (scope={}): {}", scope.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load recording coverage")
        return RecordedCoverageResponse(
            scope=scope,
            available=True,
            governments=row["governments"] if row else None,
            meetings=row["meetings"] if row else None,
            states=row["states"] if row else None,
        )
