-- Migration: Bronze tables for cached meetings scrapes (manifest + derived docs/links JSON)
-- Database: open_navigator (bronze schema)
-- One row per jurisdiction (latest load wins via ON CONFLICT DO UPDATE on jurisdiction_id).

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_events_meetings_counties_scraped (
    id                     BIGSERIAL PRIMARY KEY,
    jurisdiction_id      TEXT NOT NULL,
    state_code             CHAR(2) NOT NULL,
    census_geoid           TEXT NOT NULL,
    homepage_url           TEXT,
    scraped_at             TIMESTAMPTZ NOT NULL,
    manifest_relative_path TEXT,
    detected_stacks        JSONB,
    document_records       JSONB NOT NULL DEFAULT '[]'::JSONB,
    link_records           JSONB NOT NULL DEFAULT '[]'::JSONB,
    errors                 JSONB,
    extracted_contacts     JSONB,
    raw_manifest           JSONB,
    loaded_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_meetings_counties_scraped_jurisdiction UNIQUE (jurisdiction_id)
);

CREATE INDEX IF NOT EXISTS idx_meetings_counties_scraped_state
    ON bronze.bronze_events_meetings_counties_scraped (state_code);
CREATE INDEX IF NOT EXISTS idx_meetings_counties_scraped_scraped_at
    ON bronze.bronze_events_meetings_counties_scraped (scraped_at DESC);

COMMENT ON TABLE bronze.bronze_events_meetings_counties_scraped IS
    'Rows from data/cache/scraped_meetings/{ST}/county/*/ _manifest.json; document_records = PDFs; link_records = HTML pages + streams.';

CREATE TABLE IF NOT EXISTS bronze.bronze_events_meetings_municipalities_scraped (
    id                     BIGSERIAL PRIMARY KEY,
    jurisdiction_id      TEXT NOT NULL,
    state_code             CHAR(2) NOT NULL,
    census_geoid           TEXT NOT NULL,
    homepage_url           TEXT,
    scraped_at             TIMESTAMPTZ NOT NULL,
    manifest_relative_path TEXT,
    detected_stacks        JSONB,
    document_records       JSONB NOT NULL DEFAULT '[]'::JSONB,
    link_records           JSONB NOT NULL DEFAULT '[]'::JSONB,
    errors                 JSONB,
    extracted_contacts     JSONB,
    raw_manifest           JSONB,
    loaded_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_meetings_muni_scraped_jurisdiction UNIQUE (jurisdiction_id)
);

CREATE INDEX IF NOT EXISTS idx_meetings_muni_scraped_state
    ON bronze.bronze_events_meetings_municipalities_scraped (state_code);
CREATE INDEX IF NOT EXISTS idx_meetings_muni_scraped_scraped_at
    ON bronze.bronze_events_meetings_municipalities_scraped (scraped_at DESC);

COMMENT ON TABLE bronze.bronze_events_meetings_municipalities_scraped IS
    'Rows from data/cache/scraped_meetings/{ST}/municipality/*/ _manifest.json.';

CREATE TABLE IF NOT EXISTS bronze.bronze_events_meetings_school_districts_scraped (
    id                     BIGSERIAL PRIMARY KEY,
    jurisdiction_id      TEXT NOT NULL,
    state_code             CHAR(2) NOT NULL,
    census_geoid           TEXT NOT NULL,
    homepage_url           TEXT,
    scraped_at             TIMESTAMPTZ NOT NULL,
    manifest_relative_path TEXT,
    detected_stacks        JSONB,
    document_records       JSONB NOT NULL DEFAULT '[]'::JSONB,
    link_records           JSONB NOT NULL DEFAULT '[]'::JSONB,
    errors                 JSONB,
    extracted_contacts     JSONB,
    raw_manifest           JSONB,
    loaded_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_meetings_sd_scraped_jurisdiction UNIQUE (jurisdiction_id)
);

CREATE INDEX IF NOT EXISTS idx_meetings_sd_scraped_state
    ON bronze.bronze_events_meetings_school_districts_scraped (state_code);
CREATE INDEX IF NOT EXISTS idx_meetings_sd_scraped_scraped_at
    ON bronze.bronze_events_meetings_school_districts_scraped (scraped_at DESC);

COMMENT ON TABLE bronze.bronze_events_meetings_school_districts_scraped IS
    'Rows from data/cache/scraped_meetings/{ST}/school/school_district_* / _manifest.json (folder uses short segment school).';

COMMIT;
