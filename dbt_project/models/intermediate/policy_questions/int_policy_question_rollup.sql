-- Per-question comparative rollup: how many jurisdictions faced this question and
-- how they voted. Powers the "32 of 47 jurisdictions approved" surface and the
-- per-outcome breakdown. Grain: one row per question_id.
--
-- Outcome buckets unify the decision and bill vocabularies into one "outcome
-- family" so cross-level comparison works:
--   approved  = approved (decisions) | enacted (bills)
--   denied    = denied   (decisions) | failed | died_in_committee (bills)
--   deferred  = deferred (decisions) | carried_over (bills)
--   other     = other    (decisions) | pending (bills)
with inst as (
    select * from {{ ref('stg_question_instance') }}
),
-- Real money per instance: a local_decision instance's source_id is the
-- event_decision_id, which carries the (already per-decision, max-not-summed)
-- net_dollar_impact in item_interestingness. Bills carry no dollar impact, so
-- money is a local-decision signal; talk/instances span both sources.
decision_money as (
    select
        i.question_id,
        coalesce(ii.net_dollar_impact, 0)::numeric as net_dollar_impact
    from inst i
    join {{ ref('item_interestingness') }} ii
      on ii.event_decision_id = i.source_id
     and i.source_type = 'local_decision'
),
money as (
    select question_id, sum(net_dollar_impact)::numeric as money_total
    from decision_money
    group by question_id
),
juris as (
    select
        question_id,
        coalesce(state_code, '') || '|' || coalesce(jurisdiction_name, '') as juris_key,
        source_type,
        state_code,
        case
            when outcome_normalized in ('approved', 'enacted') then 'approved'
            when outcome_normalized in ('denied', 'failed', 'died_in_committee') then 'denied'
            when outcome_normalized in ('deferred', 'carried_over') then 'deferred'
            else 'other'
        end as outcome_family
    from inst
)
select
    j.question_id,
    count(*)                                                             as instances_total,
    count(*) filter (where source_type = 'local_decision')              as decisions_total,
    count(*) filter (where source_type = 'state_bill')                  as bills_total,
    count(distinct juris_key)                                            as jurisdictions_total,
    count(distinct juris_key) filter (where outcome_family = 'approved') as jurisdictions_approved,
    count(distinct state_code)                                          as states_total,
    count(*) filter (where outcome_family = 'approved')                 as approved_count,
    count(*) filter (where outcome_family = 'denied')                   as denied_count,
    count(*) filter (where outcome_family = 'deferred')                 as deferred_count,
    count(*) filter (where outcome_family = 'other')                    as other_count,
    coalesce(m.money_total, 0)::numeric                                 as money_total
from juris j
left join money m using (question_id)
group by j.question_id, m.money_total
