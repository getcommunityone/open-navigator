{{ config(materialized='view') }}

/*
    Staging: CivicSearch policy-topic taxonomy — one row per topic_id.

    Reads bronze.bronze_events_civicsearch_topic (landed VERBATIM by the
    CivicSearch harvest loader). Cleans/types the topic-level columns. This is a
    FLAT topic -> keyword-cluster dictionary (NOT hierarchical). keyword_stats is
    kept as a JSONB array of representative keyword strings. Promoted to the
    public mart civicsearch_topic.

    Template: source -> renamed -> final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_events_civicsearch_topic') }}
),

renamed as (
    select
        topic_id::integer                        as topic_id,
        nullif(trim(name), '')                   as name,
        nullif(trim(query_id), '')               as query_id,
        coalesce(keyword_stats, '[]'::jsonb)     as keyword_stats
    from source
)

select
    topic_id,
    name,
    query_id,
    keyword_stats
from renamed
