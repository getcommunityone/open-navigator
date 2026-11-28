{{
  config(
    materialized='table',
    tags=['marts', 'topic', 'organization', 'serving'],
    indexes=[{'columns': ['topic_slug', 'state_code'], 'type': 'btree'}]
  )
}}

/*
    How many nonprofits each topic is tied to, per place and method (#1382): the totals behind the Nonprofits screen's
    counts, so they stay true while topic_organization_serving keeps only the strongest 20 per state.
    Grain: one row per (topic_id, state_code, match_method). (A city grain was 68k rows, too big for Neon; a city scope
    counts its served rows and says when that is partial.)

    PK  topic_organization_count_id = md5(topic_id | state_code | match_method). FK topic_id -> civicsearch_topic.
*/

select
    md5(topic_id::text || '|' || state_code || '|' || match_method)::text as topic_organization_count_id,
    topic_id::integer                                                 as topic_id,
    topic_slug::text                                                  as topic_slug,
    state_code::text                                                  as state_code,
    match_method::text                                                as match_method,
    count(*)::integer                                                 as n,
    max(built_at)::timestamptz                                        as built_at
from {{ ref('topic_organization') }}
group by topic_id, topic_slug, state_code, match_method
