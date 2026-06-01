-- Migration: Create bronze_events_civicsearch_topic + _schools_topic tables
-- Description: Bronze landing for the CivicSearch policy-TOPIC decoder — the
--              id -> {name, query_id, keyword_stats} lookup that turns the bare
--              numeric topic_id landed in bronze_events_civicsearch(_schools)
--              (snippets[].topic_id / topic_ids) into a human-readable topic.
--              The CivicSearch JSON API never returns topic names; the table is
--              baked into the site's main.js bundle. The FETCH scraper
--              scrapers.civicsearch.topics extracts it into
--              data/cache/civicsearch/<portal>/topics.json and the LAND loader
--              ingestion.civicsearch.topics lands it here VERBATIM.
--
--              Topic ids are PORTAL-SPECIFIC: the cities and schools properties
--              number their topics independently, so each portal gets its own
--              decoder table (mirroring the split events tables 095 / 097).
--              topic_id == -1 is CivicSearch's catch-all bucket ("Local
--              governance" / "School board") and is kept.
-- Database: open_navigator (bronze schema) — dev warehouse on localhost:5433
-- Date: 2026-05-31

-- Run this in the open_navigator database:
--   psql -h localhost -p 5433 -U postgres -d open_navigator \
--        -f 101_create_bronze_events_civicsearch_topic.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- cities portal decoder (decodes bronze_events_civicsearch.topic_ids)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.bronze_events_civicsearch_topic (
    -- Natural key: CivicSearch's own numeric topic id (-1 == catch-all bucket).
    topic_id       INTEGER PRIMARY KEY,

    name           TEXT NOT NULL,
    query_id       TEXT,

    -- The topic's most-distinctive keywords, kept as JSONB for dbt unnesting.
    keyword_stats  JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Full original entry + provenance.
    raw_record     JSONB,
    scraped_at     TIMESTAMPTZ,
    loaded_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_topic_query_id
    ON bronze.bronze_events_civicsearch_topic (query_id);

COMMENT ON TABLE bronze.bronze_events_civicsearch_topic IS
    'CivicSearch (cities portal) topic decoder: numeric topic_id -> name / '
    'query_id / keyword_stats. Extracted from the site main.js bundle by the '
    'FETCH scraper scrapers.civicsearch.topics; landed by '
    'ingestion.civicsearch.topics. Decodes bronze_events_civicsearch.topic_ids.';

-- ---------------------------------------------------------------------------
-- schools portal decoder (decodes bronze_events_civicsearch_schools.topic_ids)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.bronze_events_civicsearch_schools_topic (
    topic_id       INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    query_id       TEXT,
    keyword_stats  JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_record     JSONB,
    scraped_at     TIMESTAMPTZ,
    loaded_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bronze_civicsearch_schools_topic_query_id
    ON bronze.bronze_events_civicsearch_schools_topic (query_id);

COMMENT ON TABLE bronze.bronze_events_civicsearch_schools_topic IS
    'CivicSearch (schools portal) topic decoder: numeric topic_id -> name / '
    'query_id / keyword_stats. Extracted from schools.civicsearch.org main.js '
    'by scrapers.civicsearch.topics; landed by ingestion.civicsearch.topics '
    '--schools. Decodes bronze_events_civicsearch_schools.topic_ids. Topic ids '
    'are numbered INDEPENDENTLY of the cities portal.';

COMMIT;
