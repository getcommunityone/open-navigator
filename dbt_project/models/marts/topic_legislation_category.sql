{{ config(materialized='table') }}

/*
    Mart: topic_legislation_category (#1274) — the category vocabulary each curated topic's state bills
    use. One row per (topic_id, category). A topic with its own rows in the topic_legislation_vocabulary seed gets
    those (water fluoridation: ban / restriction / protection; data centers: restrict / incentive / protect);
    every other curated topic gets the generic '*' set (restrict / support / other). New topics in the
    curated_topics seed are covered with no code change.
*/

with

topics as (
    select topic_id::integer as topic_id, query_id::text as topic_query_id
    from {{ ref('curated_topics') }}
),

vocab as (
    select * from {{ ref('topic_legislation_vocabulary') }}
)

select
    t.topic_id::integer         as topic_id,
    t.topic_query_id::text      as topic_query_id,
    v.category::text            as category,
    v.display_order::integer    as display_order,
    v.label::text               as label,
    v.description::text         as description,
    (v.topic_query_id = '*')    as is_generic
from topics t
join vocab v
  on v.topic_query_id = case
        when exists (select 1 from vocab o where o.topic_query_id = t.topic_query_id) then t.topic_query_id
        else '*'
     end
