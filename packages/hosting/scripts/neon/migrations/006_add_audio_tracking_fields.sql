-- Migration: Add audio download tracking fields to bronze_events_youtube
-- Purpose: Track when audio was downloaded and where it's stored
-- Date: 2026-05-06
-- Author: System
--
-- Usage:
-- psql $NEON_DATABASE_URL -f 006_add_audio_tracking_fields.sql

BEGIN;

-- Add columns to track audio downloads
ALTER TABLE bronze.bronze_events_youtube
ADD COLUMN IF NOT EXISTS audio_downloaded_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS audio_file_path VARCHAR(500),
ADD COLUMN IF NOT EXISTS audio_file_size_mb DOUBLE PRECISION;

-- Create index for querying downloaded videos
CREATE INDEX IF NOT EXISTS idx_bronze_youtube_audio_downloaded 
ON bronze.bronze_events_youtube(audio_downloaded_at) 
WHERE audio_downloaded_at IS NOT NULL;

-- Add comments
COMMENT ON COLUMN bronze.bronze_events_youtube.audio_downloaded_at IS 'Timestamp when audio file was downloaded';
COMMENT ON COLUMN bronze.bronze_events_youtube.audio_file_path IS 'Relative path to downloaded audio file (e.g., AL/Mobile_UCxxx/2026-05-01_meeting.opus)';
COMMENT ON COLUMN bronze.bronze_events_youtube.audio_file_size_mb IS 'Size of downloaded audio file in megabytes';

COMMIT;

-- Show updated table structure
\d bronze.bronze_events_youtube

-- Show download statistics
SELECT 
    COUNT(*) FILTER (WHERE audio_downloaded_at IS NOT NULL) as downloaded_count,
    COUNT(*) FILTER (WHERE audio_downloaded_at IS NULL) as not_downloaded_count,
    SUM(audio_file_size_mb) as total_size_mb,
    AVG(audio_file_size_mb) FILTER (WHERE audio_file_size_mb IS NOT NULL) as avg_size_mb
FROM bronze.bronze_events_youtube;
