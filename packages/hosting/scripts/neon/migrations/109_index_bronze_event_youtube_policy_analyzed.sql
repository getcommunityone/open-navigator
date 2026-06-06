-- Migration 109: index bronze.bronze_event_youtube for the policy-analyzed promote scan
--
-- ``ingestion.youtube.promote_to_c1_event`` (default scope) selects the curated
-- meeting set with::
--
--     SELECT ... FROM bronze.bronze_event_youtube
--     WHERE video_id IS NOT NULL
--       AND policy_analysis_at IS NOT NULL
--       AND state_code = ANY(%s)        -- when --states is given
--
-- With no supporting index this full-scans the (large) bronze_event_youtube
-- table on every promote run — observed ~26 min to find a single eligible AZ
-- row. ``policy_analysis_at IS NOT NULL`` is highly selective (only the small
-- subset of videos that have been Gemini-analyzed), so a PARTIAL index on
-- ``state_code`` filtered by that predicate is tiny and turns the scan into an
-- index lookup. The same partial index also serves the un-stated form
-- (predicate alone, any state).
--
-- Plain (non-CONCURRENT) build so it runs inside the migration transaction,
-- matching the repo convention. Dev-only target (local 5433 / NEON dev) per the
-- deployment rules — never prod.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f packages/hosting/scripts/neon/migrations/109_index_bronze_event_youtube_policy_analyzed.sql

BEGIN;

CREATE INDEX IF NOT EXISTS idx_bronze_event_youtube_policy_analyzed_by_state
    ON bronze.bronze_event_youtube (state_code)
    WHERE policy_analysis_at IS NOT NULL;

COMMENT ON INDEX bronze.idx_bronze_event_youtube_policy_analyzed_by_state IS
    'Partial index supporting ingestion.youtube.promote_to_c1_event eligibility scan (policy-analyzed videos, optionally filtered by state_code). Covers WHERE policy_analysis_at IS NOT NULL [AND state_code = ANY(...)].';

COMMIT;
