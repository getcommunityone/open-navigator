{{
  config(
    materialized='table',
    tags=['marts', 'events', 'transcripts', 'production'],
    unique_key='id',
    indexes=[
      {'columns': ['event_id'], 'type': 'btree'},
      {'columns': ['video_id'], 'unique': True},
      {'columns': ['transcript_source'], 'type': 'btree'}
    ]
  )
}}

/*
Production events_text_search table - Video transcripts for full-text search

This model:
- Joins transcripts to event to get event_id
- Deduplicates by video_id (keeps highest quality)
- Filters for useful transcripts (>100 chars)

Used by: api/routes/search_postgres.py for transcript search

Data Flow:
bronze_events_text_ai → stg_bronze_events_text_ai → events_text_search (this model)
*/

WITH events_with_datasource AS (
    SELECT
        event_id,
        datasource_id,
        video_url,
        -- Extract video_id from YouTube URL if needed
        CASE
            WHEN video_url LIKE '%youtube.com%' OR video_url LIKE '%youtu.be%' 
            THEN REGEXP_REPLACE(
                REGEXP_REPLACE(video_url, '.*[?&]v=([^&]+).*', '\1'),  -- ?v= format
                '.*youtu\.be/([^?]+).*', '\1'  -- youtu.be format
            )
            ELSE NULL
        END AS extracted_video_id
    FROM {{ ref('event') }}
    WHERE video_url IS NOT NULL
),

transcripts_with_quality AS (
    SELECT
        t.*,
        -- Assign quality score
        CASE
            WHEN transcript_quality = 'high' THEN 3
            WHEN transcript_quality = 'medium' THEN 2
            WHEN transcript_quality = 'low' THEN 1
            WHEN is_auto_generated = FALSE THEN 3  -- Manual transcripts are high quality
            WHEN word_count >= 500 THEN 2  -- Substantial auto-generated
            ELSE 1
        END AS quality_score,
        
        -- Rank by quality to keep best transcript per video
        ROW_NUMBER() OVER (
            PARTITION BY video_id
            ORDER BY 
                CASE
                    WHEN transcript_quality = 'high' THEN 3
                    WHEN transcript_quality = 'medium' THEN 2
                    WHEN transcript_quality = 'low' THEN 1
                    WHEN is_auto_generated = FALSE THEN 3
                    WHEN word_count >= 500 THEN 2
                    ELSE 1
                END DESC,
                created_at DESC
        ) AS quality_rank
    FROM {{ ref('stg_bronze_events_text_ai') }} t
    WHERE
        NOT missing_transcript
        AND NOT very_short_transcript  -- Filter out <100 char transcripts
),

-- One (video_id -> event_id) row per key. Unioning the URL-extracted id and the
-- datasource_id lets the transcript join below be a plain equality (hash) join,
-- instead of an OR-join that forced a nested loop over the 150k-row event mart
-- (turning a seconds-long build into 20+ minutes).
event_video_keys AS (
    SELECT DISTINCT ON (vid)
        vid AS video_id,
        event_id
    FROM (
        SELECT extracted_video_id AS vid, event_id
        FROM events_with_datasource
        WHERE extracted_video_id IS NOT NULL
        UNION ALL
        SELECT datasource_id AS vid, event_id
        FROM events_with_datasource
        WHERE datasource_id IS NOT NULL
    ) k
    WHERE vid IS NOT NULL
    ORDER BY vid, event_id
),

transcripts_joined AS (
    SELECT
        t.bronze_transcript_id,
        -- Canonical event_id from the event mart, else the id already on bronze.
        COALESCE(e.event_id, t.event_id) AS event_id,
        t.video_id,
        t.raw_text,
        t.segments,
        t.language,
        t.is_auto_generated,
        t.transcript_source,
        t.created_at
    FROM transcripts_with_quality t
    LEFT JOIN event_video_keys e ON e.video_id = t.video_id
    WHERE t.quality_rank = 1  -- Keep only best transcript per video
)

SELECT
    ROW_NUMBER() OVER (ORDER BY created_at DESC) AS id,
    event_id,
    video_id,
    raw_text,
    segments,
    language,
    is_auto_generated,
    transcript_source,
    created_at

FROM transcripts_joined
WHERE video_id IS NOT NULL
ORDER BY created_at DESC
