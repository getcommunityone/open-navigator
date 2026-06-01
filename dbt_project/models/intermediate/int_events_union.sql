{{ config(
    materialized='view',
    tags=['intermediate', 'events', 'transcripts']
) }}

/*
Unified candidate list of meeting videos for transcript fetching.

Two feeds, deduped to one row per video_id:

1. `event` production mart — CDP + LocalView meetings. Each already carries a
   canonical event_id and enriched jurisdiction_id, so LocalView rows keep their
   geo. video_id is parsed out of the YouTube URL (or datasource_id fallback).

2. `bronze_event_youtube` — the YouTube catalog, which the event mart does NOT
   surface. This is where CivicSearch meetings promoted in by migration 103 live
   (`datasource = 'civicsearch'`), alongside API-discovered videos
   (`datasource = 'youtube'`). Without this feed the backfill never fetches a
   CivicSearch transcript at all. A video is tagged `civicsearch_school` when its
   id is in `bronze_events_civicsearch_schools`, otherwise `civicsearch`, else
   `youtube_api`.

Each row carries a `source` label and a `source_priority` (1 civicsearch,
2 civicsearch_school, 3 youtube_api, 4 localview) so the backfill can fetch the
most-wanted sources first. On a video_id collision the lowest-priority-number
source wins the row (e.g. a CivicSearch video that also exists in LocalView is
kept as CivicSearch).

Consumed by scrapers.youtube.backfill_transcripts to decide which videos still
need a transcript landed in bronze.bronze_event_youtube_transcript.
*/

{% set youtube_video_id = "REGEXP_REPLACE(REGEXP_REPLACE(video_url, '.*[?&]v=([^&]+).*', '\\1'), '.*youtu\\.be/([^?]+).*', '\\1')" %}

WITH event_mart AS (
    -- Feed 1: CDP + LocalView meetings, with canonical event_id and enriched geo.
    SELECT
        event_id,
        event_date,
        video_url,
        event_title,
        jurisdiction_id,
        jurisdiction_name,
        state_code,
        state,
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

youtube_catalog AS (
    -- Feed 2: CivicSearch (school / general) + API-discovered YouTube videos.
    -- These live only in bronze_event_youtube and never reach the event mart.
    SELECT
        y.id::BIGINT        AS event_id,
        y.event_date,
        y.video_url,
        y.title             AS event_title,
        y.jurisdiction_id,
        y.jurisdiction_name,
        y.state_code,
        y.state,
        CASE
            WHEN y.datasource = 'civicsearch' AND sch.vid_id IS NOT NULL THEN 'civicsearch_school'
            WHEN y.datasource = 'civicsearch'                            THEN 'civicsearch'
            ELSE 'youtube_api'
        END                 AS source,
        NULLIF(TRIM(y.video_id), '') AS video_id
    FROM {{ source('bronze', 'bronze_event_youtube') }} y
    LEFT JOIN (
        SELECT DISTINCT vid_id
        FROM {{ source('bronze', 'bronze_events_civicsearch_schools') }}
        WHERE NULLIF(TRIM(vid_id), '') IS NOT NULL
    ) sch ON sch.vid_id = y.video_id
    WHERE y.video_url IS NOT NULL
),

candidates AS (
    SELECT
        event_id, event_date, video_url, event_title,
        jurisdiction_id, jurisdiction_name, state_code, state, source, video_id
    FROM event_mart
    UNION ALL
    SELECT
        event_id, event_date, video_url, event_title,
        jurisdiction_id, jurisdiction_name, state_code, state, source, video_id
    FROM youtube_catalog
),

ranked AS (
    SELECT
        *,
        CASE source
            WHEN 'civicsearch'        THEN 1
            WHEN 'civicsearch_school' THEN 2
            WHEN 'youtube_api'        THEN 3
            WHEN 'localview'          THEN 4
            ELSE 5
        END AS source_priority
    FROM candidates
    WHERE video_id IS NOT NULL
),

deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY video_id
            -- Keep the most-wanted source on collision; newest meeting as tiebreak.
            ORDER BY source_priority ASC, event_date DESC NULLS LAST
        ) AS dedupe_rank
    FROM ranked
)

SELECT
    event_id,
    event_date,
    video_url,
    event_title,
    jurisdiction_id,
    jurisdiction_name,
    state_code,
    state,
    video_id,
    source,
    source_priority
FROM deduped
WHERE dedupe_rank = 1
