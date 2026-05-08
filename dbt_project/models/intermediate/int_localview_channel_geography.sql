{{ config(
    materialized='table',
    tags=['intermediate', 'localview', 'channels']
) }}

/*
Connect LocalView-derived channels to jurisdiction geography.

Inputs:
- bronze.bronze_events_localview: LocalView events containing jurisdiction_name/state_code + datasource_id (video id)
- intermediate.int_localview_youtube_video_channels: video_id -> channel_id mapping (YouTube API backfill)
- intermediate.int_localview_jurisdiction_geography: jurisdiction_name/state -> place_geoid + county_geoids

Output grain:
- one row per (channel_id, state_code, place_name_clean) with best-effort place+county mapping
*/

WITH localview_event_channels AS (
    SELECT DISTINCT
        e.state_code,
        e.jurisdiction_name AS place_name_raw,
        m.channel_id
    FROM {{ source('bronze', 'bronze_events_localview') }} e
    JOIN intermediate.int_localview_youtube_video_channels m
      ON e.datasource_id = m.video_id
    WHERE e.datasource = 'localview'
      AND e.state_code IS NOT NULL
      AND e.jurisdiction_name IS NOT NULL
      AND m.channel_id IS NOT NULL
      AND m.channel_id != ''
),

juris_geo AS (
    SELECT
        state_code,
        place_name_raw,
        place_name_clean,
        place_geoid,
        school_district_geoid,
        township_geoid,
        matched_type,
        primary_county_geoid,
        county_geoids
    FROM {{ ref('int_localview_jurisdiction_geography') }}
)

SELECT
    lec.channel_id,
    lec.state_code,
    jg.place_name_raw,
    jg.place_name_clean,
    jg.matched_type,
    jg.place_geoid,
    jg.school_district_geoid,
    jg.township_geoid,
    jg.primary_county_geoid,
    jg.county_geoids
FROM localview_event_channels lec
LEFT JOIN juris_geo jg
  ON lec.state_code = jg.state_code
 AND lec.place_name_raw = jg.place_name_raw

