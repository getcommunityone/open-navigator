-- public.policy_question_trend — per-question quarterly history. Grain: one row
-- per (question_id, quarter). Powers the registry drill-down's "last four years"
-- chart: how often a question came up each quarter (instances) and the real
-- dollars its local decisions moved that quarter (money).
--
-- All real: instances from stg_question_instance.occurred_at; money from the
-- item_interestingness.net_dollar_impact of the linked event_decision (same
-- join as int_policy_question_rollup). Bills contribute to instances, not money.
-- Quarters with no activity are simply absent (the API/UI zero-fill a fixed
-- window) — we never fabricate empty rows with invented numbers.
{{ config(materialized='table', tags=['marts', 'policy-questions'], contract={'enforced': True}) }}

with inst as (
    select
        question_id,
        source_type,
        source_id,
        occurred_at
    from {{ ref('stg_question_instance') }}
    where occurred_at is not null
),
joined as (
    select
        i.question_id,
        date_trunc('quarter', i.occurred_at)::date as quarter_start,
        coalesce(ii.net_dollar_impact, 0)::numeric as net_dollar_impact
    from inst i
    left join {{ ref('item_interestingness') }} ii
      on ii.event_decision_id = i.source_id
     and i.source_type = 'local_decision'
)
select
    md5(question_id || '|' || quarter_start::text) as trend_id,
    question_id,
    quarter_start,
    count(*)::integer              as instances,
    sum(net_dollar_impact)::numeric as money
from joined
group by question_id, quarter_start
