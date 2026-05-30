-- Migration 011: Add jurisdiction_type and jurisdiction_id_source to bronze jurisdiction tables.
--
-- Uses proper ENUM types rather than TEXT — rejects invalid values at the type level,
-- stores as a 4-byte OID internally, and self-documents the allowed values.
--
-- jurisdiction_type values:
--   'state', 'county', 'municipality', 'school_district', 'zcta'
--
-- jurisdiction_id_source values (what field the jurisdiction_id is derived from):
--   'usps', 'county_fips', 'place_geoid', 'school_district_geoid', 'zip_code'
--
-- Idempotent: safe to re-run.

-- ─────────────────────────────────────────────────────────────────────────────
-- Enum types (created once in the bronze schema)
-- ─────────────────────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE bronze.jurisdiction_type_enum AS ENUM (
        'state',
        'county',
        'municipality',
        'school_district',
        'zcta'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE bronze.jurisdiction_id_source_enum AS ENUM (
        'usps',
        'county_fips',
        'place_geoid',
        'school_district_geoid',
        'zip_code'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- Base jurisdiction tables
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_states
    ADD COLUMN IF NOT EXISTS jurisdiction_type
        bronze.jurisdiction_type_enum NOT NULL DEFAULT 'state',
    ADD COLUMN IF NOT EXISTS jurisdiction_id_source
        bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'usps';

ALTER TABLE bronze.bronze_jurisdictions_counties
    ADD COLUMN IF NOT EXISTS jurisdiction_type
        bronze.jurisdiction_type_enum NOT NULL DEFAULT 'county',
    ADD COLUMN IF NOT EXISTS jurisdiction_id_source
        bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'county_fips';

ALTER TABLE bronze.bronze_jurisdictions_municipalities
    ADD COLUMN IF NOT EXISTS jurisdiction_type
        bronze.jurisdiction_type_enum NOT NULL DEFAULT 'municipality',
    ADD COLUMN IF NOT EXISTS jurisdiction_id_source
        bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'place_geoid';

ALTER TABLE bronze.bronze_jurisdictions_school_districts
    ADD COLUMN IF NOT EXISTS jurisdiction_type
        bronze.jurisdiction_type_enum NOT NULL DEFAULT 'school_district',
    ADD COLUMN IF NOT EXISTS jurisdiction_id_source
        bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'school_district_geoid';

ALTER TABLE bronze.bronze_jurisdictions_place_zcta
    ADD COLUMN IF NOT EXISTS jurisdiction_type
        bronze.jurisdiction_type_enum NOT NULL DEFAULT 'zcta',
    ADD COLUMN IF NOT EXISTS jurisdiction_id_source
        bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'zip_code';

-- ─────────────────────────────────────────────────────────────────────────────
-- _scraped tables
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_states_scraped
    ADD COLUMN IF NOT EXISTS jurisdiction_type
        bronze.jurisdiction_type_enum NOT NULL DEFAULT 'state',
    ADD COLUMN IF NOT EXISTS jurisdiction_id_source
        bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'usps';

ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    ADD COLUMN IF NOT EXISTS jurisdiction_type
        bronze.jurisdiction_type_enum NOT NULL DEFAULT 'municipality',
    ADD COLUMN IF NOT EXISTS jurisdiction_id_source
        bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'place_geoid';

ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    ADD COLUMN IF NOT EXISTS jurisdiction_type
        bronze.jurisdiction_type_enum NOT NULL DEFAULT 'county',
    ADD COLUMN IF NOT EXISTS jurisdiction_id_source
        bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'county_fips';

ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped
    ADD COLUMN IF NOT EXISTS jurisdiction_type
        bronze.jurisdiction_type_enum NOT NULL DEFAULT 'school_district',
    ADD COLUMN IF NOT EXISTS jurisdiction_id_source
        bronze.jurisdiction_id_source_enum NOT NULL DEFAULT 'school_district_geoid';
