-- Migration 108: drop redundant denormalized columns from
-- bronze.bronze_event_youtube_transcript
--
-- These columns are pure copies of data that already lives on
-- bronze.bronze_event_youtube and is reachable by joining on video_id
-- (the primary key of both tables). They were backfilled by migrations 098
-- and 102 and kept in sync by the sync_text_ai_geo_from_youtube trigger.
-- Removing them eliminates the duplication: any consumer that needs this
-- metadata joins bronze_event_youtube ON video_id instead (the dbt staging
-- model stg_bronze_event_youtube_transcript does exactly this).
--
-- KEPT (genuinely transcript-specific, NOT on bronze_event_youtube):
--   id, video_id, raw_text, segments, caption_text_timed, language,
--   is_auto_generated, transcript_source, ai_model, ai_extraction_version,
--   has_transcript, transcript_quality, created_at, last_updated,
--   channel_title, place_govt, vid_dislikes, vid_comments, vid_livestreamed
--
-- The geo-sync trigger + function are dropped first: they only existed to
-- mirror state_code/state/jurisdiction_id/jurisdiction_name from the youtube
-- catalog, which is precisely what we are removing.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f packages/hosting/scripts/neon/migrations/108_drop_redundant_transcript_columns.sql

BEGIN;

-- 1. Drop the geo-sync trigger + its function (the columns it syncs are going away)
DROP TRIGGER IF EXISTS trg_sync_text_ai_geo_from_youtube
    ON bronze.bronze_event_youtube_transcript;
DROP FUNCTION IF EXISTS bronze.sync_text_ai_geo_from_youtube();

-- 2. Drop the index on the redundant event_id column
DROP INDEX IF EXISTS bronze.idx_bronze_events_text_ai_event_id;

-- 3. Drop the redundant columns (all fetchable from bronze_event_youtube by video_id)
ALTER TABLE bronze.bronze_event_youtube_transcript
    DROP COLUMN IF EXISTS event_id,
    DROP COLUMN IF EXISTS state_code,
    DROP COLUMN IF EXISTS state,
    DROP COLUMN IF EXISTS jurisdiction_id,
    DROP COLUMN IF EXISTS jurisdiction_name,
    DROP COLUMN IF EXISTS event_date,
    DROP COLUMN IF EXISTS meeting_type,
    DROP COLUMN IF EXISTS title,
    DROP COLUMN IF EXISTS video_url,
    DROP COLUMN IF EXISTS channel_id,
    DROP COLUMN IF EXISTS channel_url,
    DROP COLUMN IF EXISTS channel_type,
    DROP COLUMN IF EXISTS vid_title,
    DROP COLUMN IF EXISTS vid_desc,
    DROP COLUMN IF EXISTS vid_length_min,
    DROP COLUMN IF EXISTS vid_upload_date,
    DROP COLUMN IF EXISTS vid_views,
    DROP COLUMN IF EXISTS vid_likes;

COMMIT;
