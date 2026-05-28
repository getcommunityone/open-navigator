/*
Enrich bronze_organizations_nonprofits with place_geoid (city jurisdiction link)

This script:
1. Adds place_geoid column to bronze_organizations_nonprofits
2. Links nonprofits to city jurisdictions using ZIP-to-place mapping
3. Reports match statistics

Why this is needed:
- Nonprofits have city="TUSCALOOSA" (text) but no link to Tuscaloosa city jurisdiction
- When users filter by city jurisdiction, we need place_geoid to find relevant nonprofits
- Uses bronze_jurisdictions_zip_place to map ZIP codes to place GEOIDs

Run with:
    PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator_bronze -f packages/scrapers/src/scrapers/census/enrich_nonprofits_with_place_geoid.sql
*/

-- Step 1: Add place_geoid column if it doesn't exist
ALTER TABLE bronze_organizations_nonprofits 
ADD COLUMN IF NOT EXISTS place_geoid VARCHAR(7);

-- Step 2: Create index on zip_code for faster joins
CREATE INDEX IF NOT EXISTS idx_bronze_orgs_zip_code_place 
ON bronze_organizations_nonprofits(zip_code) 
WHERE zip_code IS NOT NULL;

-- Step 3: Find primary place for each ZCTA (place with most land area in that ZCTA)
\echo ''
\echo '========================================='
\echo 'Step 1: Identifying Primary Place per ZCTA'
\echo '========================================='

CREATE TEMP TABLE primary_place_per_zcta AS
SELECT DISTINCT ON (zcta)
    zcta,
    place_geoid,
    place_name,
    state_fips,
    arealand_part
FROM bronze_jurisdictions_zip_place
ORDER BY zcta, arealand_part DESC;  -- For each ZCTA, take place with most land area

CREATE INDEX idx_temp_zcta_place ON primary_place_per_zcta(zcta);

SELECT COUNT(*) as zctas_with_primary_place FROM primary_place_per_zcta;

-- Step 4: Update nonprofits with place_geoid using ZIP-to-place mapping
\echo ''
\echo '========================================='
\echo 'Step 2: Enriching Nonprofits with place_geoid'
\echo '========================================='

UPDATE bronze_organizations_nonprofits AS n
SET place_geoid = p.place_geoid
FROM primary_place_per_zcta AS p
WHERE n.zip_code IS NOT NULL
  AND LEFT(n.zip_code, 5) = p.zcta;

-- Step 5: Report final statistics
\echo ''
\echo '========================================='
\echo 'Place GEOID Enrichment Statistics'
\echo '========================================='
\echo ''

SELECT 
    '📊 Total Nonprofits' as metric,
    COUNT(*)::text as count,
    '100%' as percentage
FROM bronze_organizations_nonprofits
UNION ALL
SELECT 
    '  Has ZIP code',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE zip_code IS NOT NULL
UNION ALL
SELECT 
    '  ✅ Matched to place_geoid',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE place_geoid IS NOT NULL
UNION ALL
SELECT 
    '  ❌ No place match',
    COUNT(*)::text,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_organizations_nonprofits), 1)::text || '%'
FROM bronze_organizations_nonprofits
WHERE zip_code IS NOT NULL AND place_geoid IS NULL;

\echo ''
\echo 'Top 10 cities by nonprofit count:'
SELECT 
    p.place_name,
    j.state_code,
    COUNT(*) as org_count,
    p.place_geoid
FROM bronze_organizations_nonprofits n
JOIN primary_place_per_zcta p ON n.place_geoid = p.place_geoid
JOIN bronze_jurisdictions j ON j.geoid = p.place_geoid AND j.type IN ('city', 'town', 'village', 'borough', 'place')
WHERE n.place_geoid IS NOT NULL
GROUP BY p.place_name, j.state_code, p.place_geoid
ORDER BY COUNT(*) DESC
LIMIT 10;

\echo ''
\echo 'Tuscaloosa city verification:'
SELECT 
    'Tuscaloosa city nonprofits' as metric,
    COUNT(*)::text as count
FROM bronze_organizations_nonprofits
WHERE place_geoid = '0177256'  -- Tuscaloosa city
UNION ALL
SELECT 
    'All TUSCALOOSA city records',
    COUNT(*)::text
FROM bronze_organizations_nonprofits
WHERE city ILIKE '%tuscaloosa%' AND state_code = 'AL';

\echo ''
\echo 'Sample Tuscaloosa nonprofits with place_geoid:'
SELECT 
    ein,
    LEFT(org_name, 40) as org_name,
    city,
    LEFT(zip_code, 5) as zip,
    place_geoid,
    county_fips
FROM bronze_organizations_nonprofits
WHERE place_geoid = '0177256'
ORDER BY RANDOM()
LIMIT 5;

\echo ''
\echo '✅ Place GEOID enrichment complete!'
\echo ''
