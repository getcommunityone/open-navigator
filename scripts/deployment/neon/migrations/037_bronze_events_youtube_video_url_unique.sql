-- Migration: Ensure bronze.bronze_events_youtube.video_url is UNIQUE
--
-- Same canonical URL loaded more than once (e.g. different video_id rows): keep lowest id.
--
-- Apply (example):
--   psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f scripts/deployment/neon/migrations/037_bronze_events_youtube_video_url_unique.sql

BEGIN;

DELETE FROM bronze.bronze_events_youtube a
    USING bronze.bronze_events_youtube b
WHERE a.video_url = b.video_url
  AND a.id > b.id;

ALTER TABLE bronze.bronze_events_youtube
    DROP CONSTRAINT IF EXISTS bronze_events_youtube_video_url_key;

ALTER TABLE bronze.bronze_events_youtube
    DROP CONSTRAINT IF EXISTS unique_video_url;

ALTER TABLE bronze.bronze_events_youtube
    ADD CONSTRAINT bronze_events_youtube_video_url_key UNIQUE (video_url);

COMMIT;
