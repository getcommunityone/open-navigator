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
    is_featured: bool = False
    display_order: Optional[int] = None
    # Real money & talk (see dbt policy_question mart). money_total = dollars moved
    # by this question's local decisions; *_share = its slice of ALL decisions.
    money_total: float = 0
    money_share: float = 0
    talk_share: float = 0


class RelationOut(BaseModel):
    relation_type: str
    direction: str  # "outgoing" (this -> other) | "incoming" (other -> this)
    evidence: Optional[str] = None
    question_id: str
    canonical_text: Optional[str] = None
    scope: Optional[str] = None


class TrendPoint(BaseModel):
    quarter_start: Any  # date — ISO-serialized
    instances: int = 0
    money: float = 0


class PolicyQuestionDetail(PolicyQuestionSummary):
    first_seen: Optional[Any] = None
    rollup: RollupOut
    arguments: List[ArgumentOut] = []
    sample_instances: List[InstanceOut] = []
    relations: List[RelationOut] = []
    # Per-quarter history (real): how often the question came up + dollars moved.
    trend: List[TrendPoint] = []


_RELATIONS_SQL = """
    select
        r.relation_type,
        r.evidence,
        case when r.from_question_id = $1 then 'outgoing' else 'incoming' end as direction,
        q.question_id, q.canonical_text, q.scope
    from public.policy_question_relation r
    join public.policy_question q
      on q.question_id = case when r.from_question_id = $1
                              then r.to_question_id else r.from_question_id end
    where r.from_question_id = $1 or r.to_question_id = $1
    order by r.relation_type
"""


# Shared projection for the summary list. is_featured/display_order are the
# curated-feature columns (added by the parallel dbt build); display_order is
# nullable and only meaningful for featured rows.
_LIST_COLS = """
    question_id, canonical_text, topic_code, primary_theme, cofog_code,
    scope, status, instances_total, jurisdictions_total, jurisdictions_approved,
    is_featured, display_order,
    money_total, money_share, talk_share
"""

# Default list: theme/scope filters. Curated featured questions are PINNED to the
# top in editorial order (display_order); everything else follows, ranked by reach.
_LIST_SQL = f"""
    select {_LIST_COLS}
    from public.policy_question
    where ($1::text is null or primary_theme = $1)
      and ($2::text is null or scope = $2)
    order by is_featured desc, display_order asc nulls last, instances_total desc
    limit $3 offset $4
"""

# Featured list: curated home-page rows only, in editorial order
# (display_order asc, nulls last), theme/scope filters still respected.
_LIST_FEATURED_SQL = f"""
    select {_LIST_COLS}
    from public.policy_question
    where is_featured = true
      and ($1::text is null or primary_theme = $1)
      and ($2::text is null or scope = $2)
    order by display_order asc nulls last, instances_total desc
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

# Quarterly history (oldest → newest) for the registry drill-down trend chart.
_TREND_SQL = """
    select quarter_start, instances, coalesce(money, 0) as money
    from public.policy_question_trend
    where question_id = $1
    order by quarter_start asc
"""


@router.get("/", response_model=List[PolicyQuestionSummary])
async def list_policy_questions(
    theme: Optional[str] = Query(None, description="Filter by coarse primary_theme bucket."),
    scope: Optional[str] = Query(None, description="local | state | both."),
    featured: bool = Query(
        False,
        description=(
            "When true, return ONLY curated featured questions "
            "(is_featured = true), ordered by display_order asc nulls last."
        ),
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[PolicyQuestionSummary]:
    with tracer.start_as_current_span("policy-question-list") as span:
        span.set_attribute("policy_question.theme", theme or "")
        span.set_attribute("policy_question.featured", featured)
        sql = _LIST_FEATURED_SQL if featured else _LIST_SQL
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, theme, scope, limit, offset)
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
                trend = await conn.fetch(_TREND_SQL, question_id)
                try:
                    rels = await conn.fetch(_RELATIONS_SQL, question_id)
                except Exception:  # noqa: BLE001 — relations are best-effort (Phase 3 mart optional)
                    rels = []
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
            is_featured=d.get("is_featured", False),
            display_order=d.get("display_order"),
            money_total=float(d.get("money_total") or 0),
            money_share=float(d.get("money_share") or 0),
            talk_share=float(d.get("talk_share") or 0),
            rollup=rollup,
            arguments=[ArgumentOut(**dict(a)) for a in args],
            sample_instances=[InstanceOut(**dict(i)) for i in insts],
            relations=[RelationOut(**dict(r)) for r in rels],
            trend=[TrendPoint(**dict(t)) for t in trend],
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
