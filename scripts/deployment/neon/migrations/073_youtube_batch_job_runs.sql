-- Migration: Persist YouTube caption/analyze batch job progress in Postgres
-- Purpose: Real-time batch dashboard via API (replaces JSON-only status files)
-- Date: 2026-05-26
--
-- Usage:
--   psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f scripts/deployment/neon/migrations/073_youtube_batch_job_runs.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.youtube_batch_job_runs (
    batch_id    VARCHAR(128) PRIMARY KEY,
    step        VARCHAR(32)  NOT NULL,
    status      VARCHAR(32)  NOT NULL,
    started_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    config      JSONB        NOT NULL DEFAULT '{}',
    summary     JSONB        NOT NULL DEFAULT '{}',
    payload     JSONB        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_youtube_batch_job_runs_updated
    ON bronze.youtube_batch_job_runs (updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_youtube_batch_job_runs_running
    ON bronze.youtube_batch_job_runs (status)
    WHERE status = 'running';

COMMENT ON TABLE bronze.youtube_batch_job_runs IS
    'Priority-state caption/analyze/catalog batch runs (run_priority_states_last_n.sh)';
COMMENT ON COLUMN bronze.youtube_batch_job_runs.payload IS
    'Full batch document: jurisdictions[], per-video outcomes, file_counts';

COMMIT;
