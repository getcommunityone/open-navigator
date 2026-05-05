/*
Enrich bronze_organizations_nonprofits with county FIPS codes

This script:
1. Adds county_fips column to bronze_organizations_nonprofits (if not exists)
2. Updates it by joining with bronze_jurisdictions on county name + state
3. Reports match statistics

Run with:
    PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator_bronze -f scripts/datasources/census/enrich_nonprofits_with_county_fips.sql
*/

-- Step 1: Add county_fips column if it doesn't exist
ALTER TABLE bronze_organizations_nonprofits 
ADD COLUMN IF NOT EXISTS county_fips VARCHAR(5);

-- Step 2: Create index on census_county_name for faster joins
CREATE INDEX IF NOT EXISTS idx_bronze_orgs_census_county 
ON bronze_organizations_nonprofits(census_county_name, state_code) 
WHERE census_county_name IS NOT NULL;

-- Step 3: Update nonprofits with county FIPS codes
UPDATE bronze_organizations_nonprofits AS n
SET county_fips = c.fips_code
FROM bronze_jurisdictions AS c
WHERE c.type = 'county'
  AND n.state_code = c.state_code
  AND n.census_county_name IS NOT NULL
  AND (
      -- Exact match on county name
      n.census_county_name = c.name
      -- Match without " County" suffix
      OR REPLACE(n.census_county_name, ' County', '') = REPLACE(c.name, ' County', '')
  );

-- Step 4: Report match statistics
\echo ''
\echo '========================================='
\echo 'County FIPS Enrichment Statistics'
\echo '========================================='
\echo ''

SELECT 
    '📊 Total Nonprofits' as metric,
    COUNT(*)::text as count,
    '100%' as percentage
FROM bronze_organizations_nonprofits
UNION ALL
SELECT 
    '  Has census_county_name',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE census_county_name IS NOT NULL
UNION ALL
SELECT 
    '  ✅ Matched to county FIPS',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL
UNION ALL
SELECT 
    '  ❌ No FIPS match',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE census_county_name IS NOT NULL AND county_fips IS NULL;

\echo ''
\echo 'Match rate among geocoded nonprofits:'
SELECT 
    ROUND(100.0 * COUNT(*) FILTER (WHERE county_fips IS NOT NULL) / 
          COUNT(*) FILTER (WHERE census_county_name IS NOT NULL), 2)::text || '%' as match_percentage,
    COUNT(*) FILTER (WHERE county_fips IS NOT NULL) as matched,
    COUNT(*) FILTER (WHERE census_county_name IS NOT NULL) as geocoded_total
FROM bronze_organizations_nonprofits;

\echo ''
\echo 'Top 10 states by matched nonprofits:'
SELECT 
    state_code,
    COUNT(*) FILTER (WHERE county_fips IS NOT NULL) as matched_orgs,
    COUNT(*) as total_orgs,
    ROUND(100.0 * COUNT(*) FILTER (WHERE county_fips IS NOT NULL) / COUNT(*), 1)::text || '%' as match_rate
FROM bronze_organizations_nonprofits
WHERE state_code IS NOT NULL
GROUP BY state_code
ORDER BY COUNT(*) FILTER (WHERE county_fips IS NOT NULL) DESC
LIMIT 10;

\echo ''
\echo 'Sample matched nonprofits:'
SELECT 
    ein,
    org_name,
    city,
    state_code,
    census_county_name,
    county_fips
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL
ORDER BY RANDOM()
LIMIT 5;

\echo ''
\echo '✅ County FIPS enrichment complete!'
\echo ''
