with src as (
    select * from {{ source('pq_bronze', 'bronze_question_relation') }}
)
select
    relation_id,
    from_question_id,
    to_question_id,
    relation_type,
    evidence
from src
where relation_id is not null
  and from_question_id is not null
  and to_question_id is not null
