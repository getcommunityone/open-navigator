-- Migration: primary YouTube channel columns on municipality/county scraped tables
--
-- Keeps the full channel list in ``payload->youtube_channels``; these columns store the
-- single best pick (URL, how it was found, confidence used for ranking).
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/060_add_youtube_primary_to_bronze_jurisdictions_scraped.sql

BEGIN;

ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    ADD COLUMN IF NOT EXISTS youtube_channel_url                  TEXT,
    ADD COLUMN IF NOT EXISTS youtube_channel_selection_method     TEXT,
    ADD COLUMN IF NOT EXISTS youtube_channel_selection_confidence DOUBLE PRECISION;

ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    ADD COLUMN IF NOT EXISTS youtube_channel_url                  TEXT,
    ADD COLUMN IF NOT EXISTS youtube_channel_selection_method     TEXT,
    ADD COLUMN IF NOT EXISTS youtube_channel_selection_confidence DOUBLE PRECISION;

COMMENT ON COLUMN bronze.bronze_jurisdictions_municipalities_scraped.youtube_channel_url IS
    'Primary official/meeting YouTube channel URL chosen from payload youtube_channels.';
COMMENT ON COLUMN bronze.bronze_jurisdictions_municipalities_scraped.youtube_channel_selection_method IS
    'Discovery method of the selected primary channel (e.g. website_scrape, domain_search, youtube_api).';
COMMENT ON COLUMN bronze.bronze_jurisdictions_municipalities_scraped.youtube_channel_selection_confidence IS
    'Official-channel confidence (from enrichment official_meeting_confidence).';

COMMENT ON COLUMN bronze.bronze_jurisdictions_counties_scraped.youtube_channel_url IS
    'Primary official/meeting YouTube channel URL chosen from payload youtube_channels.';
COMMENT ON COLUMN bronze.bronze_jurisdictions_counties_scraped.youtube_channel_selection_method IS
    'Discovery method of the selected primary channel.';
COMMENT ON COLUMN bronze.bronze_jurisdictions_counties_scraped.youtube_channel_selection_confidence IS
    'Confidence used to rank channels for primary selection.';

COMMIT;
