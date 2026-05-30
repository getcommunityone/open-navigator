-- Migration: rename the misleading ``confidence`` column on
-- ``bronze.bronze_jurisdiction_youtube`` to ``discovery_confidence``.
--
-- The column holds the *upstream discovery* confidence (e.g. ``0.95`` for any channel
-- returned by the YouTube Data API search, ``0.7`` for pattern-match handle probes).
-- It does NOT mean "this is the jurisdiction's official channel" — that signal is
-- ``official_meeting_confidence``. The old name was confusing reviewers into trusting
-- the wrong column for filtering.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/042_rename_bronze_jurisdiction_youtube_confidence.sql

BEGIN;

ALTER TABLE bronze.bronze_jurisdiction_youtube
    RENAME COLUMN confidence TO discovery_confidence;

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.discovery_confidence IS
    'Upstream discovery confidence — how sure the discovery method was that this is a real YouTube channel (not the official-channel score). For relevance filtering use ``official_meeting_confidence`` instead.';

COMMIT;
