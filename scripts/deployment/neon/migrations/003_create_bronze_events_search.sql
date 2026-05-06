-- Migration: Create bronze_events_search table
-- Description: Bronze layer for meeting events from LocalView, YouTube, and other sources
-- Target Database: open_navigator_bronze
-- Date: 2026-05-06

-- Run with:
-- psql -h localhost -p 5433 -U postgres -d open_navigator_bronze -f 003_create_bronze_events_search.sql

-- ============================================================================
-- Create bronze_events_search table
-- ============================================================================

CREATE TABLE IF NOT EXISTS bronze_events_search (
    id SERIAL PRIMARY KEY,
    
    -- Event basics
    title TEXT NOT NULL,
    description TEXT,
    event_date DATE,
    event_time TIME,
    
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
    
    -- Documents/links
    agenda_url TEXT,
    minutes_url TEXT,
    video_url TEXT,               -- Will be enforced as unique when loading to production
    
    -- YouTube-specific fields (for source='youtube')
    channel_id VARCHAR(50),       -- YouTube channel ID for per-channel tracking
    channel_url TEXT,             -- YouTube channel URL
    channel_type VARCHAR(50),     -- Type of channel (municipal, county, state, school, etc.)
    view_count INTEGER,           -- Number of views
    duration_minutes INTEGER,     -- Video duration in minutes
    like_count INTEGER,           -- Number of likes
    language VARCHAR(10),         -- Video language (e.g., 'en', 'es', 'fr')
    
    -- Data source tracking
    source VARCHAR(50) NOT NULL DEFAULT 'unknown',  -- 'localview', 'youtube', 'legistar', etc.
    datasource_id VARCHAR(255),   -- Original ID from source system (video_id, event_id, etc.)
    
    -- Metadata
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Indexes for performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_bronze_events_search_date ON bronze_events_search(event_date DESC);
CREATE INDEX IF NOT EXISTS idx_bronze_events_search_state ON bronze_events_search(state_code, state);
CREATE INDEX IF NOT EXISTS idx_bronze_events_search_jurisdiction ON bronze_events_search(jurisdiction_name, state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_events_search_channel ON bronze_events_search(channel_id);
CREATE INDEX IF NOT EXISTS idx_bronze_events_search_source ON bronze_events_search(source);
CREATE INDEX IF NOT EXISTS idx_bronze_events_search_video_url ON bronze_events_search(video_url);
CREATE INDEX IF NOT EXISTS idx_bronze_events_search_datasource_id ON bronze_events_search(datasource_id);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE bronze_events_search IS 'Bronze table for meeting events from LocalView, YouTube, Legistar and other sources. Raw data before deduplication and quality checks.';
COMMENT ON COLUMN bronze_events_search.source IS 'Data source: localview, youtube, legistar, granicus, etc.';
COMMENT ON COLUMN bronze_events_search.datasource_id IS 'Original ID from source system (video_id for YouTube, event_id for Legistar, etc.)';
COMMENT ON COLUMN bronze_events_search.video_url IS 'Video URL - will be deduplicated when loading to production events_search';

-- ============================================================================
-- Import as Foreign Table in Production Database
-- ============================================================================
-- Run this in the open_navigator database to access bronze data via Foreign Data Wrapper:
--
-- IMPORT FOREIGN SCHEMA public
--     LIMIT TO (bronze_events_search)
--     FROM SERVER bronze_server INTO bronze;
