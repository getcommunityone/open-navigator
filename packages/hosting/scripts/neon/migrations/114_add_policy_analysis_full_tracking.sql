-- Migration: Distinct full-tier policy analysis/report stamps (#755)
-- Purpose: Light stamps stay on policy_analysis_* / policy_report_*; full writes
--          policy_*_full_* so stage progress can split light vs full.
-- Date: 2026-11-22
--
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f packages/hosting/scripts/neon/migrations/114_add_policy_analysis_full_tracking.sql

BEGIN;

ALTER TABLE bronze.bronze_event_youtube
ADD COLUMN IF NOT EXISTS policy_analysis_full_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS policy_analysis_full_error TEXT,
ADD COLUMN IF NOT EXISTS policy_analysis_full_path VARCHAR(500),
ADD COLUMN IF NOT EXISTS policy_report_full_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS policy_report_full_error TEXT,
ADD COLUMN IF NOT EXISTS policy_report_full_path VARCHAR(500);

CREATE INDEX IF NOT EXISTS idx_bronze_youtube_policy_analysis_full_at
ON bronze.bronze_event_youtube (policy_analysis_full_at)
WHERE policy_analysis_full_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bronze_youtube_policy_report_full_at
ON bronze.bronze_event_youtube (policy_report_full_at)
WHERE policy_report_full_at IS NOT NULL;

COMMENT ON COLUMN bronze.bronze_event_youtube.policy_analysis_full_at IS
    'Timestamp when full-tier Part 1 policy analysis was last produced successfully';
COMMENT ON COLUMN bronze.bronze_event_youtube.policy_analysis_full_error IS
    'Last full-tier analysis failure message; NULL on success';
COMMENT ON COLUMN bronze.bronze_event_youtube.policy_analysis_full_path IS
    'Repo-relative path to the full analysis JSON (*_full.json)';
COMMENT ON COLUMN bronze.bronze_event_youtube.policy_report_full_at IS
    'Timestamp when full-tier Part 2 report was last produced successfully';
COMMENT ON COLUMN bronze.bronze_event_youtube.policy_report_full_error IS
    'Last full-tier report failure message; NULL on success';
COMMENT ON COLUMN bronze.bronze_event_youtube.policy_report_full_path IS
    'Repo-relative path to the full report markdown (*_full.md)';

COMMIT;
