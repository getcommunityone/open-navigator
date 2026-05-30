-- Migration: Create canonical OpenCivicData jurisdiction reference table.
--
-- bronze_jurisdiction_ocd is the authoritative source for all US jurisdictions
-- with their OpenCivicData IDs. Pre-loaded on first run, then used for fast
-- OCD ID lookups without needing to parse CSV files.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/042_create_bronze_jurisdiction_ocd.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_ocd (
    ocd_id TEXT PRIMARY KEY,
    state_code CHAR(2) NOT NULL,
    jurisdiction_type TEXT,  -- 'county', 'place', 'school_district', etc.
    name TEXT NOT NULL,
    parent_ocd_id TEXT,  -- For hierarchical references (e.g., county parent of school districts)
    loaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ocd_state_valid CHECK (state_code ~ '^[A-Z]{2}$')
);

COMMENT ON TABLE bronze.bronze_jurisdiction_ocd IS
    'Canonical OpenCivicData jurisdiction reference. Authoritative source for all US jurisdictions with OCD IDs. Pre-loaded from ocd-division-ids project.';

COMMENT ON COLUMN bronze.bronze_jurisdiction_ocd.ocd_id IS
    'OpenCivicData division ID (e.g., ocd-division/country:us/state:ma/county:suffolk)';

COMMENT ON COLUMN bronze.bronze_jurisdiction_ocd.state_code IS
    'US state code (2-letter, uppercase)';

COMMENT ON COLUMN bronze.bronze_jurisdiction_ocd.jurisdiction_type IS
    'Type of jurisdiction: county, place (municipality), school_district, etc.';

COMMENT ON COLUMN bronze.bronze_jurisdiction_ocd.name IS
    'Canonical jurisdiction name';

COMMENT ON COLUMN bronze.bronze_jurisdiction_ocd.parent_ocd_id IS
    'Parent jurisdiction OCD ID (e.g., county for school districts within it)';

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_bronze_ocd_state ON bronze.bronze_jurisdiction_ocd(state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_ocd_type ON bronze.bronze_jurisdiction_ocd(jurisdiction_type);
CREATE INDEX IF NOT EXISTS idx_bronze_ocd_name ON bronze.bronze_jurisdiction_ocd(name);
CREATE INDEX IF NOT EXISTS idx_bronze_ocd_parent ON bronze.bronze_jurisdiction_ocd(parent_ocd_id);

COMMIT;
