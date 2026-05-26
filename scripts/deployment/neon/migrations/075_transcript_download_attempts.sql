-- Migration: Track caption download attempt count on bronze_events_youtube
-- Purpose: Prefer never-tried videos before retries; surface attempt count in ops
-- Date: 2026-05-26
--
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/075_transcript_download_attempts.sql

BEGIN;

ALTER TABLE bronze.bronze_events_youtube
ADD COLUMN IF NOT EXISTS transcript_download_attempts INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN bronze.bronze_events_youtube.transcript_download_attempts IS
    'Number of caption download attempts (success or failure); 0 = never tried';

-- Rows already touched before this column existed count as one attempt.
UPDATE bronze.bronze_events_youtube
SET transcript_download_attempts = 1
WHERE transcript_download_at IS NOT NULL
  AND transcript_download_attempts = 0;

CREATE INDEX IF NOT EXISTS idx_bronze_youtube_transcript_attempts
ON bronze.bronze_events_youtube (jurisdiction_id, transcript_download_attempts)
WHERE transcript_download_attempts > 0;

COMMIT;
