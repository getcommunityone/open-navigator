-- Migration 069: channel purpose tags for jurisdiction YouTube rows.
--
-- Values: county-meeting, county-general, municipality-meeting, municipality-general,
-- tv-public, unknown.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/069_add_channel_purpose_youtube.sql

BEGIN;

ALTER TABLE bronze.bronze_jurisdiction_youtube_candidates
    ADD COLUMN IF NOT EXISTS channel_purpose TEXT;

ALTER TABLE bronze.bronze_jurisdiction_youtube
    ADD COLUMN IF NOT EXISTS channel_purpose TEXT;

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube_candidates.channel_purpose IS
    'Meeting focus: county-meeting, county-general, municipality-meeting, municipality-general, tv-public, unknown.';

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.channel_purpose IS
    'Meeting focus tag; county-general and tv-public require stricter verification for canonical rows.';

CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_channel_purpose
    ON bronze.bronze_jurisdiction_youtube (channel_purpose);

CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_candidates_channel_purpose
    ON bronze.bronze_jurisdiction_youtube_candidates (channel_purpose);

COMMIT;
