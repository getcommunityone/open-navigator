-- Migration: Add policy analysis/report event tracking to bronze_events_youtube
-- Purpose: Record when Part 1 analysis and Part 2 report are produced (or fail) per
--          video, so the batch dashboard can count analyses/reports over a rolling
--          24h window independent of batch-job enrollment (standalone CLI runs included).
-- Date: 2026-05-28
--
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/083_add_policy_analysis_report_tracking.sql

BEGIN;

ALTER TABLE bronze.bronze_events_youtube
ADD COLUMN IF NOT EXISTS policy_analysis_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS policy_analysis_error TEXT,
ADD COLUMN IF NOT EXISTS policy_analysis_path VARCHAR(500),
ADD COLUMN IF NOT EXISTS policy_report_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS policy_report_error TEXT,
ADD COLUMN IF NOT EXISTS policy_report_path VARCHAR(500);

CREATE INDEX IF NOT EXISTS idx_bronze_youtube_policy_analysis_at
ON bronze.bronze_events_youtube (policy_analysis_at)
WHERE policy_analysis_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bronze_youtube_policy_report_at
ON bronze.bronze_events_youtube (policy_report_at)
WHERE policy_report_at IS NOT NULL;

COMMENT ON COLUMN bronze.bronze_events_youtube.policy_analysis_at IS
    'Timestamp when Part 1 policy analysis JSON was last produced successfully; NULL if never or last attempt errored';
COMMENT ON COLUMN bronze.bronze_events_youtube.policy_analysis_error IS
    'Last policy analysis failure message; NULL on success';
COMMENT ON COLUMN bronze.bronze_events_youtube.policy_analysis_path IS
    'Repo-relative path to the analysis JSON (02_analysis/<meeting>.json)';
COMMENT ON COLUMN bronze.bronze_events_youtube.policy_report_at IS
    'Timestamp when Part 2 resident-facing report markdown was last produced successfully; NULL if never or last attempt errored';
COMMENT ON COLUMN bronze.bronze_events_youtube.policy_report_error IS
    'Last policy report failure message; NULL on success';
COMMENT ON COLUMN bronze.bronze_events_youtube.policy_report_path IS
    'Repo-relative path to the report markdown (03_reports/<meeting>.md)';

COMMIT;
