-- public.question_instance — polymorphic bridge: each local decision (and, Phase 2,
-- state bill) that is an instance of a policy question, with its normalized outcome.
-- source_type in ('local_decision','state_bill'); source_id is the decision/bill id.
select
    instance_id,
    question_id,
    source_type,
    source_id,
    state_code,
    jurisdiction_name,
    city,
    outcome_raw,
    outcome_normalized,
    occurred_at,
    session,
    assign_score
from {{ ref('stg_question_instance') }}
