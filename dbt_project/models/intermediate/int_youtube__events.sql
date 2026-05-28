{{ config(
    materialized='view',
    tags=['intermediate', 'youtube', 'events']
) }}

/*
LocalView-enriched YouTube meeting events — one row per video_id.

Declarative replacement for the in-place UPDATE in
packages/scrapers/src/scrapers/youtube/sync_bronze_youtube_from_localview.py. Rather than
mutating bronze.bronze_events_youtube, the enrichment is derived here as a SELECT
on top of stg_youtube__event (which already dedups to one row per video_id and
parses event_date / channel_type from the raw bronze landing).

Geography (jurisdiction_name/type, city, state_code, state, meeting_type) is
taken from LocalView when that source carries a non-blank value for the matching
video (lv.datasource_id = video_id, datasource = 'localview'), otherwise the
value already on the YouTube row — mirroring the script's COALESCE(localview,
youtube) precedence.

channel_id comes from the LocalView→YouTube channel map
(intermediate.int_localview_youtube_video_channels, same table int_events_localview
joins) when present, else the YouTube row; channel_url falls back to the canonical
channel URL when blank.
*/

with

youtube as (
    select * from {{ ref('stg_youtube__event') }}
),

localview as (
    select
        nullif(trim(datasource_id), '')      as video_id,
        nullif(trim(jurisdiction_name), '')  as jurisdiction_name,
        nullif(trim(jurisdiction_type), '')  as jurisdiction_type,
        nullif(trim(city_name), '')          as city,
        upper(nullif(trim(state_code), ''))  as state_code,
        nullif(trim(state), '')              as state,
        nullif(trim(meeting_type), '')       as meeting_type
    from {{ source('bronze', 'bronze_events_localview') }}
    where datasource = 'localview'
      and nullif(trim(datasource_id), '') is not null
),

-- Collapse to one LocalView row per video; keep any non-null attribute.
localview_by_video as (
    select
        video_id,
        max(jurisdiction_name) as jurisdiction_name,
        max(jurisdiction_type) as jurisdiction_type,
        max(city)              as city,
        max(state_code)        as state_code,
        max(state)             as state,
        max(meeting_type)      as meeting_type
    from localview
    group by video_id
),

channel_map as (
    select
        video_id,
        max(nullif(trim(channel_id), '')) as channel_id
    from intermediate.int_localview_youtube_video_channels
    where nullif(trim(channel_id), '') is not null
    group by video_id
),

final as (
    select
        y.video_id,
        y.event_id,
        y.title,
        y.description,
        y.event_date,
        y.published_at,
        y.jurisdiction_id,
        coalesce(lv.jurisdiction_name, y.jurisdiction_name) as jurisdiction_name,
        coalesce(lv.jurisdiction_type, y.jurisdiction_type) as jurisdiction_type,
        coalesce(lv.city, y.city)                           as city,
        coalesce(lv.state_code, y.state_code)               as state_code,
        coalesce(lv.state, y.state)                         as state,
        coalesce(cm.channel_id, y.channel_id)               as channel_id,
        coalesce(
            y.channel_url,
            case
                when coalesce(cm.channel_id, y.channel_id) is not null
                then 'https://www.youtube.com/channel/' || coalesce(cm.channel_id, y.channel_id)
            end
        )                                                   as channel_url,
        y.channel_type,
        coalesce(lv.meeting_type, y.meeting_type)           as meeting_type,
        y.video_url,
        y.location_description,
        y.view_count,
        y.duration_minutes,
        y.like_count,
        y.language,
        y.datasource,
        y.datasource_id,
        (lv.video_id is not null)                           as localview_enriched,
        y.source_ingested_at,
        current_timestamp                                   as dbt_loaded_at
    from youtube y
    left join localview_by_video lv on lv.video_id = y.video_id
    left join channel_map cm on cm.video_id = y.video_id
)

select * from final
