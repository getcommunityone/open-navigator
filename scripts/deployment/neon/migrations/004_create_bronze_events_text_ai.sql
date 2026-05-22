-- Migration: Create bronze_events_text_ai table
-- Description: Bronze layer for video transcripts and AI-extracted meeting text
-- Target Database: open_navigator_bronze
-- Date: 2026-05-06

-- Run with:
-- psql -h localhost -p 5433 -U postgres -d open_navigator_bronze -f 004_create_bronze_events_text_ai.sql

-- ============================================================================
-- Create bronze_events_text_ai table
-- ============================================================================

CREATE TABLE IF NOT EXISTS bronze.bronze_events_text_ai (
    id SERIAL PRIMARY KEY,
    
    -- Link to event (will join to bronze_event.datasource_id or production event.id)
    event_id INTEGER,             -- Foreign key to production event (if loaded)
    video_id VARCHAR(20) NOT NULL,  -- YouTube video ID (unique identifier)
    
    -- Transcript data
    raw_text TEXT,                -- Full transcript as plain text
    segments JSONB,               -- Structured transcript with timestamps
                                  -- Format: [{"text": "...", "start": 0.0, "duration": 2.5}, ...]
    
    -- Transcript metadata
    language VARCHAR(10),         -- Transcript language (e.g., 'en', 'es', 'fr')
    is_auto_generated BOOLEAN DEFAULT FALSE,  -- True if auto-generated captions
    transcript_source VARCHAR(50),  -- Source of transcript: 'youtube_api', 'youtube_manual', 'whisper_ai', etc.
    
    -- AI extraction metadata
    ai_model VARCHAR(100),        -- AI model used for extraction (e.g., 'gemini-1.5-flash')
    ai_extraction_version VARCHAR(20),  -- Version of extraction logic
    
    -- Data quality flags
    has_transcript BOOLEAN DEFAULT FALSE,
    transcript_quality VARCHAR(20),  -- 'high', 'medium', 'low' based on completeness and accuracy
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Indexes for performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_bronze_events_text_ai_event_id ON bronze.bronze_events_text_ai(event_id);
CREATE INDEX IF NOT EXISTS idx_bronze_events_text_video_id ON bronze.bronze_events_text_ai(video_id);
CREATE INDEX IF NOT EXISTS idx_bronze_events_text_source ON bronze.bronze_events_text_ai(transcript_source);
CREATE INDEX IF NOT EXISTS idx_bronze_events_text_quality ON bronze.bronze_events_text_ai(has_transcript, transcript_quality);

-- Full-text search index on transcript
CREATE INDEX IF NOT EXISTS idx_bronze_events_text_search_gin 
    ON bronze.bronze_events_text_ai USING GIN (to_tsvector('english', COALESCE(raw_text, '')));

-- ============================================================================
-- Constraints
-- ============================================================================

-- Unique constraint on video_id to prevent duplicate transcripts
CREATE UNIQUE INDEX IF NOT EXISTS idx_bronze_events_text_video_id_unique ON bronze.bronze_events_text_ai(video_id);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE bronze.bronze_events_text_ai IS 'Bronze table for video transcripts and AI-extracted meeting text from YouTube and other sources.';
COMMENT ON COLUMN bronze.bronze_events_text_ai.video_id IS 'YouTube video ID (unique identifier)';
COMMENT ON COLUMN bronze.bronze_events_text_ai.segments IS 'Structured transcript with timestamps: [{"text": "...", "start": 0.0, "duration": 2.5}, ...]';
COMMENT ON COLUMN bronze.bronze_events_text_ai.transcript_source IS 'Source: youtube_api, youtube_manual, whisper_ai, gemini_ai, etc.';
COMMENT ON COLUMN bronze.bronze_events_text_ai.ai_model IS 'AI model used: gemini-1.5-flash, gpt-4, claude-3, etc.';

-- ============================================================================
-- Import as Foreign Table in Production Database
-- ============================================================================
-- Run this in the open_navigator database to access bronze data via Foreign Data Wrapper:
--
-- IMPORT FOREIGN SCHEMA public
--     LIMIT TO (bronze_events_text_ai)
--     FROM SERVER bronze_server INTO bronze;
