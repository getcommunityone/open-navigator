{{ config(
    materialized='view',
    tags=['intermediate', 'civicsearch', 'events']
) }}

/*
Intermediate model: bridge CivicSearch meetings to the unified event spine.

CivicSearch meetings ARE YouTube videos (vid_id == int_events_union.video_id).
This model joins the two on that id so downstream marts can attach CivicSearch's
policy-topic tags + transcript snippets to an existing event, and so we can see
which CivicSearch meetings are NOT yet represented in int_events_union (i.e.
LocalView/YouTube ingest missed them).

Grain: one row per CivicSearch meeting (vid_id). `is_in_event_union` is the
match flag; the int_events_union columns are NULL for unmatched meetings.
*/

with

civicsearch as (
    select * from {{ ref('stg_civicsearch__event') }}
),

events as (
    select
        video_id,
        event_id,
        event_date,
        event_title,
        jurisdiction_id,
        jurisdiction_name,
        state_code,
        state,
        source as event_source
    from {{ ref('int_events_union') }}
),

joined as (
    select
        cs.vid_id,
        cs.title                              as civicsearch_title,
        cs.meeting_date,
        cs.location                           as civicsearch_location,
        cs.location_query_id,
        cs.youtube_url,
        cs.num_snippets,
        cs.num_topics,
        cs.topic_ids,

        (ev.video_id is not null)             as is_in_event_union,
        ev.event_id,
        ev.event_date,
        ev.event_title,
        ev.jurisdiction_id,
        ev.jurisdiction_name,
        ev.state_code,
        ev.state,
        ev.event_source,

        current_timestamp                     as dbt_loaded_at
    from civicsearch cs
    left join events ev
        on cs.vid_id = ev.video_id
)

select * from joined
