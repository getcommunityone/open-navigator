{{
    config(
        materialized='table',
        schema='bronze',
        tags=['bronze', 'youtube', 'events']
    )
}}

-- Bronze YouTube Events Table
-- Purpose: Store raw YouTube video data from government channels
-- Source: Loaded via packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py
-- Target: Can be deployed to local or Neon (cloud) database

-- This model creates the table structure in the target database
-- Data population happens via:
--   1. Local: load_youtube_events_to_postgres.py (ongoing)
--   2. Neon: Initial load via pg_dump/restore or COPY command

SELECT
    -- Primary key
    id,
    
    -- Event identification
    event_id,  -- Generated from video_id hash
    video_id,  -- YouTube video ID (e.g., "dQw4w9WgXcQ")
    
    -- Event details
    event_date,
    event_time,
    title,
    description,
    
    -- Jurisdiction linkage
    jurisdiction_id,
    jurisdiction_name,
    jurisdiction_type,
    city,
    state_code,
    state,
    
    -- Meeting details
    meeting_type,
    location,
    location_description,
    
    -- YouTube channel info
    channel_id,
    channel_url,
    channel_type,
    
    -- Video metadata
    video_url,
    view_count,
    duration_minutes,
    like_count,
    language,
    
    -- Data source tracking
    datasource,  -- Always 'youtube'
    datasource_id,  -- YouTube video ID
    
    -- Publishing metadata
    published_at,  -- When YouTube published the video
    
    -- Audit fields
    loaded_at,
    last_updated

FROM {{ source('bronze', 'bronze_events_youtube') }}

-- Limit 0 to create empty table structure (for initial Neon deployment)
-- Remove this line when syncing data from local to Neon
{% if target.name == 'neon_init' %}
WHERE 1 = 0
{% endif %}
