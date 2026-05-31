-- Migration: rename bronze.bronze_schools_nces -> bronze.bronze_jurisdictions_schools
--
-- NCES CCD school-level (individual school) snapshot. Renamed to the
-- bronze_jurisdictions_* family so it sits alongside its parent districts
-- (bronze_jurisdictions_school_districts_nces_directory). Each school's
-- leaid is the Local Education Agency (district) NCES id; this migration
-- formalizes that parent link with a foreign key to the district directory
-- PK (nces_id) plus a supporting index. Link coverage is 100% at write time
-- (102,178 / 102,178 schools resolve to a loaded district).
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -v ON_ERROR_STOP=1 \
--     -f packages/hosting/scripts/neon/migrations/088_rename_bronze_schools_nces_to_jurisdictions_schools.sql

BEGIN;

-- 1. Rename the table (Postgres carries dependent objects + the PK index along).
ALTER TABLE IF EXISTS bronze.bronze_schools_nces
    RENAME TO bronze_jurisdictions_schools;

-- 2. Rename the carried-over PK index to match the new table name.
ALTER INDEX IF EXISTS bronze.bronze_schools_nces_pkey
    RENAME TO bronze_jurisdictions_schools_pkey;

-- 3. Index the parent key for the school -> district roll-up join.
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdictions_schools_leaid
    ON bronze.bronze_jurisdictions_schools (leaid);

-- 4. Link each school to its district. leaid (school-level LEA id) references
--    the district directory PK nces_id. Validates immediately given 100%
--    coverage; future school loads must land their district first.
ALTER TABLE bronze.bronze_jurisdictions_schools
    ADD CONSTRAINT fk_bronze_jurisdictions_schools_district
    FOREIGN KEY (leaid)
    REFERENCES bronze.bronze_jurisdictions_school_districts_nces_directory (nces_id);

COMMIT;
