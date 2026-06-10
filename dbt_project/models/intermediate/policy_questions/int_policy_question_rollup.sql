-- Per-question comparative rollup: how many jurisdictions faced this question and
-- how they voted. Powers the "32 of 47 jurisdictions approved" surface and the
-- per-outcome breakdown. Grain: one row per question_id.
with inst as (
    select * from {{ ref('stg_question_instance') }}
),
juris as (
    select
        question_id,
        coalesce(state_code, '') || '|' || coalesce(jurisdiction_name, '') as juris_key,
        source_type,
        state_code,
        outcome_normalized
    from inst
)
select
    question_id,
    count(*)                                                             as instances_total,
    count(*) filter (where source_type = 'local_decision')              as decisions_total,
    count(*) filter (where source_type = 'state_bill')                  as bills_total,
    count(distinct juris_key)                                            as jurisdictions_total,
    count(distinct juris_key) filter (where outcome_normalized = 'approved') as jurisdictions_approved,
    count(distinct state_code)                                          as states_total,
    count(*) filter (where outcome_normalized = 'approved')             as approved_count,
    count(*) filter (where outcome_normalized = 'denied')               as denied_count,
    count(*) filter (where outcome_normalized = 'deferred')             as deferred_count,
    count(*) filter (where outcome_normalized = 'other')                as other_count
from juris
group by question_id
