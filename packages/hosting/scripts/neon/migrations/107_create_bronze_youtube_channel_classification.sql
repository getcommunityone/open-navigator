-- Migration 107: create bronze.bronze_youtube_channel_classification
--
-- Per-channel government-vs-junk verdict for YouTube channels that have been
-- stamped onto jurisdictions. The fuzzy name/homepage matcher mis-assigns many
-- ENTERTAINMENT / CREATOR channels (bands, hunting shows, AMVs, real-estate
-- listings) to government meeting feeds. The classifier in
-- ``packages/scrapers/src/scrapers/youtube/classify_channel_purpose.py`` writes
-- one row per ``channel_id`` here; the dbt registry track
-- (``intermediate.int_events_channels_registry``) reads this table to populate
-- its currently-hardcoded-NULL ``is_government`` / ``is_verified`` gate.
--
-- This is the ingestion-track schema artifact ONLY. It does not touch the
-- registry SQL or the served mart.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f packages/hosting/scripts/neon/migrations/107_create_bronze_youtube_channel_classification.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_youtube_channel_classification (
    channel_id          TEXT PRIMARY KEY,
    is_government       BOOLEAN,
    is_junk            BOOLEAN,
    flag_reason        TEXT,
    classification_method TEXT,
    confidence         DOUBLE PRECISION,
    classified_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bronze_youtube_channel_classification_is_government
    ON bronze.bronze_youtube_channel_classification (is_government);

CREATE INDEX IF NOT EXISTS idx_bronze_youtube_channel_classification_is_junk
    ON bronze.bronze_youtube_channel_classification (is_junk);

CREATE INDEX IF NOT EXISTS idx_bronze_youtube_channel_classification_method
    ON bronze.bronze_youtube_channel_classification (classification_method);

COMMENT ON TABLE bronze.bronze_youtube_channel_classification IS
    'Per-channel government-vs-junk verdict for jurisdiction-stamped YouTube channels. Written by scrapers.youtube.classify_channel_purpose; read by the int_events_channels_registry gate.';
COMMENT ON COLUMN bronze.bronze_youtube_channel_classification.is_government IS
    'TRUE = official government / public-body channel; FALSE = non-government; NULL = undecided (ambiguous, no LLM verdict).';
COMMENT ON COLUMN bronze.bronze_youtube_channel_classification.is_junk IS
    'TRUE = confirmed non-government junk (entertainment / creator / commercial) that must be excluded from meeting feeds.';
COMMENT ON COLUMN bronze.bronze_youtube_channel_classification.flag_reason IS
    'Human-readable rationale for the verdict (e.g. "zero-civic + max_views>=5000", "civic_fraction=0.82", "seed:known-junk").';
COMMENT ON COLUMN bronze.bronze_youtube_channel_classification.classification_method IS
    'How the verdict was reached: seed | heuristic | llm.';
COMMENT ON COLUMN bronze.bronze_youtube_channel_classification.confidence IS
    'Confidence in [0,1] for the verdict.';

COMMIT;
