-- Migration: Create bronze_events_cdp table
-- Description: Bronze layer for Council Data Project (CDP) meeting events
--              Compatible with Council Data Project (CDP) backend schema
--              See: https://councildataproject.org/
-- Target Database: open_navigator (bronze schema)
-- Date: 2026-05-06

-- Run with:
-- psql -h localhost -p 5433 -U postgres -d open_navigator -f 003_create_bronze_event.sql

-- NOTE: Table has been renamed from bronze_event to bronze_events_cdp
--       to better reflect its purpose (CDP data only, not general events search)

-- ============================================================================
-- Create bronze_events_cdp table
-- ============================================================================

CREATE TABLE IF NOT EXISTS bronze.bronze_events_cdp (
    id SERIAL PRIMARY KEY,
    
    -- Event basics (CDP-compatible)
    title TEXT NOT NULL,
    description TEXT,
    event_date DATE,
    event_time TIME,
    event_datetime TIMESTAMP,     -- CDP field: combined date+time
    
    -- Meeting Body (CDP concept: City Council, Transportation Committee, etc.)
    body_name VARCHAR(200),       -- CDP body.name: "City Council", "Planning Commission"
    body_description TEXT,        -- CDP body.description
    
    -- Organization/Jurisdiction
    jurisdiction_id VARCHAR(50),
    jurisdiction_name VARCHAR(200),
    jurisdiction_type VARCHAR(50),
    state_code VARCHAR(2),        -- Two-letter state code (e.g., 'AL', 'MA')
    state VARCHAR(50),            -- Full state name (e.g., 'Alabama', 'Massachusetts')
    city VARCHAR(100),
    
    -- Meeting details
    location TEXT,
    location_description TEXT,    -- Location description from YouTube (if available)
    meeting_type VARCHAR(100),
    status VARCHAR(50),
    
    -- Documents/links (CDP uses _uri suffix)
    agenda_url TEXT,              -- CDP: agenda_uri
    minutes_url TEXT,             -- CDP: minutes_uri  
    video_url TEXT,               -- CDP: session.video_uri (will be enforced as unique when loading to production)
    session_content_hash VARCHAR(64),  -- CDP: session.session_content_hash for deduplication
    
    -- YouTube-specific fields (for source='youtube')
    channel_id VARCHAR(50),       -- YouTube channel ID for per-channel tracking
    channel_url TEXT,             -- YouTube channel URL
    channel_type VARCHAR(50),     -- Type of channel (municipal, county, state, school, etc.)
    view_count INTEGER,           -- Number of views
    duration_minutes INTEGER,     -- Video duration in minutes
    like_count INTEGER,           -- Number of likes
    language VARCHAR(10),         -- Video language (e.g., 'en', 'es', 'fr')
    
    -- Data source tracking (CDP-compatible)
    source VARCHAR(50) NOT NULL DEFAULT 'unknown',  -- 'localview', 'youtube', 'legistar', 'granicus', etc.
    datasource_id VARCHAR(255),   -- Original ID from source system (video_id, event_id, etc.)
    external_source_id VARCHAR(255),  -- CDP field: external_source_id for tracking across systems
    
    -- Metadata
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Add new columns if table already exists (for migration from old schema)
-- ============================================================================

ALTER TABLE bronze.bronze_event 
    ADD COLUMN IF NOT EXISTS event_datetime TIMESTAMP,
    ADD COLUMN IF NOT EXISTS body_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS body_description TEXT,
    ADD COLUMN IF NOT EXISTS location_description TEXT,
    ADD COLUMN IF NOT EXISTS status VARCHAR(50),
    ADD COLUMN IF NOT EXISTS session_content_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS external_source_id VARCHAR(255);

-- ============================================================================
-- Indexes for performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_bronze_event_date ON bronze.bronze_event(event_date DESC);
CREATE INDEX IF NOT EXISTS idx_bronze_event_state ON bronze.bronze_event(state_code, state);
CREATE INDEX IF NOT EXISTS idx_bronze_event_jurisdiction ON bronze.bronze_event(jurisdiction_name, state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_event_channel ON bronze.bronze_event(channel_id);
CREATE INDEX IF NOT EXISTS idx_bronze_event_source ON bronze.bronze_event(source);
CREATE INDEX IF NOT EXISTS idx_bronze_event_video_url ON bronze.bronze_event(video_url);
CREATE INDEX IF NOT EXISTS idx_bronze_event_datasource_id ON bronze.bronze_event(datasource_id);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE bronze.bronze_event IS 'Bronze table for meeting events from LocalView, YouTube, Legistar and other sources. Raw data before deduplication and quality checks. Schema compatible with Council Data Project (CDP) backend: https://councildataproject.org/';
COMMENT ON COLUMN bronze.bronze_event.source IS 'Data source: localview, youtube, legistar, granicus, etc.';
COMMENT ON COLUMN bronze.bronze_event.datasource_id IS 'Original ID from source system (video_id for YouTube, event_id for Legistar, etc.)';
COMMENT ON COLUMN bronze.bronze_event.external_source_id IS 'CDP external_source_id field for cross-system tracking';
COMMENT ON COLUMN bronze.bronze_event.event_datetime IS 'CDP event_datetime field (combined date+time)';
COMMENT ON COLUMN bronze.bronze_event.body_name IS 'CDP body.name: meeting body like "City Council" or "Planning Commission"';
COMMENT ON COLUMN bronze.bronze_event.video_url IS 'Video URL - will be deduplicated when loading to production event';

-- ============================================================================
-- Import as Foreign Table in Production Database
-- ============================================================================
-- Run this in the open_navigator database to access bronze data via Foreign Data Wrapper:
--
-- IMPORT FOREIGN SCHEMA public
--     LIMIT TO (bronze_event)
--     FROM SERVER bronze_server INTO bronze;
