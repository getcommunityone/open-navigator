with src as (
    select * from {{ source('pq_bronze', 'bronze_policy_question') }}
)
select
    question_id,
    canonical_text,
    nullif(topic_code, '')      as topic_code,
    primary_theme,
    cofog_code,
    coalesce(scope, 'local')    as scope,
    coalesce(status, 'active')  as status,
    first_seen,
    coalesce(member_count, 0)   as member_count,
    coalesce(aliases, array[]::text[]) as aliases,
    model_name
from src
where question_id is not null
