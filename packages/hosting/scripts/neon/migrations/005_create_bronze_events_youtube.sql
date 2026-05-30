-- Migration: Create bronze_events_youtube table
-- Purpose: Store raw YouTube video data from government channels
-- Date: 2026-05-06
-- Author: System
--
-- Usage:
-- psql -h localhost -p 5433 -U postgres -d open_navigator -f 005_create_bronze_events_youtube.sql

BEGIN;

-- Create bronze_events_youtube table in bronze schema
CREATE TABLE IF NOT EXISTS bronze.bronze_events_youtube (
    -- Primary key
    id SERIAL PRIMARY KEY,
    
    -- Event identification
    event_id INTEGER NOT NULL UNIQUE,  -- Generated from video_id hash
    video_id VARCHAR(64) NOT NULL UNIQUE,  -- YouTube video ID (normally 11 chars, but live/broadcast IDs can be longer)
    
    -- Event details
    event_date DATE,
    event_time TIME,
    title TEXT,
    description TEXT,
    
    -- Jurisdiction linkage
    jurisdiction_id VARCHAR(50),
    jurisdiction_name VARCHAR(200),
    jurisdiction_type VARCHAR(50),
    city VARCHAR(100),
    state_code VARCHAR(2),
    state VARCHAR(50),
    
    -- Meeting details
    meeting_type VARCHAR(100),
    location TEXT,
    location_description TEXT,
    
    -- YouTube channel info
    channel_id VARCHAR(50) NOT NULL,
    channel_url TEXT,
    channel_type VARCHAR(50),
    
    -- Video metadata
    video_url TEXT NOT NULL,
    view_count INTEGER,
    duration_minutes INTEGER,
    like_count INTEGER,
    language VARCHAR(10),
    
    -- Data source tracking
    datasource VARCHAR(100) DEFAULT 'youtube',
    datasource_id VARCHAR(255),  -- Original YouTube video ID
    confidence_score DOUBLE PRECISION,
    
    -- Timestamps
    published_at TIMESTAMP,  -- YouTube publish date
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_bronze_youtube_video_id ON bronze.bronze_events_youtube(video_id);
CREATE INDEX IF NOT EXISTS idx_bronze_youtube_event_id ON bronze.bronze_events_youtube(event_id);
CREATE INDEX IF NOT EXISTS idx_bronze_youtube_channel_id ON bronze.bronze_events_youtube(channel_id);
CREATE INDEX IF NOT EXISTS idx_bronze_youtube_date ON bronze.bronze_events_youtube(event_date);
CREATE INDEX IF NOT EXISTS idx_bronze_youtube_jurisdiction ON bronze.bronze_events_youtube(jurisdiction_name, state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_youtube_city ON bronze.bronze_events_youtube(city, state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_youtube_published ON bronze.bronze_events_youtube(published_at);

-- Add table comment
COMMENT ON TABLE bronze.bronze_events_youtube IS 'Bronze table for YouTube videos from government channels - raw data from YouTube API/yt-dlp';
COMMENT ON COLUMN bronze.bronze_events_youtube.video_id IS 'YouTube video ID (e.g., dQw4w9WgXcQ)';
COMMENT ON COLUMN bronze.bronze_events_youtube.event_id IS 'Generated unique event ID from video_id hash';
COMMENT ON COLUMN bronze.bronze_events_youtube.published_at IS 'Original YouTube publish timestamp (from API)';
COMMENT ON COLUMN bronze.bronze_events_youtube.loaded_at IS 'When this record was first loaded into bronze';

COMMIT;

-- Show table structure
\d bronze.bronze_events_youtube

-- Show row count
SELECT COUNT(*) as total_youtube_events FROM bronze.bronze_events_youtube;
