-- Bronze tables for jurisdiction discovery (GSA bulk + deep scrape).
-- Applied automatically by: python -m scripts.discovery.jurisdiction_discovery_pipeline
-- Can also be run manually: psql "$DATABASE_URL" -f scripts/discovery/sql/bronze_jurisdictions_scraped.sql
--
-- jurisdiction_id mirrors the base tables ({place_slug}_{geoid}, e.g. andalusia_0101708):
--   states_scraped            → bronze_jurisdictions_states(jurisdiction_id)            via usps
--   municipalities_scraped    → bronze_jurisdictions_municipalities(jurisdiction_id)    via trigger + FK
--   counties_scraped          → bronze_jurisdictions_counties(jurisdiction_id)          via trigger + FK
--   school_districts_scraped  → bronze_jurisdictions_school_districts(jurisdiction_id)  via trigger + FK

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_states_scraped (
    geoid                  TEXT          PRIMARY KEY,
    usps                   VARCHAR(2)    NOT NULL,
    discovered_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    homepage_url           TEXT,
    homepage_final_url     TEXT,
    gsa_matched_domain     TEXT,
    discovery_source       TEXT          NOT NULL DEFAULT 'deep_scrape',
    status                 TEXT,
    completeness_score     DOUBLE PRECISION,
    payload                JSONB         NOT NULL DEFAULT '{}'::jsonb,
    jurisdiction_id        TEXT          GENERATED ALWAYS AS (usps) STORED,
    jurisdiction_type      bronze.jurisdiction_type_enum      NOT NULL DEFAULT 'state',
    jurisdiction_id_source bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'usps',
    CONSTRAINT fk_bjss_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_states (jurisdiction_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bjss_usps            ON bronze.bronze_jurisdictions_states_scraped (usps);
CREATE INDEX IF NOT EXISTS idx_bjss_discovered_at   ON bronze.bronze_jurisdictions_states_scraped (discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_bjss_jurisdiction_id ON bronze.bronze_jurisdictions_states_scraped (jurisdiction_id);

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_municipalities_scraped (
    geoid                  TEXT          PRIMARY KEY,
    usps                   VARCHAR(2)    NOT NULL,
    discovered_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    homepage_url           TEXT,
    homepage_final_url     TEXT,
    gsa_matched_domain     TEXT,
    discovery_source       TEXT          NOT NULL DEFAULT 'deep_scrape',
    status                 TEXT,
    completeness_score     DOUBLE PRECISION,
    youtube_channel_url                  TEXT,
    youtube_channel_id                   TEXT,
    youtube_channel_selection_method     TEXT,
    youtube_channel_selection_confidence DOUBLE PRECISION,
    payload                JSONB         NOT NULL DEFAULT '{}'::jsonb,
    jurisdiction_id        TEXT,
    jurisdiction_type      bronze.jurisdiction_type_enum      NOT NULL DEFAULT 'municipality',
    jurisdiction_id_source bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'place_geoid',
    CONSTRAINT fk_bjms_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_municipalities (jurisdiction_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bjms_usps            ON bronze.bronze_jurisdictions_municipalities_scraped (usps);
CREATE INDEX IF NOT EXISTS idx_bjms_discovered_at   ON bronze.bronze_jurisdictions_municipalities_scraped (discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_bjms_jurisdiction_id ON bronze.bronze_jurisdictions_municipalities_scraped (jurisdiction_id);

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_counties_scraped (
    geoid                  TEXT          PRIMARY KEY,
    usps                   VARCHAR(2)    NOT NULL,
    discovered_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    homepage_url           TEXT,
    homepage_final_url     TEXT,
    gsa_matched_domain     TEXT,
    discovery_source       TEXT          NOT NULL DEFAULT 'deep_scrape',
    status                 TEXT,
    completeness_score     DOUBLE PRECISION,
    youtube_channel_url                  TEXT,
    youtube_channel_id                   TEXT,
    youtube_channel_selection_method     TEXT,
    youtube_channel_selection_confidence DOUBLE PRECISION,
    payload                JSONB         NOT NULL DEFAULT '{}'::jsonb,
    jurisdiction_id        TEXT,
    jurisdiction_type      bronze.jurisdiction_type_enum      NOT NULL DEFAULT 'county',
    jurisdiction_id_source bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'county_fips',
    CONSTRAINT fk_bjcs_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_counties (jurisdiction_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bjcs_usps            ON bronze.bronze_jurisdictions_counties_scraped (usps);
CREATE INDEX IF NOT EXISTS idx_bjcs_discovered_at   ON bronze.bronze_jurisdictions_counties_scraped (discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_bjcs_jurisdiction_id ON bronze.bronze_jurisdictions_counties_scraped (jurisdiction_id);

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_school_districts_scraped (
    geoid                  TEXT          PRIMARY KEY,
    usps                   VARCHAR(2)    NOT NULL,
    discovered_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    homepage_url           TEXT,
    homepage_final_url     TEXT,
    gsa_matched_domain     TEXT,
    discovery_source       TEXT          NOT NULL DEFAULT 'deep_scrape',
    status                 TEXT,
    completeness_score     DOUBLE PRECISION,
    payload                JSONB         NOT NULL DEFAULT '{}'::jsonb,
    jurisdiction_id        TEXT,
    jurisdiction_type      bronze.jurisdiction_type_enum      NOT NULL DEFAULT 'school_district',
    jurisdiction_id_source bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'school_district_geoid',
    CONSTRAINT fk_bjsds_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_school_districts (jurisdiction_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bjsds_usps            ON bronze.bronze_jurisdictions_school_districts_scraped (usps);
CREATE INDEX IF NOT EXISTS idx_bjsds_discovered_at   ON bronze.bronze_jurisdictions_school_districts_scraped (discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_bjsds_jurisdiction_id ON bronze.bronze_jurisdictions_school_districts_scraped (jurisdiction_id);
