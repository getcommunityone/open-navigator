-- Migration: bronze.bronze_events_cdp — Council Data Project meeting events
--
-- Lands meeting events (date, body, agenda/minutes/video URIs) from CDP's
-- per-jurisdiction GraphQL instances. CDP-compatible superset read by the
-- shared staging view stg_bronze_events_cdp; the YouTube-only columns
-- (channel_id, view_count, …) exist so that view compiles but stay NULL for
-- CDP-sourced rows. Loaded by:
--   python -m ingestion.cdp.events --instance seattle   (FETCH→data/cache/cdp/, LAND→bronze)
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -v ON_ERROR_STOP=1 \
--     -f packages/hosting/scripts/neon/migrations/086_create_bronze_events_cdp.sql
--
-- AFTER applying: load data, then build the staging view:
--   python -m ingestion.cdp.events --instance all
--   ./scripts/dbt.sh run --select stg_bronze_events_cdp

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_events_cdp (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title                TEXT,
    description          TEXT,
    event_date           DATE,
    event_time           TIME,
    event_datetime       TIMESTAMPTZ,
    body_name            TEXT,
    body_description     TEXT,
    jurisdiction_id      TEXT,
    jurisdiction_name    TEXT,
    jurisdiction_type    TEXT,
    state_code           VARCHAR(2),
    state                TEXT,
    city                 TEXT,
    location             TEXT,
    location_description TEXT,
    meeting_type         TEXT,
    status               TEXT,
    agenda_url           TEXT,
    minutes_url          TEXT,
    video_url            TEXT,
    session_content_hash TEXT,
    channel_id           TEXT,
    channel_url          TEXT,
    channel_type         TEXT,
    view_count           BIGINT,
    duration_minutes     NUMERIC,
    like_count           BIGINT,
    language             TEXT,
    source               TEXT NOT NULL,
    datasource_id        TEXT,
    external_source_id   TEXT,
    loaded_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Natural dedup key for ON CONFLICT upserts: one row per CDP event id.
    CONSTRAINT uq_bronze_events_cdp_source_extid UNIQUE (source, external_source_id)
);

CREATE INDEX IF NOT EXISTS idx_bronze_events_cdp_state_source
    ON bronze.bronze_events_cdp (state_code, source);

COMMENT ON TABLE bronze.bronze_events_cdp IS
    'Council Data Project meeting events (CDP-compatible superset). Loaded by `python -m ingestion.cdp.events`. Source: councildataproject.org per-instance GraphQL endpoints.';

COMMIT;
