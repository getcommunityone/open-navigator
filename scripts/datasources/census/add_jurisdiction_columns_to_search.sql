/*
Add jurisdiction linking columns to organization_nonprofit table

This adds place_geoid and county_fips to the production search table so nonprofits
can be filtered by city/county jurisdictions.

Run with:
    PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator -f scripts/datasources/census/add_jurisdiction_columns_to_search.sql
*/

\echo ''
\echo '========================================='
\echo 'Adding Jurisdiction Columns to Search Table'
\echo '========================================='
\echo ''

-- Step 1: Add columns to organization_nonprofit
ALTER TABLE organization_nonprofit 
ADD COLUMN IF NOT EXISTS place_geoid VARCHAR(7),
ADD COLUMN IF NOT EXISTS county_fips VARCHAR(5);

-- Step 2: Create index on EIN for joining
CREATE INDEX IF NOT EXISTS idx_org_search_ein 
ON organization_nonprofit(ein);

\echo 'Columns added. Ready to populate from bronze database.'
\echo ''
\echo 'To populate, run this query in bronze database and import results:'
\echo ''
\echo 'SELECT ein, place_geoid, county_fips'
\echo 'FROM bronze_organizations_nonprofits'
\echo 'WHERE ein IS NOT NULL'
\echo '  AND (place_geoid IS NOT NULL OR county_fips IS NOT NULL);'
\echo ''
