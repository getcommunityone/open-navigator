{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'civicsearch', 'topic'],
        contract={'enforced': true}
    )
}}

/*
public.civicsearch_topic — CivicSearch policy-topic taxonomy.

GRAIN: one row per topic_id. A FLAT topic -> keyword-cluster dictionary (NOT
hierarchical) that CivicSearch uses to tag meeting snippets. keyword_stats is a
JSONB array of the cluster's representative keywords.

SOURCE : staging.stg_civicsearch__topic (bronze.bronze_events_civicsearch_topic).
TARGET : public.civicsearch_topic (served via publish_public_serving).
*/

select
    topic_id::integer       as topic_id,
    name::text              as name,
    query_id::text          as query_id,
    keyword_stats::jsonb    as keyword_stats
from {{ ref('stg_civicsearch__topic') }}
