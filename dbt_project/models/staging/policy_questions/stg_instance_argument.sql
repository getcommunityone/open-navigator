with src as (
    select * from {{ source('pq_bronze', 'bronze_instance_argument') }}
)
select
    instance_argument_id,
    instance_id,
    argument_id,
    verbatim_excerpt,
    source_view,
    match_score
from src
where instance_argument_id is not null
