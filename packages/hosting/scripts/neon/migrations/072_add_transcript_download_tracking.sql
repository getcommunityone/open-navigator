-- Migration: Add transcript download tracking fields to bronze_events_youtube
-- Purpose: Track caption download time, cache file path/size, and last error
-- Date: 2026-05-25
--
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/072_add_transcript_download_tracking.sql

BEGIN;

ALTER TABLE bronze.bronze_events_youtube
ADD COLUMN IF NOT EXISTS transcript_download_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS transcript_file_path VARCHAR(500),
ADD COLUMN IF NOT EXISTS transcript_file_size BIGINT,
ADD COLUMN IF NOT EXISTS transcript_file_error TEXT;

CREATE INDEX IF NOT EXISTS idx_bronze_youtube_transcript_downloaded
ON bronze.bronze_events_youtube (transcript_download_at)
WHERE transcript_download_at IS NOT NULL;

COMMENT ON COLUMN bronze.bronze_events_youtube.transcript_download_at IS
    'Timestamp when caption/transcript was last downloaded to policy cache';
COMMENT ON COLUMN bronze.bronze_events_youtube.transcript_file_path IS
    'Repo-relative path to main transcript JSON (e.g. data/cache/gemini_transcript_policy/GA/county/foo_13001/UCxxx/01_transcripts/2024-01-01_meeting.json)';
COMMENT ON COLUMN bronze.bronze_events_youtube.transcript_file_size IS
    'Size in bytes of the main transcript JSON file';
COMMENT ON COLUMN bronze.bronze_events_youtube.transcript_file_error IS
    'Last caption download failure message; NULL on success';

COMMIT;
