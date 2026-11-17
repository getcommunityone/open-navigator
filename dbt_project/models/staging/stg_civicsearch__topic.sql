{{ config(materialized='view') }}

/*
    Staging: policy-topic taxonomy — one row per topic_id.

    Two sources, unioned so every downstream topic model treats them alike:
      * 'civicsearch' — bronze.bronze_events_civicsearch_topic (landed VERBATIM
        by the CivicSearch harvest loader). keyword_stats is CivicSearch's JSONB
        array of representative keyword strings.
      * 'curated'     — the hand-authored curated_topics seed (issue #500, e.g.
        "Data centers"). Its pipe-delimited `keywords` become the same JSONB
        keyword_stats array. Curated topic_ids start at 100000, so they can never
        collide with a CivicSearch id (documented in seeds/schema.yml).

    `source` lets the keyword-matching models apply the right precision rule:
    CivicSearch vocabularies are generic and need >= 2 distinct phrase hits;
    curated keywords are specific and count at 1 hit.

    This is a FLAT topic -> keyword-cluster dictionary (NOT hierarchical).
    Promoted to the public mart civicsearch_topic.

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
        coalesce(keyword_stats, '[]'::jsonb)     as keyword_stats,
        'civicsearch'::text                      as source
    from source
),

curated as (
    select
        c.topic_id::integer                      as topic_id,
        nullif(trim(c.name), '')                 as name,
        nullif(trim(c.query_id), '')             as query_id,
        coalesce(
            (
                select jsonb_agg(trim(k) order by ord)
                from unnest(string_to_array(c.keywords, '|')) with ordinality as u(k, ord)
                where trim(coalesce(k, '')) <> ''
            ),
            '[]'::jsonb
        )                                        as keyword_stats,
        'curated'::text                          as source
    from {{ ref('curated_topics') }} c
),

unioned as (
    select * from renamed
    union all
    select * from curated
)

select
    topic_id,
    name,
    query_id,
    keyword_stats,
    source
from unioned
