-- Migration: Record how each analysis was made (#798)
-- Purpose: the decision page shows a quiet "how this summary was made" panel. The model, time and prompt
--          version were already stored (ai_model, created_at, prompt_version). The tier (light or full) and the
--          transcript source were not. Both are nullable: analyses loaded before this migration keep NULL and the
--          panel leaves them out, they are never guessed.
-- Date: 2026-11-24
--
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f packages/hosting/scripts/neon/migrations/115_add_analysis_provenance_columns.sql

BEGIN;

ALTER TABLE bronze.bronze_events_analysis_ai
ADD COLUMN IF NOT EXISTS analysis_tier VARCHAR(10),
ADD COLUMN IF NOT EXISTS transcript_source TEXT;

COMMENT ON COLUMN bronze.bronze_events_analysis_ai.analysis_tier IS
    'light or full: the analysis tier the file was produced by (from the run metadata); NULL when not recorded';
COMMENT ON COLUMN bronze.bronze_events_analysis_ai.transcript_source IS
    'Where the transcript text came from, as recorded by the run; NULL when not recorded';

COMMIT;
