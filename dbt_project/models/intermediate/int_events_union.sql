{{ config(
    materialized='view',
    tags=['intermediate', 'events', 'transcripts']
) }}

/*
Unified candidate list of meeting videos for transcript fetching.

Merges the two event sources that carry YouTube-hosted meeting video URLs:

- `event` (CDP-derived production mart) where source = 'youtube'
- `int_events_localview` (LocalView events) — its `datasource_id` IS the
  YouTube video_id

Deduped to one row per `video_id`, preferring the YouTube source when a video
appears in both (so the canonical `event` event_id is kept).

Consumed by scrapers.youtube.backfill_transcripts to decide which videos still
need a transcript landed in bronze.bronze_events_text_ai. Adding a new event
source here (rather than UNIONing inline in Python) is all that's needed to pull
transcripts for that source.

NOTE: `event_id` is source-local and not a global key — the `event` mart and
LocalView number rows independently. It is carried only as a hint; the
events_text_search mart re-resolves the canonical event_id by joining on
video_id. The durable fix is to promote LocalView events into the `event` mart
so video_url joins resolve there too.
*/

{% set youtube_video_id = "REGEXP_REPLACE(REGEXP_REPLACE(video_url, '.*[?&]v=([^&]+).*', '\\1'), '.*youtu\\.be/([^?]+).*', '\\1')" %}

WITH youtube_events AS (
    SELECT
        event_id,
        video_url,
        event_title,
        jurisdiction_name,
        state_code,
        COALESCE(
            CASE
                WHEN video_url LIKE '%youtube.com%' OR video_url LIKE '%youtu.be%'
                THEN {{ youtube_video_id }}
            END,
            NULLIF(TRIM(datasource_id), '')
        ) AS video_id,
        'youtube' AS source
    FROM {{ ref('event') }}
    WHERE source = 'youtube'
      AND video_url IS NOT NULL
),

localview_events AS (
    SELECT
        event_id,
        video_url,
        title AS event_title,
        jurisdiction_name,
        state_code,
        NULLIF(TRIM(datasource_id), '') AS video_id,
        'localview' AS source
    FROM {{ ref('int_events_localview') }}
    WHERE video_url IS NOT NULL
      AND NULLIF(TRIM(datasource_id), '') IS NOT NULL
),

unioned AS (
    SELECT * FROM youtube_events
    UNION ALL
    SELECT * FROM localview_events
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY video_id
            ORDER BY CASE source WHEN 'youtube' THEN 0 ELSE 1 END
        ) AS dedupe_rank
    FROM unioned
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
