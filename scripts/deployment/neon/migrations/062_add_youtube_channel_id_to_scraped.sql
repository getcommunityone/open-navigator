-- Migration 062: store resolved UC channel id on scraped jurisdiction rows.
--
-- ``youtube_channel_url`` may be an @handle; after resolution we persist
-- ``youtube_channel_id`` and canonical ``https://www.youtube.com/channel/UC…`` URL.

BEGIN;

ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    ADD COLUMN IF NOT EXISTS youtube_channel_id TEXT;

ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    ADD COLUMN IF NOT EXISTS youtube_channel_id TEXT;

CREATE INDEX IF NOT EXISTS idx_bjcs_youtube_channel_id
    ON bronze.bronze_jurisdictions_counties_scraped (youtube_channel_id)
    WHERE youtube_channel_id IS NOT NULL AND BTRIM(youtube_channel_id) <> '';

CREATE INDEX IF NOT EXISTS idx_bjms_youtube_channel_id
    ON bronze.bronze_jurisdictions_municipalities_scraped (youtube_channel_id)
    WHERE youtube_channel_id IS NOT NULL AND BTRIM(youtube_channel_id) <> '';

COMMENT ON COLUMN bronze.bronze_jurisdictions_counties_scraped.youtube_channel_id IS
    'YouTube channel id (UC…) resolved from youtube_channel_url (@handle or /channel/UC).';
COMMENT ON COLUMN bronze.bronze_jurisdictions_municipalities_scraped.youtube_channel_id IS
    'YouTube channel id (UC…) resolved from youtube_channel_url.';

COMMIT;
