-- public.policy_question_relation — cross-level edges between policy questions.
-- from_question_id (typically a state-bill question) relates to to_question_id
-- (typically a local-decision question): preempts | implements | related.
select
    relation_id,
    from_question_id,
    to_question_id,
    relation_type,
    evidence
from {{ ref('stg_question_relation') }}
