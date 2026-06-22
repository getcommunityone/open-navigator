{{
  config(
    materialized='view',
    tags=['staging', 'events', 'transcripts', 'ai']
  )
}}

/*
Staging view for bronze_event_youtube_transcript

Applies basic cleaning and quality checks to video transcripts.
Filters out low-quality or empty transcripts.

Source: bronze_event_youtube_transcript (from `open_navigator.bronze` schema)
Target: Intermediate models for text analysis and search
*/

SELECT
    -- Primary key
    t.id AS bronze_transcript_id,
    
    -- Event linking (event_id now sourced from the youtube catalog via video_id;
    -- migration 108 dropped the redundant copy from the transcript table)
    y.event_id,
    TRIM(t.video_id) AS video_id,
    
    -- Transcript data (cleaned)
    NULLIF(TRIM(t.raw_text), '') AS raw_text,
    t.segments,  -- Keep JSONB as-is

    -- Metadata
    LOWER(TRIM(t.language)) AS language,
    t.is_auto_generated,
    LOWER(TRIM(t.transcript_source)) AS transcript_source,

    -- AI extraction metadata
    NULLIF(TRIM(t.ai_model), '') AS ai_model,
    NULLIF(TRIM(t.ai_extraction_version), '') AS ai_extraction_version,

    -- Quality metrics
    t.has_transcript,
    LOWER(TRIM(t.transcript_quality)) AS transcript_quality,

    -- LocalView meeting / video metadata.
    -- These were redundant copies and are now read from bronze_event_youtube
    -- via the video_id join (migration 108 dropped them from the transcript table).
    y.event_date,
    NULLIF(TRIM(y.meeting_type), '')   AS meeting_type,
    NULLIF(TRIM(y.title), '')          AS title,
    NULLIF(TRIM(y.video_url), '')      AS video_url,
    NULLIF(TRIM(t.place_govt), '')     AS place_govt,
    NULLIF(TRIM(t.channel_title), '')  AS channel_title,
    NULLIF(TRIM(y.title), '')          AS vid_title,
    NULLIF(TRIM(y.description), '')    AS vid_desc,
    y.duration_minutes AS vid_length_min,
    y.published_at     AS vid_upload_date,
    t.vid_livestreamed,
    y.view_count       AS vid_views,
    y.like_count       AS vid_likes,
    t.vid_dislikes,
    t.vid_comments,
    NULLIF(TRIM(y.channel_type), '')   AS channel_type,
    NULLIF(TRIM(y.channel_id), '')     AS channel_id,
    NULLIF(TRIM(y.channel_url), '')    AS channel_url,

    -- Calculate transcript length
    LENGTH(raw_text) AS transcript_length,
    
    -- Calculate word count (approximate)
    CASE 
        WHEN raw_text IS NOT NULL 
        THEN array_length(regexp_split_to_array(TRIM(raw_text), '\s+'), 1)
        ELSE 0 
    END AS word_count,
    
    -- Quality flags
    CASE 
        WHEN raw_text IS NULL OR TRIM(raw_text) = '' THEN TRUE 
        ELSE FALSE 
    END AS missing_transcript,
    
    CASE 
        WHEN LENGTH(raw_text) < 100 THEN TRUE  -- Less than 100 chars likely not useful
        ELSE FALSE 
    END AS very_short_transcript,
    
    CASE
        WHEN segments IS NULL OR jsonb_array_length(segments) = 0 THEN TRUE
        ELSE FALSE
    END AS missing_segments,
    
    -- Timestamps
    t.created_at,
    t.last_updated

FROM {{ source('bronze', 'bronze_event_youtube_transcript') }} t
-- Recover the meeting/video metadata that used to be denormalized onto the
-- transcript row (dropped by migration 108) from the canonical youtube catalog.
LEFT JOIN {{ source('bronze', 'bronze_event_youtube') }} y
    ON y.video_id = t.video_id

-- Basic quality filter: must have video_id and some transcript data.
-- Exclude policy-pipeline rejects (``excluded:non_meeting``, etc.) so promos /
-- news segments never reach events_text_search / event_documents.
WHERE
    t.video_id IS NOT NULL
    AND TRIM(t.video_id) != ''
    AND COALESCE(t.has_transcript, false) = true
    AND LOWER(COALESCE(TRIM(t.transcript_source), '')) NOT LIKE 'excluded:%'
    AND (
        t.raw_text IS NOT NULL
        OR t.segments IS NOT NULL
    )
