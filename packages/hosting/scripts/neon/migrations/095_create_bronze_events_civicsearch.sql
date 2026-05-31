-- Migration: Create bronze_events_civicsearch table
-- Description: Bronze landing for CivicSearch meeting records — the policy-topic
--              + timestamped-snippet layer CivicSearch (schools.civicsearch.org)
--              builds on top of LocalView/YouTube transcripts. One row per
--              vid_id (a YouTube video id), landed VERBATIM by the LAND loader
--              ingestion.civicsearch.events from data/cache/civicsearch/meetings.jsonl
--              (emitted by the FETCH scraper scrapers.civicsearch.harvest).
--              vid_id is the bridge to existing localview/youtube events.
-- Database: open_navigator (bronze schema) — dev warehouse on localhost:5433
-- Date: 2026-05-31

-- Run this in the open_navigator database:
--   psql -h localhost -p 5433 -U postgres -d open_navigator \
--        -f 095_create_bronze_events_civicsearch.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_events_civicsearch (
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

CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_vid_id
    ON bronze.bronze_events_civicsearch (vid_id);
CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_location_query_id
    ON bronze.bronze_events_civicsearch (location_query_id);
CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_place_query_id
    ON bronze.bronze_events_civicsearch (place_query_id);
CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_meeting_date
    ON bronze.bronze_events_civicsearch (meeting_date);
CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_topic_ids
    ON bronze.bronze_events_civicsearch USING gin (topic_ids);

COMMENT ON TABLE bronze.bronze_events_civicsearch IS
    'Bronze landing for CivicSearch meeting records (topic tags + timestamped '
    'transcript snippets keyed by YouTube vid_id). Landed verbatim by '
    'ingestion.civicsearch.events; vid_id bridges to localview/youtube events.';

COMMIT;
