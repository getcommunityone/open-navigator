-- Migration: Create bronze_events_civicsearch_schools table
-- Description: Bronze landing for CivicSearch SCHOOL-DISTRICT meeting records —
--              the school-board counterpart to bronze_events_civicsearch. Same
--              schema, separate table, populated from a distinct harvest run
--              (school-district seed sweep) so school-board meetings can be
--              landed/queried independently of general municipal meetings.
--              One row per vid_id (a YouTube video id); vid_id bridges to
--              existing localview/youtube events. Landed VERBATIM by the LAND
--              loader ingestion.civicsearch.events --schools from
--              data/cache/civicsearch/meetings.jsonl (emitted by the FETCH
--              scraper scrapers.civicsearch.harvest run against school seeds).
-- Database: open_navigator (bronze schema) — dev warehouse on localhost:5433
-- Date: 2026-05-31

-- Run this in the open_navigator database:
--   psql -h localhost -p 5433 -U postgres -d open_navigator \
--        -f 097_create_bronze_events_civicsearch_schools.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_events_civicsearch_schools (
    id                       BIGSERIAL PRIMARY KEY,

    -- Natural key: the YouTube video id (== localview/youtube datasource_id).
    vid_id                   VARCHAR(20) UNIQUE NOT NULL,

    -- Meeting attributes (landed verbatim from the CivicSearch search result).
    title                    TEXT,
    meeting_date             DATE,
    location                 TEXT,
    location_query_id        TEXT,
    distance                 DOUBLE PRECISION,
    has_approximate_timings  BOOLEAN,
    youtube_url              TEXT,

    -- Which discovered place this meeting was harvested under (location sweep).
    place_query_id           TEXT,
    place_lat                DOUBLE PRECISION,
    place_lon                DOUBLE PRECISION,

    -- CivicSearch's value-add, kept as JSONB for downstream dbt unnesting:
    --   matched_keywords : search keywords that surfaced this meeting
    --   snippets         : [{text, timestamp, topic_id}, ...]
    --   topic_ids        : distinct non-negative CivicSearch topic ids
    matched_keywords         JSONB NOT NULL DEFAULT '[]'::jsonb,
    snippets                 JSONB NOT NULL DEFAULT '[]'::jsonb,
    topic_ids                JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Full original record + provenance.
    raw_record               JSONB,
    scraped_at               TIMESTAMPTZ,
    loaded_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_schools_vid_id
    ON bronze.bronze_events_civicsearch_schools (vid_id);
CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_schools_location_query_id
    ON bronze.bronze_events_civicsearch_schools (location_query_id);
CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_schools_place_query_id
    ON bronze.bronze_events_civicsearch_schools (place_query_id);
CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_schools_meeting_date
    ON bronze.bronze_events_civicsearch_schools (meeting_date);
CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_schools_topic_ids
    ON bronze.bronze_events_civicsearch_schools USING gin (topic_ids);

COMMENT ON TABLE bronze.bronze_events_civicsearch_schools IS
    'Bronze landing for CivicSearch SCHOOL-DISTRICT meeting records (topic tags '
    '+ timestamped transcript snippets keyed by YouTube vid_id). Schools-only '
    'counterpart to bronze_events_civicsearch. Landed verbatim by '
    'ingestion.civicsearch.events --schools; vid_id bridges to localview/youtube events.';

COMMIT;
