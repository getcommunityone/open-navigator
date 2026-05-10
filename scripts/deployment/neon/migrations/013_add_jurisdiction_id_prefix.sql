-- Migration 013: Add type prefix to jurisdiction_id to guarantee global uniqueness.
--
-- Problem: municipalities and school_districts both produce usps||'-'||geoid
--   (7-char GEOIDs) — Census place codes and NCES district codes are independent
--   number pools and can produce the same numeric suffix.
--
-- New format:
--   state           →  AL              (no prefix — 2-char alpha is already unique)
--   county          →  c-AL-01001
--   municipality    →  m-AL-0100124
--   school_district →  s-AL-0100260
--   zcta            →  z-01-35004
--
-- Generated columns cannot have their expression altered in-place; we must
-- DROP + ADD.  DROP COLUMN CASCADE removes the UNIQUE constraint automatically,
-- so we rebuild it explicitly.  FKs from _scraped and _wikidata tables are
-- dropped first and restored after.
--
-- States are unchanged — skipped entirely.
-- Idempotent for tables that don't exist (wikidata may not be materialized).

-- ═════════════════════════════════════════════════════════════════════════════
-- COUNTIES   c-{usps}-{geoid}
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    DROP CONSTRAINT IF EXISTS fk_bjcs_jurisdiction_id;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_counties_wikidata
        DROP CONSTRAINT IF EXISTS fk_bjcw_jurisdiction_id;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

ALTER TABLE bronze.bronze_jurisdictions_counties      DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_counties
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS ('c-' || usps || '-' || geoid) STORED;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_counties
        ADD CONSTRAINT uq_bjc_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_bjc_jurisdiction_id ON bronze.bronze_jurisdictions_counties(jurisdiction_id);

ALTER TABLE bronze.bronze_jurisdictions_counties_scraped DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS ('c-' || usps || '-' || geoid) STORED;
ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    ADD CONSTRAINT fk_bjcs_jurisdiction_id
    FOREIGN KEY (jurisdiction_id)
    REFERENCES bronze.bronze_jurisdictions_counties(jurisdiction_id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_bjcs_jurisdiction_id ON bronze.bronze_jurisdictions_counties_scraped(jurisdiction_id);

DO $$ BEGIN
    UPDATE bronze.bronze_jurisdictions_counties_wikidata
        SET jurisdiction_id = 'c-' || usps || '-' || geoid;
    ALTER TABLE bronze.bronze_jurisdictions_counties_wikidata
        ADD CONSTRAINT fk_bjcw_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_counties(jurisdiction_id) ON DELETE CASCADE;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- ═════════════════════════════════════════════════════════════════════════════
-- MUNICIPALITIES   m-{usps}-{geoid}
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    DROP CONSTRAINT IF EXISTS fk_bjms_jurisdiction_id;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_municipalities_wikidata
        DROP CONSTRAINT IF EXISTS fk_bjmw_jurisdiction_id;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

ALTER TABLE bronze.bronze_jurisdictions_municipalities  DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_municipalities
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS ('m-' || usps || '-' || geoid) STORED;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_municipalities
        ADD CONSTRAINT uq_bjm_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_bjm_jurisdiction_id ON bronze.bronze_jurisdictions_municipalities(jurisdiction_id);

ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS ('m-' || usps || '-' || geoid) STORED;
ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    ADD CONSTRAINT fk_bjms_jurisdiction_id
    FOREIGN KEY (jurisdiction_id)
    REFERENCES bronze.bronze_jurisdictions_municipalities(jurisdiction_id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_bjms_jurisdiction_id ON bronze.bronze_jurisdictions_municipalities_scraped(jurisdiction_id);

DO $$ BEGIN
    UPDATE bronze.bronze_jurisdictions_municipalities_wikidata
        SET jurisdiction_id = 'm-' || usps || '-' || geoid;
    ALTER TABLE bronze.bronze_jurisdictions_municipalities_wikidata
        ADD CONSTRAINT fk_bjmw_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_municipalities(jurisdiction_id) ON DELETE CASCADE;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- ═════════════════════════════════════════════════════════════════════════════
-- SCHOOL DISTRICTS   s-{usps}-{geoid}
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped
    DROP CONSTRAINT IF EXISTS fk_bjsds_jurisdiction_id;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_school_districts_wikidata
        DROP CONSTRAINT IF EXISTS fk_bjsdw_jurisdiction_id;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

ALTER TABLE bronze.bronze_jurisdictions_school_districts  DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_school_districts
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS ('s-' || usps || '-' || geoid) STORED;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_school_districts
        ADD CONSTRAINT uq_bjsd_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_bjsd_jurisdiction_id ON bronze.bronze_jurisdictions_school_districts(jurisdiction_id);

ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS ('s-' || usps || '-' || geoid) STORED;
ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped
    ADD CONSTRAINT fk_bjsds_jurisdiction_id
    FOREIGN KEY (jurisdiction_id)
    REFERENCES bronze.bronze_jurisdictions_school_districts(jurisdiction_id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_bjsds_jurisdiction_id ON bronze.bronze_jurisdictions_school_districts_scraped(jurisdiction_id);

DO $$ BEGIN
    UPDATE bronze.bronze_jurisdictions_school_districts_wikidata
        SET jurisdiction_id = 's-' || usps || '-' || geoid;
    ALTER TABLE bronze.bronze_jurisdictions_school_districts_wikidata
        ADD CONSTRAINT fk_bjsdw_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_school_districts(jurisdiction_id) ON DELETE CASCADE;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- ═════════════════════════════════════════════════════════════════════════════
-- PLACE_ZCTA   z-{state_fips}-{zcta}   (crosswalk — no UNIQUE, no FK)
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE bronze.bronze_jurisdictions_place_zcta DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_place_zcta
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS ('z-' || state_fips || '-' || zcta) STORED;
CREATE INDEX IF NOT EXISTS idx_bjpz_jurisdiction_id ON bronze.bronze_jurisdictions_place_zcta(jurisdiction_id);
