-- Migration 010: Add jurisdiction_id to bronze jurisdiction tables.
--
-- jurisdiction_id is a human-readable, stable, unique identifier:
--   states              → usps                   e.g. "AL"
--   counties            → usps || '-' || geoid   e.g. "AL-01001"
--   municipalities      → usps || '-' || geoid   e.g. "AL-0100124"
--   school_districts    → usps || '-' || geoid   e.g. "AL-0100260"
--   place_zcta          → state_fips || '-' || zcta  e.g. "01-35004"
--                         (crosswalk table — NOT unique; same zcta appears per place)
--
-- _scraped tables get the same generated column + a FK back to the base table.
-- _wikidata tables inherit jurisdiction_id via SELECT base.* at next materialization.
--
-- Idempotent: safe to re-run on a database that already has these columns/constraints.

-- ─────────────────────────────────────────────────────────────────────────────
-- Base jurisdiction tables
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_states
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT GENERATED ALWAYS AS (usps) STORED;

DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_states
        ADD CONSTRAINT uq_bjs_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_bjs_jurisdiction_id
    ON bronze.bronze_jurisdictions_states (jurisdiction_id);

-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_counties
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT GENERATED ALWAYS AS (usps || '-' || geoid) STORED;

DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_counties
        ADD CONSTRAINT uq_bjc_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_bjc_jurisdiction_id
    ON bronze.bronze_jurisdictions_counties (jurisdiction_id);

-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_municipalities
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT GENERATED ALWAYS AS (usps || '-' || geoid) STORED;

DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_municipalities
        ADD CONSTRAINT uq_bjm_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_bjm_jurisdiction_id
    ON bronze.bronze_jurisdictions_municipalities (jurisdiction_id);

-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_school_districts
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT GENERATED ALWAYS AS (usps || '-' || geoid) STORED;

DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_school_districts
        ADD CONSTRAINT uq_bjsd_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_bjsd_jurisdiction_id
    ON bronze.bronze_jurisdictions_school_districts (jurisdiction_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- place_zcta crosswalk — jurisdiction_id identifies the ZCTA within a state.
-- NOT unique here because the same (state_fips, zcta) pair can appear multiple
-- times (once per place that overlaps that ZCTA).
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_place_zcta
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT GENERATED ALWAYS AS (state_fips || '-' || zcta) STORED;

CREATE INDEX IF NOT EXISTS idx_bjpz_jurisdiction_id
    ON bronze.bronze_jurisdictions_place_zcta (jurisdiction_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- _scraped tables — generated jurisdiction_id + FK to the base table
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_states_scraped
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT GENERATED ALWAYS AS (usps) STORED;

DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_states_scraped
        ADD CONSTRAINT fk_bjss_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_states (jurisdiction_id)
        ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_bjss_jurisdiction_id
    ON bronze.bronze_jurisdictions_states_scraped (jurisdiction_id);

-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT GENERATED ALWAYS AS (usps || '-' || geoid) STORED;

DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
        ADD CONSTRAINT fk_bjms_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_municipalities (jurisdiction_id)
        ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_bjms_jurisdiction_id
    ON bronze.bronze_jurisdictions_municipalities_scraped (jurisdiction_id);

-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT GENERATED ALWAYS AS (usps || '-' || geoid) STORED;

DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
        ADD CONSTRAINT fk_bjcs_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_counties (jurisdiction_id)
        ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_bjcs_jurisdiction_id
    ON bronze.bronze_jurisdictions_counties_scraped (jurisdiction_id);

-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT GENERATED ALWAYS AS (usps || '-' || geoid) STORED;

DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped
        ADD CONSTRAINT fk_bjsds_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_school_districts (jurisdiction_id)
        ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_bjsds_jurisdiction_id
    ON bronze.bronze_jurisdictions_school_districts_scraped (jurisdiction_id);
