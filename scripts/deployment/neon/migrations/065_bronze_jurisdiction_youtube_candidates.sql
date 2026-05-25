-- Migration 065: split YouTube channel audit from verified canonical rows.
--
-- bronze.bronze_jurisdiction_youtube_candidates — every probe / discovery attempt
--   (pattern_match noise, rejected gates, low-confidence rows) for review.
-- bronze.bronze_jurisdiction_youtube — verified jurisdiction channels only
--   (website-linked, high-confidence, localview, events-catalog, manual).
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/065_bronze_jurisdiction_youtube_candidates.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_youtube_candidates (
    id                               BIGSERIAL PRIMARY KEY,
    scrape_batch_id                  UUID NOT NULL,
    jurisdiction_id                  TEXT NOT NULL,
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
  rejection_reason                   TEXT,
  is_verified                        BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_candidates_jurisdiction
    ON bronze.bronze_jurisdiction_youtube_candidates (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_candidates_batch
    ON bronze.bronze_jurisdiction_youtube_candidates (scrape_batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_candidates_state
    ON bronze.bronze_jurisdiction_youtube_candidates (state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_candidates_verified
    ON bronze.bronze_jurisdiction_youtube_candidates (is_verified);

COMMENT ON TABLE bronze.bronze_jurisdiction_youtube_candidates IS
    'Audit log of every YouTube channel probe during jurisdiction pilot runs. Includes rejected pattern_match noise.';

-- Copy historical audit rows into candidates (idempotent on re-run).
INSERT INTO bronze.bronze_jurisdiction_youtube_candidates (
    scrape_batch_id, jurisdiction_id, state_code, ocd_id, website_url,
    youtube_channel_url, youtube_channel_id, channel_title,
    subscriber_count, video_count, view_count, latest_upload,
    discovery_method, raw_row, scraped_at, loaded_at,
    channel_description, back_links_to_jurisdiction_website,
    official_meeting_confidence, external_links,
    rejection_reason, is_verified
)
SELECT
    y.scrape_batch_id, y.jurisdiction_id, y.state_code, y.ocd_id, y.website_url,
    y.youtube_channel_url, y.youtube_channel_id, y.channel_title,
    y.subscriber_count, y.video_count, y.view_count, y.latest_upload,
    y.discovery_method, y.raw_row, y.scraped_at, y.loaded_at,
    y.channel_description, y.back_links_to_jurisdiction_website,
    y.official_meeting_confidence, y.external_links,
    CASE
        WHEN COALESCE(y.official_meeting_confidence, 0) < 0.55 THEN 'low_official_confidence'
        WHEN y.discovery_method LIKE 'pattern_match%'
             AND COALESCE(y.back_links_to_jurisdiction_website, FALSE) IS NOT TRUE
             AND COALESCE(y.official_meeting_confidence, 0) < 0.55 THEN 'pattern_match_weak'
        WHEN LOWER(BTRIM(COALESCE(y.channel_title, ''))) IN ('home', 'videos', 'shorts', 'live', 'playlists')
             AND COALESCE(y.official_meeting_confidence, 0) < 0.55 THEN 'junk_channel_title'
        ELSE NULL
    END,
    (
        COALESCE(y.official_meeting_confidence, 0) >= 0.55
        AND (
            COALESCE(y.back_links_to_jurisdiction_website, FALSE) IS TRUE
            OR COALESCE(y.discovery_method, '') NOT LIKE 'pattern_match%'
        )
        AND NOT (
            LOWER(BTRIM(COALESCE(y.channel_title, ''))) IN ('home', 'videos', 'shorts', 'live', 'playlists')
            AND COALESCE(y.official_meeting_confidence, 0) < 0.55
        )
    )
FROM bronze.bronze_jurisdiction_youtube y
WHERE NOT EXISTS (
    SELECT 1
    FROM bronze.bronze_jurisdiction_youtube_candidates c
    WHERE c.scrape_batch_id = y.scrape_batch_id
      AND c.jurisdiction_id = y.jurisdiction_id
      AND c.youtube_channel_url = y.youtube_channel_url
);

-- Canonical table: add provenance + primary flag.
ALTER TABLE bronze.bronze_jurisdiction_youtube
    ADD COLUMN IF NOT EXISTS source TEXT,
    ADD COLUMN IF NOT EXISTS is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;

COMMENT ON TABLE bronze.bronze_jurisdiction_youtube IS
    'Verified official YouTube channel(s) per jurisdiction — consolidated from pilot website discovery, localview, and events catalog. No pattern_match noise.';

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.source IS
    'Provenance: pilot_website_search, pilot_civic_api, localview, events_catalog, manual, …';

-- Drop noise from canonical table (keep rows that meet verified bar).
DELETE FROM bronze.bronze_jurisdiction_youtube y
WHERE COALESCE(y.official_meeting_confidence, 0) < 0.55
   OR (
       COALESCE(y.discovery_method, '') LIKE 'pattern_match%'
       AND COALESCE(y.back_links_to_jurisdiction_website, FALSE) IS NOT TRUE
   )
   OR (
       LOWER(BTRIM(COALESCE(y.channel_title, ''))) IN ('home', 'videos', 'shorts', 'live', 'playlists')
       AND COALESCE(y.official_meeting_confidence, 0) < 0.55
   );

UPDATE bronze.bronze_jurisdiction_youtube
SET source = COALESCE(source, discovery_method, 'pilot_legacy'),
    verified_at = COALESCE(verified_at, loaded_at)
WHERE source IS NULL OR verified_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_bronze_jurisdiction_youtube_jur_url
    ON bronze.bronze_jurisdiction_youtube (jurisdiction_id, youtube_channel_url);

COMMIT;
