{{ config(materialized='view') }}

/*
    Staging: CivicSearch transcript snippets — one row per (vid_id, snippet).

    Unnests the JSONB `snippets` array landed on bronze.bronze_events_civicsearch.
    Each snippet is a keyword/topic-matched transcript excerpt with a video
    timestamp (seconds). topic_id = -1 means "no CivicSearch topic" and is kept
    NULL here; non-negative ids reference CivicSearch's policy-topic taxonomy.

    Grain: one row per snippet. snippet_seq makes (vid_id, snippet_seq) unique
    and stable for tests/joins. The <mark>…</mark> highlight tags from the API are
    preserved in snippet_text_marked and stripped in snippet_text.
*/

with

source as (
    select
        vid_id,
        location_query_id,
        meeting_date,
        snippets
    from {{ source('bronze', 'bronze_events_civicsearch') }}
    where vid_id is not null
      and snippets is not null
      and jsonb_array_length(snippets) > 0
),

exploded as (
    select
        s.vid_id,
        s.location_query_id,
        s.meeting_date,
        snip.ordinality - 1                              as snippet_seq,
        snip.value ->> 'text'                            as snippet_text_marked,
        (snip.value ->> 'timestamp')::double precision   as timestamp_seconds,
        nullif((snip.value ->> 'topic_id')::int, -1)     as topic_id
    from source s
    cross join lateral jsonb_array_elements(s.snippets)
        with ordinality as snip(value, ordinality)
),

final as (
    select
        vid_id,
        snippet_seq,
        location_query_id,
        meeting_date,
        snippet_text_marked,
        regexp_replace(snippet_text_marked, '</?mark>', '', 'g') as snippet_text,
        timestamp_seconds,
        topic_id,
        current_timestamp as dbt_loaded_at
    from exploded
)

select * from final
