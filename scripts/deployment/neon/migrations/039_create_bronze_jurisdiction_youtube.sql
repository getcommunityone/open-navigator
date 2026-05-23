-- Migration: bronze.bronze_jurisdiction_youtube — YouTube channels discovered for a jurisdiction,
-- linked to the official website that yielded (or anchored) the discovery.
--
-- One row per (scrape_batch_id, jurisdiction_id, youtube_channel_url). The same jurisdiction
-- can have multiple channels (e.g. a city tv channel and a council channel); per-batch
-- duplicates within a single discovery pass are deduped client-side before insert.
--
-- Apply from repo root:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/039_create_bronze_jurisdiction_youtube.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_youtube (
    id                   BIGSERIAL PRIMARY KEY,
    scrape_batch_id      UUID NOT NULL,
    jurisdiction_id      TEXT NOT NULL,
    state_code           CHAR(2) NOT NULL,
    website_url          TEXT,
    youtube_channel_url  TEXT NOT NULL,
    youtube_channel_id   TEXT,
    channel_title        TEXT,
    subscriber_count     BIGINT,
    video_count          BIGINT,
    view_count           BIGINT,
    latest_upload        TEXT,
    discovery_method     TEXT,
    confidence           DOUBLE PRECISION,
    raw_row              JSONB NOT NULL DEFAULT '{}'::JSONB,
    scraped_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_jurisdiction
    ON bronze.bronze_jurisdiction_youtube (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_batch
    ON bronze.bronze_jurisdiction_youtube (scrape_batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_state
    ON bronze.bronze_jurisdiction_youtube (state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_channel
    ON bronze.bronze_jurisdiction_youtube (youtube_channel_url);

COMMENT ON TABLE bronze.bronze_jurisdiction_youtube IS
    'YouTube channels discovered per jurisdiction, with the website_url that anchored the discovery. Best-effort, not authoritative — confirms which channel(s) a jurisdiction publishes meeting/government video on.';

COMMIT;
