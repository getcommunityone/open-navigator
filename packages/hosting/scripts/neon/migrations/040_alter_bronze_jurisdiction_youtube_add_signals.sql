-- Migration: add channel description + officialness signals to bronze_jurisdiction_youtube.
--
-- ``channel_description`` is the verbatim text from the channel's About page.
-- ``back_links_to_jurisdiction_website`` is TRUE when the channel description / external-links
-- list contains an HTTP(S) link whose host matches the jurisdiction's ``website_url`` host
-- (or shares a parent .gov domain).
-- ``official_meeting_confidence`` is 0.0–1.0 combining name match, back-link, and policy
-- keyword signals — see ``youtube_channel_enrich.py`` for the weighting.
-- ``external_links`` is the deduped list of outbound URLs found in the channel description /
-- About page banner links (JSONB array of strings).
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/040_alter_bronze_jurisdiction_youtube_add_signals.sql

BEGIN;

ALTER TABLE bronze.bronze_jurisdiction_youtube
    ADD COLUMN IF NOT EXISTS channel_description                   TEXT,
    ADD COLUMN IF NOT EXISTS back_links_to_jurisdiction_website    BOOLEAN,
    ADD COLUMN IF NOT EXISTS official_meeting_confidence           DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS external_links                        JSONB NOT NULL DEFAULT '[]'::JSONB;

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.channel_description IS
    'Text scraped from the YouTube channel About page (best-effort; may be empty if the page failed to load).';
COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.back_links_to_jurisdiction_website IS
    'TRUE when the channel description / external-links list contains a link to the jurisdiction website host (or a parent .gov of it).';
COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.official_meeting_confidence IS
    '0.0–1.0 heuristic that this is the official meeting/government channel — combines name match, back-link, and policy keywords. >= 0.5 ≈ confident.';
COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.external_links IS
    'JSONB array of outbound URLs scraped from the channel About page (for back-link verification and downstream linkage).';

COMMIT;
