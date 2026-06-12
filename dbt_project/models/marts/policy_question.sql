-- public.policy_question — the minted registry of recurring, jurisdiction-neutral
-- policy questions that local decisions (and, Phase 2, state bills) map into.
-- Rollup counts are denormalized in from int_policy_question_rollup so the API
-- can serve the comparative numbers ("32 of 47 jurisdictions approved") directly.
with q as (
    select * from {{ ref('stg_policy_question') }}
),
rollup as (
    select * from {{ ref('int_policy_question_rollup') }}
)
select
    q.question_id,
    q.canonical_text,
    q.topic_code,
    q.primary_theme,
    q.cofog_code,
    q.scope,
    q.status,
    q.first_seen,
    q.member_count,
    coalesce(r.instances_total, 0)::integer        as instances_total,
    coalesce(r.decisions_total, 0)::integer        as decisions_total,
    coalesce(r.bills_total, 0)::integer            as bills_total,
    coalesce(r.jurisdictions_total, 0)::integer    as jurisdictions_total,
    coalesce(r.jurisdictions_approved, 0)::integer as jurisdictions_approved,
    coalesce(r.states_total, 0)::integer           as states_total,
    coalesce(r.approved_count, 0)::integer         as approved_count,
    coalesce(r.denied_count, 0)::integer           as denied_count,
    coalesce(r.deferred_count, 0)::integer         as deferred_count,
    coalesce(r.other_count, 0)::integer            as other_count,
    q.model_name
from q
left join rollup r using (question_id)
