-- Migration 071: merge bronze jurisdiction YouTube tables into intermediate.
--
-- - Rename channel-centric ``intermediate.int_events_channels`` (dbt registry) to
--   ``intermediate.int_events_channels_registry``.
-- - ``intermediate.int_events_channels`` — golden verified county/municipality channels
--   (replaces ``bronze.bronze_jurisdiction_youtube``).
-- - ``intermediate.int_events_channels_candidates`` — audit probes
--   (replaces ``bronze.bronze_jurisdiction_youtube_candidates``).
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/071_int_events_channels_jurisdiction_merge.sql

BEGIN;

-- Channel-centric registry (dbt ``int_events_channels_registry``).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'intermediate'
          AND table_name = 'int_events_channels'
    )
    AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'intermediate'
          AND table_name = 'int_events_channels_registry'
    ) THEN
        ALTER TABLE intermediate.int_events_channels
            RENAME TO int_events_channels_registry;
    END IF;
END $$;

-- Golden jurisdiction ↔ channel (county / municipality verified rows).
CREATE TABLE IF NOT EXISTS intermediate.int_events_channels (
    id                               BIGSERIAL PRIMARY KEY,
    scrape_batch_id                  UUID,
    jurisdiction_id                  TEXT NOT NULL,
    jurisdiction_type                TEXT,
    state_code                       CHAR(2) NOT NULL,
    ocd_id                           TEXT,
    website_url                      TEXT,
    youtube_channel_url              TEXT NOT NULL,
    youtube_channel_id               TEXT,
    channel_title                    TEXT,
    subscriber_count                 BIGINT,
    video_count                      BIGINT,
    view_count                       BIGINT,
    latest_upload                    TEXT,
    discovery_method                 TEXT,
    raw_row                          JSONB NOT NULL DEFAULT '{}'::JSONB,
    scraped_at                       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at                        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    channel_description              TEXT,
    back_links_to_jurisdiction_website BOOLEAN,
    official_meeting_confidence      DOUBLE PRECISION,
    external_links                   JSONB NOT NULL DEFAULT '[]'::JSONB,
    jurisdiction_website_back_links  JSONB NOT NULL DEFAULT '[]'::JSONB,
    channel_purpose                  TEXT,
    source                           TEXT,
    is_primary                       BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at                      TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_int_events_channels_jur_url
    ON intermediate.int_events_channels (jurisdiction_id, youtube_channel_url);

CREATE INDEX IF NOT EXISTS idx_int_events_channels_jurisdiction
    ON intermediate.int_events_channels (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_int_events_channels_state
    ON intermediate.int_events_channels (state_code);
CREATE INDEX IF NOT EXISTS idx_int_events_channels_type
    ON intermediate.int_events_channels (jurisdiction_type);
CREATE INDEX IF NOT EXISTS idx_int_events_channels_channel_id
    ON intermediate.int_events_channels (youtube_channel_id);
CREATE INDEX IF NOT EXISTS idx_int_events_channels_channel_purpose
    ON intermediate.int_events_channels (channel_purpose);

COMMENT ON TABLE intermediate.int_events_channels IS
    'Golden verified YouTube channel(s) per county/municipality jurisdiction. Replaces bronze.bronze_jurisdiction_youtube.';

-- Audit / candidate probes.
CREATE TABLE IF NOT EXISTS intermediate.int_events_channels_candidates (
    id                               BIGSERIAL PRIMARY KEY,
    scrape_batch_id                  UUID NOT NULL,
    jurisdiction_id                  TEXT NOT NULL,
    jurisdiction_type                TEXT,
    state_code                       CHAR(2) NOT NULL,
    ocd_id                           TEXT,
    website_url                      TEXT,
    youtube_channel_url              TEXT NOT NULL,
    youtube_channel_id               TEXT,
    channel_title                    TEXT,
    subscriber_count                 BIGINT,
    video_count                      BIGINT,
    view_count                       BIGINT,
    latest_upload                    TEXT,
    discovery_method                 TEXT,
    raw_row                          JSONB NOT NULL DEFAULT '{}'::JSONB,
    scraped_at                       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at                        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    channel_description              TEXT,
    back_links_to_jurisdiction_website BOOLEAN,
    official_meeting_confidence      DOUBLE PRECISION,
    external_links                   JSONB NOT NULL DEFAULT '[]'::JSONB,
    jurisdiction_website_back_links  JSONB NOT NULL DEFAULT '[]'::JSONB,
    channel_purpose                  TEXT,
    rejection_reason                 TEXT,
    is_verified                      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_int_events_channels_candidates_jurisdiction
    ON intermediate.int_events_channels_candidates (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_int_events_channels_candidates_batch
    ON intermediate.int_events_channels_candidates (scrape_batch_id);
CREATE INDEX IF NOT EXISTS idx_int_events_channels_candidates_state
    ON intermediate.int_events_channels_candidates (state_code);
CREATE INDEX IF NOT EXISTS idx_int_events_channels_candidates_verified
    ON intermediate.int_events_channels_candidates (is_verified);
CREATE INDEX IF NOT EXISTS idx_int_events_channels_candidates_type
    ON intermediate.int_events_channels_candidates (jurisdiction_type);
CREATE INDEX IF NOT EXISTS idx_int_events_channels_candidates_channel_purpose
    ON intermediate.int_events_channels_candidates (channel_purpose);

COMMENT ON TABLE intermediate.int_events_channels_candidates IS
    'Audit log of YouTube channel discovery probes per jurisdiction. Replaces bronze.bronze_jurisdiction_youtube_candidates.';

-- Migrate bronze candidates (idempotent).
INSERT INTO intermediate.int_events_channels_candidates (
    scrape_batch_id, jurisdiction_id, jurisdiction_type, state_code, ocd_id, website_url,
    youtube_channel_url, youtube_channel_id, channel_title,
    subscriber_count, video_count, view_count, latest_upload,
    discovery_method, raw_row, scraped_at, loaded_at,
    channel_description, back_links_to_jurisdiction_website,
    official_meeting_confidence, external_links,
    jurisdiction_website_back_links, channel_purpose,
    rejection_reason, is_verified
)
SELECT
    c.scrape_batch_id, c.jurisdiction_id, c.jurisdiction_type, c.state_code, c.ocd_id, c.website_url,
    c.youtube_channel_url, c.youtube_channel_id, c.channel_title,
    c.subscriber_count, c.video_count, c.view_count, c.latest_upload,
    c.discovery_method, c.raw_row, c.scraped_at, c.loaded_at,
    c.channel_description, c.back_links_to_jurisdiction_website,
    c.official_meeting_confidence, c.external_links,
    c.jurisdiction_website_back_links, c.channel_purpose,
    c.rejection_reason, c.is_verified
FROM bronze.bronze_jurisdiction_youtube_candidates c
WHERE NOT EXISTS (
    SELECT 1
    FROM intermediate.int_events_channels_candidates t
    WHERE t.scrape_batch_id = c.scrape_batch_id
      AND t.jurisdiction_id = c.jurisdiction_id
      AND t.youtube_channel_url = c.youtube_channel_url
);

-- Migrate bronze verified golden rows (county/municipality only).
INSERT INTO intermediate.int_events_channels (
    scrape_batch_id, jurisdiction_id, jurisdiction_type, state_code, ocd_id, website_url,
    youtube_channel_url, youtube_channel_id, channel_title,
    subscriber_count, video_count, view_count, latest_upload,
    discovery_method, raw_row, scraped_at, loaded_at,
    channel_description, back_links_to_jurisdiction_website,
    official_meeting_confidence, external_links,
    jurisdiction_website_back_links, channel_purpose,
    source, is_primary, verified_at
)
SELECT
    y.scrape_batch_id, y.jurisdiction_id, y.jurisdiction_type, y.state_code, y.ocd_id, y.website_url,
    y.youtube_channel_url, y.youtube_channel_id, y.channel_title,
    y.subscriber_count, y.video_count, y.view_count, y.latest_upload,
    y.discovery_method, y.raw_row, y.scraped_at, y.loaded_at,
    y.channel_description, y.back_links_to_jurisdiction_website,
    y.official_meeting_confidence, y.external_links,
    y.jurisdiction_website_back_links, y.channel_purpose,
    y.source, y.is_primary, y.verified_at
FROM bronze.bronze_jurisdiction_youtube y
WHERE COALESCE(y.jurisdiction_type, '') IN ('county', 'municipality')
  AND NOT EXISTS (
    SELECT 1
    FROM intermediate.int_events_channels t
    WHERE t.jurisdiction_id = y.jurisdiction_id
      AND t.youtube_channel_url = y.youtube_channel_url
);

-- Drop legacy bronze tables.
DROP TABLE IF EXISTS bronze.bronze_jurisdiction_youtube CASCADE;
DROP TABLE IF EXISTS bronze.bronze_jurisdiction_youtube_candidates CASCADE;

COMMIT;
