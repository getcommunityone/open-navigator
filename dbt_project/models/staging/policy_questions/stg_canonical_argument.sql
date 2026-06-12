with src as (
    select * from {{ source('pq_bronze', 'bronze_canonical_argument') }}
)
select
    argument_id,
    question_id,
    lower(nullif(stance, ''))       as stance,
    label,
    summary,
    lower(nullif(source_role, ''))  as source_role,
    coalesce(nullif(frame_id, ''), 'other') as frame_id,
    coalesce(member_count, 0)       as member_count,
    model_name
from src
where argument_id is not null
  and question_id is not null
