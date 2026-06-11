-- public.instance_argument — bridge from a question instance to each canonical
-- argument it expressed, preserving the local verbatim excerpt + match score.
select
    instance_argument_id,
    instance_id,
    argument_id,
    verbatim_excerpt,
    source_view,
    match_score
from {{ ref('stg_instance_argument') }}
