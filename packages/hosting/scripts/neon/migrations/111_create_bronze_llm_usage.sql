-- Migration 111: create bronze.bronze_llm_call and bronze.bronze_gpu_run (#262)
--
-- Usage records for the LLM pipelines, loaded from the JSON-lines logs that
-- ``llm.usage`` writes (``python -m llm.usage.load_bronze``).
--
--   bronze_llm_call  one row per model call, after its retries: token counts,
--                    thinking tokens, latency, attempts, outcome
--   bronze_gpu_run   one row per GPU step (WhisperX diarization, a Gemma
--                    generation): wall time, GPU-hours, utilization, memory, energy
--
-- Cost is not stored. ``python -m llm.usage.report`` derives it from these
-- columns and ``packages/llm/src/llm/usage/prices.yaml``, so a corrected price
-- reprices history.
--
-- ``video_id`` matches ``bronze.bronze_event_youtube.video_id`` where the row is
-- about a video. It is not a foreign key: these are bronze tables, and a call
-- can be about a document or nothing at all.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f packages/hosting/scripts/neon/migrations/111_create_bronze_llm_usage.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_llm_call (
    llm_call_id               UUID PRIMARY KEY,
    called_at                 TIMESTAMPTZ NOT NULL,
    provider                  TEXT NOT NULL,
    model                     TEXT NOT NULL,
    api_mode                  TEXT NOT NULL,
    stage                     TEXT,
    video_id                  TEXT,
    jurisdiction_id           TEXT,
    run_id                    TEXT,
    input_token_count         INTEGER,
    cached_input_token_count  INTEGER,
    output_token_count        INTEGER,
    thinking_token_count      INTEGER,
    total_token_count         INTEGER,
    latency_seconds           DOUBLE PRECISION,
    attempt_count             INTEGER,
    is_ok                     BOOLEAN NOT NULL,
    error_type                TEXT,
    host_name                 TEXT
);

CREATE INDEX IF NOT EXISTS idx_bronze_llm_call_called_at
    ON bronze.bronze_llm_call (called_at);
CREATE INDEX IF NOT EXISTS idx_bronze_llm_call_video_id
    ON bronze.bronze_llm_call (video_id);

CREATE TABLE IF NOT EXISTS bronze.bronze_gpu_run (
    gpu_run_id               UUID PRIMARY KEY,
    step_name                TEXT NOT NULL,
    started_at               TIMESTAMPTZ NOT NULL,
    ended_at                 TIMESTAMPTZ NOT NULL,
    wall_seconds             DOUBLE PRECISION NOT NULL,
    gpu_count                INTEGER NOT NULL,
    gpu_name                 TEXT,
    gpu_hours                DOUBLE PRECISION NOT NULL,
    gpu_sample_count         INTEGER,
    avg_gpu_utilization_pct  DOUBLE PRECISION,
    max_gpu_memory_used_mb   DOUBLE PRECISION,
    energy_wh                DOUBLE PRECISION,
    video_id                 TEXT,
    jurisdiction_id          TEXT,
    run_id                   TEXT,
    host_name                TEXT
);

CREATE INDEX IF NOT EXISTS idx_bronze_gpu_run_started_at
    ON bronze.bronze_gpu_run (started_at);

COMMIT;
