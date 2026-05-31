{{ config(
    materialized='view',
    tags=['intermediate', 'localview', 'events']
) }}

/*
Intermediate model: LocalView events with derived channel_id and jurisdiction_id.

`bronze_events_localview` should not carry derived identifiers (medallion: no
SQL/geo logic in the Python loader). This model ties each event to:

- `channel_id`, joining:
    - `intermediate.int_localview_youtube_video_channels` (video_id → channel_id) when present
    - fallback: `bronze_events_youtube` (video_id → channel_id) when available

- `jurisdiction_id` (canonical `{place_slug}_{geoid}`), resolved per event from
  `int_localview_jurisdiction_geography` (place_name + state → typed GEOID) joined
  to `int_jurisdictions` on (state_code, geoid, jurisdiction_type). Events whose
  place did not resolve to a GEOID keep `jurisdiction_id` NULL.
*/

WITH geo AS (
    -- Collapse the per-tier GEOID columns into a single typed GEOID per place.
    SELECT
        state_code,
        place_name_raw,
        matched_type,
        CASE matched_type
            WHEN 'municipality'    THEN place_geoid
            WHEN 'school_district' THEN school_district_geoid
            WHEN 'township'        THEN township_geoid
            WHEN 'county'          THEN primary_county_geoid
        END AS geoid
    FROM {{ ref('int_localview_jurisdiction_geography') }}
),

geo_resolved AS (
    -- Resolve the typed GEOID to a canonical jurisdiction_id (1 row per place).
    SELECT
        g.state_code,
        g.place_name_raw,
        g.matched_type,
        g.geoid,
        j.jurisdiction_id
    FROM geo g
    JOIN {{ ref('int_jurisdictions') }} j
        ON j.state_code        = g.state_code
       AND j.geoid             = g.geoid
       AND j.jurisdiction_type = g.matched_type
    WHERE g.geoid IS NOT NULL
)

SELECT
    e.event_id,
    e.event_date,
    e.jurisdiction_name,
    e.jurisdiction_type,
    e.city_name,
    e.state_code,
    e.state,
    e.meeting_type,
    e.title,
    e.video_url,
    COALESCE(m.channel_id, y.channel_id) AS channel_id,
    e.channel_type,
    gr.jurisdiction_id,
    gr.geoid        AS jurisdiction_geoid,
    gr.matched_type AS jurisdiction_match_type,
    -- Video metrics (carried from bronze for the event mart). The parquet has
    -- a handful of non-finite floats (NaN/Inf) — null them so bigint casts
    -- downstream don't overflow.
    e.vid_desc AS description,
    CASE WHEN e.vid_views      IN ('NaN','Infinity','-Infinity') THEN NULL ELSE e.vid_views      END AS view_count,
    CASE WHEN e.vid_length_min IN ('NaN','Infinity','-Infinity') THEN NULL ELSE e.vid_length_min END AS duration_minutes,
    CASE WHEN e.vid_likes      IN ('NaN','Infinity','-Infinity') THEN NULL ELSE e.vid_likes      END AS like_count,
    e.datasource,
    e.datasource_id,
    e.loaded_at
FROM {{ source('bronze', 'bronze_events_localview') }} e
LEFT JOIN intermediate.int_localview_youtube_video_channels m
    ON e.datasource_id = m.video_id
LEFT JOIN {{ source('bronze', 'bronze_events_youtube') }} y
    ON e.datasource_id = y.video_id
LEFT JOIN geo_resolved gr
    ON gr.state_code     = e.state_code
   AND gr.place_name_raw = e.jurisdiction_name
