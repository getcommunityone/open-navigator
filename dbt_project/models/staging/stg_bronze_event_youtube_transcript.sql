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
    id AS bronze_transcript_id,
    
    -- Event linking
    event_id,
    TRIM(video_id) AS video_id,
    
    -- Transcript data (cleaned)
    NULLIF(TRIM(raw_text), '') AS raw_text,
    segments,  -- Keep JSONB as-is
    
    -- Metadata
    LOWER(TRIM(language)) AS language,
    is_auto_generated,
    LOWER(TRIM(transcript_source)) AS transcript_source,
    
    -- AI extraction metadata
    NULLIF(TRIM(ai_model), '') AS ai_model,
    NULLIF(TRIM(ai_extraction_version), '') AS ai_extraction_version,
    
    -- Quality metrics
    has_transcript,
    LOWER(TRIM(transcript_quality)) AS transcript_quality,

    -- LocalView meeting / video metadata (backfilled by migration 098)
    event_date,
    NULLIF(TRIM(meeting_type), '')   AS meeting_type,
    NULLIF(TRIM(title), '')          AS title,
    NULLIF(TRIM(video_url), '')      AS video_url,
    NULLIF(TRIM(place_govt), '')     AS place_govt,
    NULLIF(TRIM(channel_title), '')  AS channel_title,
    NULLIF(TRIM(vid_title), '')      AS vid_title,
    NULLIF(TRIM(vid_desc), '')       AS vid_desc,
    vid_length_min,
    vid_upload_date,
    vid_livestreamed,
    vid_views,
    vid_likes,
    vid_dislikes,
    vid_comments,
    NULLIF(TRIM(channel_type), '')   AS channel_type,
    NULLIF(TRIM(channel_id), '')     AS channel_id,
    NULLIF(TRIM(channel_url), '')    AS channel_url,

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
    created_at,
    last_updated

FROM {{ source('bronze', 'bronze_event_youtube_transcript') }}

-- Basic quality filter: must have video_id and some transcript data
WHERE 
    video_id IS NOT NULL 
    AND TRIM(video_id) != ''
    AND (
        raw_text IS NOT NULL 
        OR segments IS NOT NULL
    )
