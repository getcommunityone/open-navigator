/*
Enrich bronze_organizations_nonprofits with county FIPS codes

This script:
1. Adds county_fips column to bronze_organizations_nonprofits (if not exists)
2. Updates it by joining with bronze_jurisdictions on county name + state (Method 1)
3. Updates remaining records using ZCTA-to-county mapping for single-county ZCTAs (Method 2)
4. Reports match statistics

Run with:
    PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator_bronze -f packages/scrapers/src/scrapers/census/enrich_nonprofits_with_county_fips.sql
*/

-- Step 1: Add county_fips column if it doesn't exist
ALTER TABLE bronze_organizations_nonprofits 
ADD COLUMN IF NOT EXISTS county_fips VARCHAR(5);

-- Step 2: Create indexes for faster joins
CREATE INDEX IF NOT EXISTS idx_bronze_orgs_census_county 
ON bronze_organizations_nonprofits(census_county_name, state_code) 
WHERE census_county_name IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bronze_orgs_zip_code 
ON bronze_organizations_nonprofits(zip_code) 
WHERE zip_code IS NOT NULL;

-- Step 3a: Update nonprofits with county FIPS codes using census_county_name
\echo ''
\echo '========================================='
\echo 'Method 1: Matching via census_county_name'
\echo '========================================='

UPDATE bronze_organizations_nonprofits AS n
SET county_fips = c.fips_code
FROM bronze_jurisdictions AS c
WHERE c.type = 'county'
  AND n.state_code = c.state_code
  AND n.census_county_name IS NOT NULL
  AND county_fips IS NULL  -- Only update if not already set
  AND (
      -- Exact match on county name
      n.census_county_name = c.name
      -- Match without " County" suffix
      OR REPLACE(n.census_county_name, ' County', '') = REPLACE(c.name, ' County', '')
  );

-- Report Method 1 results
SELECT 
    COUNT(*) as matched_via_county_name
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL;

-- Step 3b: Update remaining nonprofits using ZCTA-to-county mapping (single-county ZCTAs only)
\echo ''
\echo '========================================='
\echo 'Method 2: Matching via ZCTA (single-county ZCTAs only)'
\echo '========================================='

-- Create temp table of single-county ZCTAs
CREATE TEMP TABLE single_county_zctas AS
SELECT 
    zcta,
    county_geoid,
    county_name,
    state_fips
FROM bronze_jurisdictions_zip_county
WHERE zcta IN (
    SELECT zcta 
    FROM bronze_jurisdictions_zip_county 
    GROUP BY zcta 
    HAVING COUNT(DISTINCT county_geoid) = 1
);

CREATE INDEX idx_temp_zcta ON single_county_zctas(zcta);

-- Update nonprofits using ZIP-to-county mapping
UPDATE bronze_organizations_nonprofits AS n
SET county_fips = z.county_geoid
FROM single_county_zctas AS z
WHERE n.county_fips IS NULL  -- Only update if not already set
  AND n.zip_code IS NOT NULL
  AND LEFT(n.zip_code, 5) = z.zcta;  -- Match 5-digit ZIP to ZCTA

-- Report Method 2 results
SELECT 
    COUNT(*) as total_matched,
    COUNT(*) FILTER (WHERE census_county_name IS NULL) as matched_via_zcta_only
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL;

-- Step 4: Report final match statistics
\echo ''
\echo '========================================='
\echo 'Final County FIPS Enrichment Statistics'
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
    '  Has ZIP code',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE zip_code IS NOT NULL
UNION ALL
SELECT 
    '  ✅ Matched to county FIPS',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL
UNION ALL
SELECT 
    '     Via census_county_name',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL AND census_county_name IS NOT NULL
UNION ALL
SELECT 
    '     Via ZCTA (no census name)',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL AND census_county_name IS NULL
UNION ALL
SELECT 
    '  ❌ No FIPS match',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE county_fips IS NULL;

\echo ''
\echo 'Match breakdown by method:'
SELECT 
    'Total matched' as method,
    COUNT(*)::text as count,
    '100%' as pct_of_matched
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL
UNION ALL
SELECT 
    'Method 1: census_county_name',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits WHERE county_fips IS NOT NULL), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL AND census_county_name IS NOT NULL
UNION ALL
SELECT 
    'Method 2: ZCTA only',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits WHERE county_fips IS NOT NULL), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL AND census_county_name IS NULL;

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
\echo 'Sample matched nonprofits (via census_county_name):'
SELECT 
    ein,
    LEFT(org_name, 40) as org_name,
    city,
    state_code,
    LEFT(census_county_name, 20) as county,
    county_fips,
    'census_name' as method
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL AND census_county_name IS NOT NULL
ORDER BY RANDOM()
LIMIT 3;

\echo ''
\echo 'Sample matched nonprofits (via ZCTA only):'
SELECT 
    ein,
    LEFT(org_name, 40) as org_name,
    city,
    state_code,
    LEFT(zip_code, 5) as zip,
    county_fips,
    'zcta' as method
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL AND census_county_name IS NULL
ORDER BY RANDOM()
LIMIT 3;

\echo ''
\echo '✅ County FIPS enrichment complete!'
\echo ''
