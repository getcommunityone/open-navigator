/*
Fast sync of jurisdiction columns from bronze to production using postgres_fdw

This uses Foreign Data Wrapper to link databases and run a single UPDATE.
Much faster than Python batching.

Run with:
    PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator -f packages/scrapers/src/scrapers/census/sync_jurisdictions_fast.sql
*/

\echo 'Setting up foreign data wrapper...'

-- Enable postgres_fdw extension
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- Drop existing server if it exists
DROP SERVER IF EXISTS bronze_server CASCADE;

-- Create foreign server pointing to bronze database
CREATE SERVER bronze_server
FOREIGN DATA WRAPPER postgres_fdw
OPTIONS (host 'localhost', port '5433', dbname 'open_navigator_bronze');

-- Create user mapping
CREATE USER MAPPING IF NOT EXISTS FOR postgres
SERVER bronze_server
OPTIONS (user 'postgres', password 'password');

-- Create foreign table for bronze nonprofits
DROP FOREIGN TABLE IF EXISTS bronze_nonprofits_fdw;
CREATE FOREIGN TABLE bronze_nonprofits_fdw (
    ein VARCHAR(10),
    place_geoid VARCHAR(7),
    county_fips VARCHAR(5)
)
SERVER bronze_server
OPTIONS (schema_name 'public', table_name 'bronze_organizations_nonprofits');

\echo 'Adding columns to organization_nonprofit...'

-- Add columns if they don't exist
ALTER TABLE organization_nonprofit 
ADD COLUMN IF NOT EXISTS place_geoid VARCHAR(7),
ADD COLUMN IF NOT EXISTS county_fips VARCHAR(5);

\echo 'Updating from bronze database (this will take ~30 seconds)...'

-- Single UPDATE statement using foreign table
UPDATE organization_nonprofit AS o
SET 
    place_geoid = b.place_geoid,
    county_fips = b.county_fips
FROM bronze_nonprofits_fdw AS b
WHERE o.ein = b.ein
  AND b.ein IS NOT NULL
  AND (b.place_geoid IS NOT NULL OR b.county_fips IS NOT NULL);

\echo 'Creating indexes...'

-- Create indexes for fast filtering
CREATE INDEX IF NOT EXISTS idx_org_search_place_geoid 
ON organization_nonprofit(place_geoid) 
WHERE place_geoid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_org_search_county_fips 
ON organization_nonprofit(county_fips) 
WHERE county_fips IS NOT NULL;

\echo ''
\echo '========================================='
\echo 'Statistics'
\echo '========================================='

-- Show statistics
SELECT 
    COUNT(*) as total_nonprofits,
    COUNT(place_geoid) as with_place_geoid,
    COUNT(county_fips) as with_county_fips,
    ROUND(100.0 * COUNT(place_geoid) / COUNT(*), 1) || '%' as pct_place,
    ROUND(100.0 * COUNT(county_fips) / COUNT(*), 1) || '%' as pct_county
FROM organization_nonprofit;

\echo ''
\echo 'Tuscaloosa city nonprofits:'
SELECT COUNT(*) FROM organization_nonprofit WHERE place_geoid = '0177256';

\echo ''
\echo '✅ Done! City filtering should now work.'
