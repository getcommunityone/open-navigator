{{ config(
    materialized='view',
    tags=['intermediate', 'events', 'transcripts']
) }}

/*
Unified candidate list of meeting videos for transcript fetching.

Reads the `event` production mart, which already unions every event source that
carries a meeting video — CDP/YouTube events plus LocalView meetings promoted in
by marts.event (deduped by video_url, CDP winning collisions). Each row therefore
already carries a canonical `event_id`; this model just narrows to rows with a
fetchable YouTube video, derives the `video_id`, and dedups to one row per
video_id.

Consumed by scrapers.youtube.backfill_transcripts to decide which videos still
need a transcript landed in bronze.bronze_events_text_ai. To pull transcripts for
a new source, add that source to marts.event — it flows through here for free.
*/

{% set youtube_video_id = "REGEXP_REPLACE(REGEXP_REPLACE(video_url, '.*[?&]v=([^&]+).*', '\\1'), '.*youtu\\.be/([^?]+).*', '\\1')" %}

WITH events AS (
    SELECT
        event_id,
        video_url,
        event_title,
        jurisdiction_name,
        state_code,
        source,
        COALESCE(
            -- Primary: parse the video_id out of the YouTube URL.
            CASE
                WHEN video_url LIKE '%youtube.com%' OR video_url LIKE '%youtu.be%'
                THEN {{ youtube_video_id }}
            END,
            -- Fallback: for sources whose datasource_id IS the video_id.
            CASE
                WHEN source IN ('youtube', 'localview')
                THEN NULLIF(TRIM(datasource_id), '')
            END
        ) AS video_id
    FROM {{ ref('event') }}
    WHERE video_url IS NOT NULL
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY video_id
            ORDER BY CASE source WHEN 'youtube' THEN 0 ELSE 1 END
        ) AS dedupe_rank
    FROM events
    WHERE video_id IS NOT NULL
)

SELECT
    event_id,
    video_url,
    event_title,
    jurisdiction_name,
    state_code,
    video_id,
    source
FROM deduped
WHERE dedupe_rank = 1
