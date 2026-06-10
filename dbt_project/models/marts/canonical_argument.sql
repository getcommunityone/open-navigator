-- public.canonical_argument — the recurring "key points" (pro/con) attached to a
-- policy question, built via Key Point Analysis over the decisions' competing_views
-- snippets, each tagged with a Boydstun policy frame.
select
    a.argument_id,
    a.question_id,
    a.stance,
    a.label,
    a.summary,
    a.source_role,
    a.frame_id,
    f.label as frame_label,
    a.member_count,
    a.model_name
from {{ ref('stg_canonical_argument') }} a
left join {{ ref('policy_frame') }} f on f.frame_id = a.frame_id
