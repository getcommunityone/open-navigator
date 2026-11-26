"""
Policy-question registry API.

Serves the cross-jurisdiction policy-question layer: a question with its
pro/con canonical arguments (Boydstun-framed) and the comparative rollup
("32 of 47 jurisdictions approved"), plus the list of decisions/bills that
instantiate it. Reads the public marts published over gold
(policy_question / canonical_argument / question_instance / instance_argument).

No fabricated data: a question with zero mapped instances returns an explicit
empty rollup (all-zero counts), never placeholder numbers.

Scope (#499): the detail, instances and meetings endpoints take ?state=&city=.
Every figure the question header shows (outcome counts, jurisdictions, money,
meetings) is then counted over the same scoped rows the lists show, and the
response says which scope it is (`scope.level` national | state | city). Outcome
families come from question_instance.outcome_family, the rollup's own rule (dbt
macro question_outcome_family), never re-derived here.
"""

from __future__ import annotations

import json
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.data_centers import jump_url
from api.routes.search_postgres import get_db_pool, normalize_state_input

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
    # Date range of the counted instances (#508's plain summary: "since May 2026").
    first_occurred_at: Optional[Any] = None
    last_occurred_at: Optional[Any] = None
    decisions_total: int = 0
    bills_total: int = 0
    jurisdictions_total: int = 0
    jurisdictions_approved: int = 0
    states_total: int = 0
    approved_count: int = 0
    denied_count: int = 0
    deferred_count: int = 0
    # Adopted/recommended moratoriums (#483) — its own family, never approved.
    moratorium_count: int = 0
    other_count: int = 0


# The rollup's outcome families (dbt macro question_outcome_family).
OutcomeFamily = Literal["approved", "denied", "moratorium", "deferred", "other"]


class ScopeOut(BaseModel):
    """The place scope every figure in a response is counted over."""

    level: Literal["national", "state", "city"] = "national"
    state_code: Optional[str] = None
    city: Optional[str] = None


class CompanyMentionOut(BaseModel):
    """A company named for a decision (dbt decision_company_mention, #508, #525)."""

    operator_name: str
    # The exact words matched, and a verbatim excerpt with them in <mark>.
    matched_text: str
    evidence: Optional[str] = None
    # decision_text: the decision's own headline/statement. meeting_passage: a passage of
    # its own meeting, where the passage says the company is the applicant or developer
    # (#525); the page labels it "Named in the meeting".
    evidence_source: str = "decision_text"
    # meeting_passage only: the passage's moment in the recording (its first data center
    # cue, not the exact second of the quote), and a link to it. When the transcript is
    # untimed the link is the recording itself with no time.
    start_seconds: Optional[float] = None
    jump_url: Optional[str] = None


class NearbySiteOut(BaseModel):
    """A tracked Epoch AI site near the decision's government (#445 mapping). Nearby only."""

    data_center_site_id: str
    site_name: Optional[str] = None
    owner: Optional[str] = None


class InstanceOut(BaseModel):
    instance_id: str
    source_type: str
    source_id: str
    state_code: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    city: Optional[str] = None
    outcome_raw: Optional[str] = None
    outcome_normalized: Optional[str] = None
    outcome_family: Optional[str] = None
    occurred_at: Optional[Any] = None
    assign_score: Optional[float] = None
    # #508: what was decided, where and who. All null/empty for a state bill.
    event_decision_id: Optional[str] = None
    headline: Optional[str] = None
    # A street-level address that agrees with the decision's own government
    # (dbt decision_place_label); null when there is none we can trust.
    place_label: Optional[str] = None
    # Companies named for the decision: from its own headline/statement, or (#525) from a
    # passage of its own meeting, each with the matched text and a verbatim quote.
    company_names: List[str] = []
    company_evidence: Optional[str] = None
    company_mentions: List[CompanyMentionOut] = []
    # Tracked sites near the decision's government. NOT the decision's subject.
    nearby_sites: List[NearbySiteOut] = []


class QuestionMeetingOut(BaseModel):
    """A real meeting whose transcript discusses the question's alias keyword(s)."""

    video_id: str
    event_title: Optional[str] = None
    event_date: Optional[Any] = None  # date — ISO-serialized
    state_code: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    video_url: Optional[str] = None
    n_alias_hits: int = 0
    # Verbatim transcript passage with the alias words <mark>ed (ts_headline in
    # dbt question_transcript_link, #499), and the moment to jump to.
    evidence: Optional[str] = None
    start_seconds: Optional[float] = None
    # The recording at start_seconds (YouTube t=); null when the transcript is untimed.
    jump_url: Optional[str] = None


class MoneySourceOut(BaseModel):
    """A linked decision whose net_dollar_impact adds up to money_total."""

    event_decision_id: str
    title: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    state_code: Optional[str] = None
    outcome_family: Optional[str] = None
    occurred_at: Optional[Any] = None
    net_dollar_impact: float = 0


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
    # Linked local decisions that adopted or recommended a moratorium (#483).
    moratorium_count: int = 0
    is_featured: bool = False
    display_order: Optional[int] = None
    # Real money & talk (see dbt policy_question mart). money_total = dollars moved
    # by this question's local decisions; *_share = its slice of ALL decisions.
    money_total: float = 0
    money_share: float = 0
    talk_share: float = 0
    # Real meetings whose transcript discusses this question's alias keyword(s)
    # (dbt question_transcript_link). High-recall keyword signal, distinct from the
    # structured decision/bill instances above — powers the "discussed in N
    # meetings" fallback for questions with zero mapped decisions.
    discussion_meeting_count: int = 0


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
    # The question's level (local | state | both); `scope` is the place scope here.
    question_scope: Optional[str] = None
    # The place scope every count, money figure and meeting count below is for (#499).
    scope: ScopeOut = ScopeOut()  # type: ignore[assignment]
    rollup: RollupOut
    # The decisions whose net_dollar_impact sums to money_total, largest first.
    money_sources: List[MoneySourceOut] = []
    # The Browse Topics topic named like one of the question's aliases (e.g. the
    # "Data centers" topic), when one exists; null otherwise.
    topic_id: Optional[int] = None
    topic_name: Optional[str] = None
    arguments: List[ArgumentOut] = []
    sample_instances: List[InstanceOut] = []
    relations: List[RelationOut] = []
    # Per-quarter history (real), counted over the same scope (and outcome, when given)
    # as the rollup: how often the question came up + dollars moved.
    trend: List[TrendPoint] = []
    # #508: with ?outcome=, the same counts for that outcome family only (the dashboard's
    # summary sentence). Null without an outcome.
    outcome: Optional[str] = None
    outcome_rollup: Optional[RollupOut] = None


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
    moratorium_count, is_featured, display_order,
    money_total, money_share, talk_share,
    (select count(*) from public.question_transcript_link l
       where l.question_id = policy_question.question_id) as discussion_meeting_count
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

# Place scope (#499), shared by every scoped query: $2 = state_code or null,
# $3 = '%city%' or null (the same ILIKE on city / jurisdiction_name that
# /api/decisions uses, so the header counts and the decision list agree).
_SCOPE_WHERE = """
      and ($2::text is null or {a}.state_code = $2)
      and ($3::text is null or {a}.city ilike $3 or {a}.jurisdiction_name ilike $3)
"""

# Header counts for the scope: the rollup's aggregates (int_policy_question_rollup)
# over the scoped question_instance rows, by the same outcome_family column.
_SCOPED_COUNTS_SQL = f"""
    select
        count(*)::int                                                      as instances_total,
        count(*) filter (where qi.source_type = 'local_decision')::int     as decisions_total,
        count(*) filter (where qi.source_type = 'state_bill')::int         as bills_total,
        count(distinct coalesce(qi.state_code, '') || '|' || coalesce(qi.jurisdiction_name, ''))::int
                                                                           as jurisdictions_total,
        count(distinct coalesce(qi.state_code, '') || '|' || coalesce(qi.jurisdiction_name, ''))
            filter (where qi.outcome_family = 'approved')::int             as jurisdictions_approved,
        count(distinct qi.state_code)::int                                 as states_total,
        count(*) filter (where qi.outcome_family = 'approved')::int        as approved_count,
        count(*) filter (where qi.outcome_family = 'denied')::int          as denied_count,
        count(*) filter (where qi.outcome_family = 'deferred')::int        as deferred_count,
        count(*) filter (where qi.outcome_family = 'moratorium')::int      as moratorium_count,
        count(*) filter (where qi.outcome_family = 'other')::int           as other_count,
        min(qi.occurred_at)::date                                          as first_occurred_at,
        max(qi.occurred_at)::date                                          as last_occurred_at
    from public.question_instance qi
    where qi.question_id = $1
    {_SCOPE_WHERE.format(a="qi")}
      and ($4::text is null or qi.outcome_family = $4)
"""

# The linked decisions that carry a dollar figure: money_total is their sum, as in
# the rollup (item_interestingness.net_dollar_impact, already max-not-summed per
# decision). Listed so the page can show where the amount comes from.
_MONEY_SOURCES_SQL = f"""
    select
        qi.source_id                       as event_decision_id,
        ii.title,
        qi.jurisdiction_name,
        qi.state_code,
        qi.outcome_family,
        qi.occurred_at,
        ii.net_dollar_impact::float8       as net_dollar_impact
    from public.question_instance qi
    join public.item_interestingness ii
      on ii.event_decision_id = qi.source_id
    where qi.question_id = $1
      and qi.source_type = 'local_decision'
      and coalesce(ii.net_dollar_impact, 0) <> 0
    {_SCOPE_WHERE.format(a="qi")}
    order by abs(ii.net_dollar_impact) desc, qi.source_id
"""

# $4 = outcome family or null. {order} is one of _INSTANCE_ORDER.
# #508: each local decision carries its headline (latest extraction), the place label,
# the companies its own text names and the tracked sites near its government, all
# built in dbt (decision_place_label, decision_company_mention,
# decision_nearby_data_center_site); bills get nulls / empty lists.
_INSTANCES_SQL_TMPL = f"""
    select qi.instance_id, qi.source_type, qi.source_id, qi.state_code, qi.jurisdiction_name,
           qi.city, qi.outcome_raw, qi.outcome_normalized, qi.outcome_family, qi.occurred_at,
           qi.assign_score,
           d.event_decision_id, d.headline,
           pl.place_label,
           coalesce(cm.mentions, '[]'::jsonb)::text as company_mentions,
           coalesce(ns.sites, '[]'::jsonb)::text    as nearby_sites
    from public.question_instance qi
    left join lateral (
        select ed.event_decision_id, ed.headline
        from public.event_decision ed
        where qi.source_type = 'local_decision' and ed.event_decision_id = qi.source_id
        order by ed.extracted_at desc
        limit 1
    ) d on true
    left join public.decision_place_label pl on pl.event_decision_id = d.event_decision_id
    left join lateral (
        select jsonb_agg(jsonb_build_object(
                   'operator_name', m.operator_name,
                   'matched_text', m.matched_text,
                   'evidence', m.evidence,
                   'evidence_source', m.evidence_source,
                   'start_seconds', m.start_seconds::float8,
                   'video_url', mm.video_url) order by m.operator_name) as mentions
        from public.decision_company_mention m
        left join public.data_center_meeting_mention mm
          on mm.data_center_meeting_mention_id = m.data_center_meeting_mention_id
        where m.event_decision_id = d.event_decision_id
    ) cm on true
    left join lateral (
        select jsonb_agg(jsonb_build_object(
                   'data_center_site_id', s.data_center_site_id,
                   'site_name', s.site_name,
                   'owner', s.owner) order by s.site_name) as sites
        from public.decision_nearby_data_center_site n
        join public.data_center_site s on s.data_center_site_id = n.data_center_site_id
        where n.event_decision_id = d.event_decision_id
    ) ns on true
    where qi.question_id = $1
    {_SCOPE_WHERE.format(a="qi")}
      and ($4::text is null or qi.outcome_family = $4)
    order by {{order}}
    limit $5 offset $6
"""

_INSTANCE_ORDER = {
    "relevance": "qi.assign_score desc nulls last, qi.instance_id",
    # Newest first; a future date is a source error (#472), so it sorts with the unknowns.
    "recent": "(qi.occurred_at is null or qi.occurred_at > current_date), qi.occurred_at desc, qi.instance_id",
}
_INSTANCES_SQL = _INSTANCES_SQL_TMPL.format(order=_INSTANCE_ORDER["relevance"])
_INSTANCES_RECENT_SQL = _INSTANCES_SQL_TMPL.format(order=_INSTANCE_ORDER["recent"])


def _mention(m: dict[str, Any]) -> CompanyMentionOut:
    """One company mention -> CompanyMentionOut. A meeting_passage link goes to the recording
    at the passage's moment, or to the recording alone when untimed; decision_text has none."""
    video_url = m.pop("video_url", None) or ""
    if m.get("evidence_source") == "meeting_passage" and video_url:
        m["jump_url"] = jump_url(video_url, m.get("start_seconds")) or video_url
    return CompanyMentionOut(**m)


def _instance(row: Any) -> InstanceOut:
    """One instances row -> InstanceOut, decoding the JSON lists and the company fields."""
    d = dict(row)
    mentions = [_mention(m) for m in json.loads(d.pop("company_mentions", None) or "[]")]
    sites = [NearbySiteOut(**s) for s in json.loads(d.pop("nearby_sites", None) or "[]")]
    return InstanceOut(
        **d,
        company_mentions=mentions,
        company_names=[m.operator_name for m in mentions],
        company_evidence=" · ".join(m.evidence for m in mentions if m.evidence) or None,
        nearby_sites=sites,
    )


# Per-quarter history for the scope and outcome: the policy_question_trend mart's rule
# (instances by quarter; money = the linked decision's item_interestingness
# net_dollar_impact) over the scoped question_instance rows, so the chart never shows
# national figures under a state label.
_SCOPED_TREND_SQL = f"""
    select date_trunc('quarter', qi.occurred_at)::date as quarter_start,
           count(*)::int                                  as instances,
           coalesce(sum(ii.net_dollar_impact), 0)::float8 as money
    from public.question_instance qi
    left join public.item_interestingness ii
      on ii.event_decision_id = qi.source_id and qi.source_type = 'local_decision'
    where qi.question_id = $1
      and qi.occurred_at is not null
    {_SCOPE_WHERE.format(a="qi")}
      and ($4::text is null or qi.outcome_family = $4)
    group by 1
    order by 1
"""

# Real meetings whose transcript discusses the question's alias keyword(s)
# (dbt question_transcript_link), newest first. A date after today is a source
# error (#472), so it sorts with the unknown dates at the end; relevance
# (n_alias_hits) breaks ties.
_MEETINGS_SQL = f"""
    select video_id, event_title, event_date, state_code, state, city,
           jurisdiction_name, video_url, n_alias_hits,
           evidence, start_seconds::float8 as start_seconds
    from public.question_transcript_link l
    where l.question_id = $1
    {_SCOPE_WHERE.format(a="l")}
    order by (l.event_date is null or l.event_date > current_date),
             l.event_date desc,
             l.n_alias_hits desc,
             l.video_id
    limit $4 offset $5
"""

_DISCUSSION_COUNT_SQL = f"""
    select count(*) from public.question_transcript_link l
    where l.question_id = $1
    {_SCOPE_WHERE.format(a="l")}
"""


# Browse Topics topic whose name equals one of the question's curated aliases.
_TOPIC_SQL = """
    select t.topic_id, t.name as topic_name
    from public.policy_question q
    cross join lateral unnest(coalesce(q.aliases, '{}'::text[])) as a(alias)
    join public.civicsearch_topic t on lower(t.name) = lower(trim(a.alias))
    where q.question_id = $1
    order by t.topic_id
    limit 1
"""


def _scope(state: Optional[str], city: Optional[str]) -> tuple[ScopeOut, Optional[str], Optional[str]]:
    """Normalize ?state=&city= into the response scope and the SQL params ($2, $3)."""
    state_code = normalize_state_input(state) if state and state.strip() else None
    city_name = city.strip() if city and city.strip() else None
    level = "city" if city_name else "state" if state_code else "national"
    city_param = f"%{city_name}%" if city_name else None
    return ScopeOut(level=level, state_code=state_code, city=city_name), state_code, city_param



_ROLLUP_DATES = ("first_occurred_at", "last_occurred_at")


def _rollup(c: dict[str, Any]) -> RollupOut:
    """A scoped counts row -> RollupOut (missing counts read 0, missing dates null)."""
    return RollupOut(
        **{k: int(c.get(k) or 0) for k in RollupOut.model_fields if k not in _ROLLUP_DATES},
        **{k: c.get(k) for k in _ROLLUP_DATES},
    )


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
    state: Optional[str] = Query(None, description="2-letter state code (a full name is normalized)."),
    city: Optional[str] = Query(None, description="City; case-insensitive match on city / jurisdiction name."),
    outcome: Optional[OutcomeFamily] = Query(
        None,
        description=(
            "Outcome family. Adds outcome_rollup (the counts for that family) and limits the "
            "trend and sample instances to it; rollup stays all families."
        ),
    ),
) -> PolicyQuestionDetail:
    """One question, with every count and the money figure computed for the scope.

    Example: ``GET /api/policy-question/f7001f99695ccecb1e8df4ab0ee721fd?state=WA``
    """
    scope, state_code, city_param = _scope(state, city)
    with tracer.start_as_current_span("policy-question-detail") as span:
        span.set_attribute("policy_question.id", question_id)
        span.set_attribute("policy_question.scope", scope.level)
        span.set_attribute("policy_question.state_code", state_code or "")
        span.set_attribute("policy_question.city", scope.city or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(_DETAIL_SQL, question_id)
                if row is None:
                    raise HTTPException(status_code=404, detail=f"No policy question '{question_id}'")
                counts = await conn.fetchrow(
                    _SCOPED_COUNTS_SQL, question_id, state_code, city_param, None
                )
                outcome_counts = (
                    await conn.fetchrow(_SCOPED_COUNTS_SQL, question_id, state_code, city_param, outcome)
                    if outcome
                    else None
                )
                money_rows = await conn.fetch(_MONEY_SOURCES_SQL, question_id, state_code, city_param)
                args = await conn.fetch(_ARGS_SQL, question_id)
                insts = await conn.fetch(
                    _INSTANCES_RECENT_SQL, question_id, state_code, city_param, outcome, sample, 0
                )
                trend = await conn.fetch(_SCOPED_TREND_SQL, question_id, state_code, city_param, outcome)
                discussion_count = await conn.fetchval(
                    _DISCUSSION_COUNT_SQL, question_id, state_code, city_param
                )
                try:
                    rels = await conn.fetch(_RELATIONS_SQL, question_id)
                except Exception:  # noqa: BLE001 — relations are best-effort (Phase 3 mart optional)
                    rels = []
                try:
                    topic = await conn.fetchrow(_TOPIC_SQL, question_id)
                except Exception:  # noqa: BLE001 — the topic link is optional
                    topic = None
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("policy-question detail failed for {}", question_id)
            span.record_exception(exc)
            raise HTTPException(status_code=500, detail="policy-question lookup failed") from exc

        d = dict(row)
        c = dict(counts) if counts is not None else {}
        rollup = _rollup(c)
        outcome_rollup = _rollup(dict(outcome_counts)) if outcome_counts is not None else None
        money_sources = [MoneySourceOut(**dict(m)) for m in money_rows]
        money_total = float(sum(m.net_dollar_impact for m in money_sources))
        span.set_attribute("policy_question.instances_total", rollup.instances_total)
        return PolicyQuestionDetail(
            question_id=d["question_id"],
            canonical_text=d.get("canonical_text"),
            topic_code=d.get("topic_code"),
            primary_theme=d.get("primary_theme"),
            cofog_code=d.get("cofog_code"),
            question_scope=d.get("scope"),
            status=d.get("status"),
            first_seen=d.get("first_seen"),
            scope=scope,
            instances_total=rollup.instances_total,
            jurisdictions_total=rollup.jurisdictions_total,
            jurisdictions_approved=rollup.jurisdictions_approved,
            moratorium_count=rollup.moratorium_count,
            is_featured=d.get("is_featured", False),
            display_order=d.get("display_order"),
            money_total=money_total,
            # Shares are of ALL decisions nationwide (policy_question mart); the UI labels them so.
            money_share=float(d.get("money_share") or 0),
            talk_share=float(d.get("talk_share") or 0),
            discussion_meeting_count=int(discussion_count or 0),
            rollup=rollup,
            money_sources=money_sources,
            topic_id=(dict(topic).get("topic_id") if topic else None),
            topic_name=(dict(topic).get("topic_name") if topic else None),
            arguments=[ArgumentOut(**dict(a)) for a in args],
            sample_instances=[_instance(i) for i in insts],
            relations=[RelationOut(**dict(r)) for r in rels],
            trend=[TrendPoint(**dict(t)) for t in trend],
            outcome=outcome,
            outcome_rollup=outcome_rollup,
        )


@router.get("/{question_id}/instances", response_model=List[InstanceOut])
async def get_question_instances(
    question_id: str,
    state: Optional[str] = Query(None, description="2-letter state code (a full name is normalized)."),
    city: Optional[str] = Query(None, description="City; case-insensitive match on city / jurisdiction name."),
    outcome: Optional[OutcomeFamily] = Query(
        None, description="Outcome family: approved | denied | moratorium | deferred | other."
    ),
    order: Literal["relevance", "recent"] = Query(
        "relevance", description="relevance (assign_score) or recent (newest first)."
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[InstanceOut]:
    """The decisions/bills that instantiate the question, in the scope and outcome family.

    Example: ``GET /api/policy-question/{id}/instances?state=AL&outcome=moratorium``
    """
    scope, state_code, city_param = _scope(state, city)
    with tracer.start_as_current_span("policy-question-instances") as span:
        span.set_attribute("policy_question.id", question_id)
        span.set_attribute("policy_question.scope", scope.level)
        span.set_attribute("policy_question.outcome", outcome or "")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                _INSTANCES_RECENT_SQL if order == "recent" else _INSTANCES_SQL,
                question_id, state_code, city_param, outcome, limit, offset,
            )
        return [_instance(r) for r in rows]


@router.get("/{question_id}/meetings", response_model=List[QuestionMeetingOut])
async def get_question_meetings(
    question_id: str,
    state: Optional[str] = Query(None, description="2-letter state code (a full name is normalized)."),
    city: Optional[str] = Query(None, description="City; case-insensitive match on city / jurisdiction name."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[QuestionMeetingOut]:
    """Real meetings whose transcript discusses the question's alias keyword(s), newest first.

    The "discussed in N meetings" list. Keyword-matched (dbt question_transcript_link):
    a high-recall signal, NOT an AI-extracted decision; the UI labels it as such. Each
    item carries the matched passage (`evidence`, <mark>ed) and the moment to jump to.
    The scoped total is the detail endpoint's `discussion_meeting_count`.
    """
    scope, state_code, city_param = _scope(state, city)
    with tracer.start_as_current_span("policy-question-meetings") as span:
        span.set_attribute("policy_question.id", question_id)
        span.set_attribute("policy_question.scope", scope.level)
        span.set_attribute("policy_question.state_code", state_code or "")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                _MEETINGS_SQL, question_id, state_code, city_param, limit, offset
            )
        out: List[QuestionMeetingOut] = []
        for r in rows:
            d = dict(r)
            d["jump_url"] = jump_url(d.get("video_url") or "", d.get("start_seconds"))
            out.append(QuestionMeetingOut(**d))
        span.set_attribute("policy_question.meeting_count", len(out))
        return out


# --- Jev's reading of meetings for a question (#1032) ---------------------------------------------------------------

class JevMeetingOut(BaseModel):
    """A meeting Jev (a classifier) read as debating the question, with its outcome reading and the verbatim passage."""

    video_id: str
    meeting_title: Optional[str] = None
    meeting_date: Optional[Any] = None  # date — ISO-serialized
    jurisdiction_name: Optional[str] = None
    state_code: Optional[str] = None
    # approved / denied / tabled_or_deferred / moratorium / discussed_no_action; null when none.
    outcome: Optional[str] = None
    outcome_p: Optional[float] = None
    debated_p: Optional[float] = None
    # Verbatim transcript passage, matched words in <mark> (render with highlightSnippet).
    evidence: Optional[str] = None
    jump_url: Optional[str] = None


class JevQuestionOut(BaseModel):
    # False when this database has no Jev reading for the question (the table is missing or the question isn't
    # screened): the UI shows nothing rather than zeros.
    available: bool
    scope: ScopeOut
    meetings: int = 0
    debated: int = 0
    outcomes: dict[str, int] = {}
    items: List[JevMeetingOut] = []


_JEV_COUNTS_SQL = f"""
    select count(*) as meetings,
           count(*) filter (where l.debated) as debated,
           count(*) filter (where l.outcome = 'approved') as approved,
           count(*) filter (where l.outcome = 'denied') as denied,
           count(*) filter (where l.outcome = 'tabled_or_deferred') as tabled_or_deferred,
           count(*) filter (where l.outcome = 'moratorium') as moratorium,
           count(*) filter (where l.outcome = 'discussed_no_action') as discussed_no_action
    from public.meeting_policy_question_jev l
    where l.question_id = $1
    {_SCOPE_WHERE.format(a="l")}
"""

_JEV_ITEMS_SQL = f"""
    select video_id, meeting_title, meeting_date, jurisdiction_name, state_code, outcome,
           outcome_p::float8 as outcome_p, debated_p::float8 as debated_p, evidence, video_url,
           start_seconds::float8 as start_seconds
    from public.meeting_policy_question_jev l
    where l.question_id = $1
    {_SCOPE_WHERE.format(a="l")}
      and ($6::text is null or l.outcome = $6)
    order by case when l.outcome in ('approved', 'denied', 'tabled_or_deferred', 'moratorium') then 0 else 1 end,
             l.meeting_date desc nulls last, l.video_id
    limit $4 offset $5
"""

_JEV_OUTCOMES = ("approved", "denied", "tabled_or_deferred", "moratorium", "discussed_no_action")


@router.get("/{question_id}/jev", response_model=JevQuestionOut)
async def get_question_jev(
    question_id: str,
    state: Optional[str] = Query(None, description="2-letter state code (a full name is normalized)."),
    city: Optional[str] = Query(None, description="City; case-insensitive match on city / jurisdiction name."),
    outcome: Optional[str] = Query(None, description="Only meetings with this outcome reading."),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> JevQuestionOut:
    """Meetings Jev read as debating the question, the outcome counts, and the newest meetings with their passage.

    Jev is a classifier: these are readings with probabilities, not extracted decisions; the UI says so. Actions
    (approved, denied, tabled, moratorium) come first, newest first."""
    scope, state_code, city_param = _scope(state, city)
    if outcome is not None and outcome not in _JEV_OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {', '.join(_JEV_OUTCOMES)}")
    with tracer.start_as_current_span("policy-question-jev") as span:
        span.set_attribute("policy_question.id", question_id)
        span.set_attribute("policy_question.scope", scope.level)
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            if not await conn.fetchval("select to_regclass('public.meeting_policy_question_jev') is not null"):
                return JevQuestionOut(available=False, scope=scope)
            c = await conn.fetchrow(_JEV_COUNTS_SQL, question_id, state_code, city_param)
            rows = await conn.fetch(_JEV_ITEMS_SQL, question_id, state_code, city_param, limit, offset, outcome)
        if not c or not c["meetings"]:
            # Screened but nothing in this scope, or the question isn't screened: say which.
            async with pool.acquire() as conn:
                any_rows = await conn.fetchval(
                    "select exists (select 1 from public.meeting_policy_question_jev where question_id = $1)", question_id
                )
            return JevQuestionOut(available=bool(any_rows), scope=scope)
        items = []
        for r in rows:
            d = dict(r)
            d["jump_url"] = jump_url(d.pop("video_url") or "", d.pop("start_seconds"))
            items.append(JevMeetingOut(**d))
        span.set_attribute("policy_question.jev_meetings", int(c["meetings"]))
        return JevQuestionOut(
            available=True,
            scope=scope,
            meetings=int(c["meetings"]),
            debated=int(c["debated"]),
            outcomes={k: int(c[k]) for k in _JEV_OUTCOMES},
            items=items,
        )
