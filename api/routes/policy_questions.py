"""
Policy-question registry API.

Serves the cross-jurisdiction policy-question layer: a question with its
pro/con canonical arguments (Boydstun-framed) and the comparative rollup
("32 of 47 jurisdictions approved"), plus the list of decisions/bills that
instantiate it. Reads the public marts published over gold
(policy_question / canonical_argument / question_instance / instance_argument).

No fabricated data: a question with zero mapped instances returns an explicit
empty rollup (all-zero counts), never placeholder numbers.
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/policy-question", tags=["policy-question"])
tracer = trace.get_tracer(__name__)


class ArgumentOut(BaseModel):
    argument_id: str
    stance: Optional[str] = None
    label: Optional[str] = None
    summary: Optional[str] = None
    source_role: Optional[str] = None
    frame_id: Optional[str] = None
    frame_label: Optional[str] = None
    member_count: int = 0


class RollupOut(BaseModel):
    instances_total: int = 0
    decisions_total: int = 0
    bills_total: int = 0
    jurisdictions_total: int = 0
    jurisdictions_approved: int = 0
    states_total: int = 0
    approved_count: int = 0
    denied_count: int = 0
    deferred_count: int = 0
    other_count: int = 0


class InstanceOut(BaseModel):
    instance_id: str
    source_type: str
    source_id: str
    state_code: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    city: Optional[str] = None
    outcome_raw: Optional[str] = None
    outcome_normalized: Optional[str] = None
    occurred_at: Optional[Any] = None
    assign_score: Optional[float] = None


class PolicyQuestionSummary(BaseModel):
    question_id: str
    canonical_text: Optional[str] = None
    topic_code: Optional[str] = None
    primary_theme: Optional[str] = None
    cofog_code: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    instances_total: int = 0
    jurisdictions_total: int = 0
    jurisdictions_approved: int = 0


class PolicyQuestionDetail(PolicyQuestionSummary):
    first_seen: Optional[Any] = None
    rollup: RollupOut
    arguments: List[ArgumentOut] = []
    sample_instances: List[InstanceOut] = []


_LIST_SQL = """
    select question_id, canonical_text, topic_code, primary_theme, cofog_code,
           scope, status, instances_total, jurisdictions_total, jurisdictions_approved
    from public.policy_question
    where ($1::text is null or primary_theme = $1)
      and ($2::text is null or scope = $2)
    order by instances_total desc
    limit $3 offset $4
"""

_DETAIL_SQL = "select * from public.policy_question where question_id = $1"

_ARGS_SQL = """
    select argument_id, stance, label, summary, source_role,
           frame_id, frame_label, member_count
    from public.canonical_argument
    where question_id = $1
    order by stance nulls last, member_count desc
"""

_INSTANCES_SQL = """
    select instance_id, source_type, source_id, state_code, jurisdiction_name,
           city, outcome_raw, outcome_normalized, occurred_at, assign_score
    from public.question_instance
    where question_id = $1
    order by assign_score desc nulls last
    limit $2 offset $3
"""


@router.get("/", response_model=List[PolicyQuestionSummary])
async def list_policy_questions(
    theme: Optional[str] = Query(None, description="Filter by coarse primary_theme bucket."),
    scope: Optional[str] = Query(None, description="local | state | both."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[PolicyQuestionSummary]:
    with tracer.start_as_current_span("policy-question-list") as span:
        span.set_attribute("policy_question.theme", theme or "")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(_LIST_SQL, theme, scope, limit, offset)
        return [PolicyQuestionSummary(**dict(r)) for r in rows]


@router.get("/{question_id}", response_model=PolicyQuestionDetail)
async def get_policy_question(
    question_id: str,
    sample: int = Query(12, ge=0, le=100),
) -> PolicyQuestionDetail:
    with tracer.start_as_current_span("policy-question-detail") as span:
        span.set_attribute("policy_question.id", question_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(_DETAIL_SQL, question_id)
                if row is None:
                    raise HTTPException(status_code=404, detail=f"No policy question '{question_id}'")
                args = await conn.fetch(_ARGS_SQL, question_id)
                insts = await conn.fetch(_INSTANCES_SQL, question_id, sample, 0)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("policy-question detail failed for {}", question_id)
            span.record_exception(exc)
            raise HTTPException(status_code=500, detail="policy-question lookup failed") from exc

        d = dict(row)
        rollup = RollupOut(**{k: d.get(k, 0) for k in RollupOut.model_fields})
        return PolicyQuestionDetail(
            question_id=d["question_id"],
            canonical_text=d.get("canonical_text"),
            topic_code=d.get("topic_code"),
            primary_theme=d.get("primary_theme"),
            cofog_code=d.get("cofog_code"),
            scope=d.get("scope"),
            status=d.get("status"),
            first_seen=d.get("first_seen"),
            instances_total=d.get("instances_total", 0),
            jurisdictions_total=d.get("jurisdictions_total", 0),
            jurisdictions_approved=d.get("jurisdictions_approved", 0),
            rollup=rollup,
            arguments=[ArgumentOut(**dict(a)) for a in args],
            sample_instances=[InstanceOut(**dict(i)) for i in insts],
        )


@router.get("/{question_id}/instances", response_model=List[InstanceOut])
async def get_question_instances(
    question_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[InstanceOut]:
    with tracer.start_as_current_span("policy-question-instances") as span:
        span.set_attribute("policy_question.id", question_id)
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(_INSTANCES_SQL, question_id, limit, offset)
        return [InstanceOut(**dict(r)) for r in rows]
