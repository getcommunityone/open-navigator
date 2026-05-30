-- Migration: Ensure bronze.bronze_events_youtube.video_id is UNIQUE
--
-- load_youtube_events_to_postgres.py uses:
--   ON CONFLICT (video_id) DO UPDATE ...
-- PostgreSQL requires a UNIQUE constraint (or unique index) on (video_id).
--
-- Apply (example):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/025_bronze_events_youtube_video_id_unique.sql

BEGIN;

-- Redundant non-unique index from 005 (unique constraint below covers lookups)
DROP INDEX IF EXISTS bronze.idx_bronze_youtube_video_id;

-- Same video_id loaded more than once: keep the lowest id
DELETE FROM bronze.bronze_events_youtube a
    USING bronze.bronze_events_youtube b
WHERE a.video_id = b.video_id
  AND a.id > b.id;

-- Recreate a stable name whether an older UNIQUE existed or not
ALTER TABLE bronze.bronze_events_youtube
    DROP CONSTRAINT IF EXISTS bronze_events_youtube_video_id_key;

ALTER TABLE bronze.bronze_events_youtube
    ADD CONSTRAINT bronze_events_youtube_video_id_key UNIQUE (video_id);

COMMIT;
