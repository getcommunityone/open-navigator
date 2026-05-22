-- Migration: Create bronze_events_channels table
-- Description: Bronze table for YouTube channel data from government jurisdictions
-- Database: open_navigator (bronze schema)
-- Date: 2026-05-06

-- Run this in the open_navigator database
-- psql -h localhost -p 5433 -U postgres -d open_navigator -f 002_create_bronze_events_channels.sql

BEGIN;

-- Create bronze_events_channels table in bronze schema
CREATE TABLE IF NOT EXISTS bronze.bronze_events_channels (
    id SERIAL PRIMARY KEY,
    channel_id VARCHAR(50) UNIQUE NOT NULL,
    channel_url TEXT NOT NULL,
    channel_title VARCHAR(500),
    channel_type VARCHAR(50),
    subscriber_count INTEGER,
    video_count INTEGER,
    
    -- Source tracking
    in_localview BOOLEAN DEFAULT FALSE,
    in_jurisdictions_details BOOLEAN DEFAULT FALSE,
    on_public_website BOOLEAN DEFAULT FALSE,
    in_wikidata BOOLEAN DEFAULT FALSE,
    
    -- Discovery metadata
    discovery_method VARCHAR(100),
    discovery_date TIMESTAMP,
    confidence_score FLOAT,
    
    -- Jurisdiction associations (raw JSONB)
    jurisdictions JSONB,
    
    -- Quality flags
    is_verified BOOLEAN DEFAULT FALSE,
    is_government BOOLEAN DEFAULT NULL,
    flagged_as_junk BOOLEAN DEFAULT FALSE,
    flag_reason TEXT,
    
    -- Metadata
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_bronze_channels_channel_id ON bronze.bronze_events_channels(channel_id);
CREATE INDEX IF NOT EXISTS idx_bronze_channels_in_localview ON bronze.bronze_events_channels(in_localview);
CREATE INDEX IF NOT EXISTS idx_bronze_channels_in_wikidata ON bronze.bronze_events_channels(in_wikidata);
CREATE INDEX IF NOT EXISTS idx_bronze_channels_is_government ON bronze.bronze_events_channels(is_government);
CREATE INDEX IF NOT EXISTS idx_bronze_channels_flagged ON bronze.bronze_events_channels(flagged_as_junk);
CREATE INDEX IF NOT EXISTS idx_bronze_channels_discovery_method ON bronze.bronze_events_channels(discovery_method);
CREATE INDEX IF NOT EXISTS idx_bronze_channels_channel_type ON bronze.bronze_events_channels(channel_type);

-- Add comment
COMMENT ON TABLE bronze.bronze_events_channels IS 'Bronze table for YouTube channels from government jurisdictions - loaded from public.jurisdiction and enriched with LocalView, WikiData validation';

COMMIT;
