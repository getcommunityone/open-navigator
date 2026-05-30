-- Migration 070: cache YouTube channel metadata in intermediate for refresh without re-scrape.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/070_int_youtube_channel_metadata.sql

BEGIN;

CREATE TABLE IF NOT EXISTS intermediate.int_youtube_channel_metadata (
    channel_id           TEXT PRIMARY KEY,
    channel_url          TEXT,
    channel_title        TEXT,
    channel_description  TEXT,
    subscriber_count     BIGINT,
    video_count          BIGINT,
    view_count           BIGINT,
    latest_upload        VARCHAR(64),
    external_links       JSONB NOT NULL DEFAULT '[]'::JSONB,
    metadata_source      TEXT NOT NULL,
    fetched_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_int_youtube_channel_metadata_fetched_at
    ON intermediate.int_youtube_channel_metadata (fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_int_youtube_channel_metadata_source
    ON intermediate.int_youtube_channel_metadata (metadata_source);

COMMENT ON TABLE intermediate.int_youtube_channel_metadata IS
    'Cached YouTube channel About/metadata keyed by channel_id. Populated from bronze_events_channels and About scrapes; used to refresh int_events_channels without hitting YouTube again.';

COMMIT;
