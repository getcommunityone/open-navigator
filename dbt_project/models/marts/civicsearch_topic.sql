{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'civicsearch', 'topic'],
        contract={'enforced': true}
    )
}}

/*
public.civicsearch_topic — policy-topic taxonomy: the CivicSearch topics plus the
hand-authored curated topics (source = 'curated', topic_id >= 100000; issue #500,
e.g. "Data centers").

GRAIN: one row per topic_id. A FLAT topic -> keyword-cluster dictionary (NOT
hierarchical) that CivicSearch uses to tag meeting snippets. keyword_stats is a
JSONB array of the cluster's representative keywords.

SOURCE : staging.stg_civicsearch__topic (bronze.bronze_events_civicsearch_topic
        unioned with the curated_topics seed).
        transcript_occurrences counts staging.stg_civicsearch__snippet per topic_id,
        so it is 0 for curated topics (CivicSearch never tagged them). Their real
        meeting counts come from the keyword models (browse_transcript_count /
        browse_entity_state_transcript_count, topic_transcript_link).
TARGET : public.civicsearch_topic (served via publish_public_serving).
*/

with snippet_occurrences as (
    select
        topic_id,
        count(*)::integer as transcript_occurrences
    from {{ ref('stg_civicsearch__snippet') }}
    where topic_id is not null
    group by topic_id
)

select
    t.topic_id::integer                         as topic_id,
    t.name::text                                as name,
    t.query_id::text                            as query_id,
    t.keyword_stats::jsonb                      as keyword_stats,
    coalesce(o.transcript_occurrences, 0)::integer as transcript_occurrences,
    -- Appended last so publish_public_serving's CREATE OR REPLACE VIEW can add it.
    t.source::text                              as source
from {{ ref('stg_civicsearch__topic') }} t
left join snippet_occurrences o
    on o.topic_id = t.topic_id
