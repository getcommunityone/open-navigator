{{
    config(
        materialized='view',
        schema='public'
    )
}}

/*
Enrich bronze_organizations_nonprofits with county FIPS codes

This model joins nonprofits with county data using two methods:
1. Direct match on census_county_name (for geocoded nonprofits)
2. ZCTA-to-county mapping (for nonprofits with ZIP codes, single-county ZCTAs only)

Match logic:
- Method 1: Exact match on county name and state_code
  - Handles "County" suffix variations (e.g., "Macoupin County" vs "Macoupin")
  - Expected: ~790K matches (40% of total)
- Method 2: ZIP-to-county via single-county ZCTAs
  - Only matches ZCTAs that map to exactly one county (avoids ambiguity)
  - Expected: ~814K additional matches (42% of total)
- Total expected match rate: ~82%

Sources:
- bronze_organizations_nonprofits (has census_county_name and zip_code)
- bronze_jurisdictions (has county fips_code)
- bronze_jurisdictions_zip_county (has ZCTA to county mappings)

Note: This is a documentation model. Actual enrichment is done via SQL script.

Actual enrichment script: scripts/datasources/census/enrich_nonprofits_with_county_fips.sql
*/

WITH nonprofits AS (
    SELECT 
        ein,
        org_name,
        city,
        state_code,
        census_county_name,
        zip_code,
        LEFT(zip_code, 5) as zip_code_5,
        -- Clean county name for matching (remove " County" suffix)
        CASE 
            WHEN census_county_name LIKE '% County' 
            THEN REPLACE(census_county_name, ' County', '')
            ELSE census_county_name
        END as county_name_clean
    FROM {{ source('bronze', 'bronze_organizations_nonprofits') }}
),

counties AS (
    SELECT 
        name,
        state_code,
        fips_code as county_fips,
        geoid
    FROM {{ source('bronze', 'bronze_jurisdictions') }}
    WHERE type = 'county'
),

-- Method 1: Match via census_county_name
matched_via_county_name AS (
    SELECT 
        n.ein,
        n.org_name,
        n.city,
        n.state_code,
        n.census_county_name,
        n.zip_code,
        c.county_fips,
        c.name as matched_county_name,
        'census_county_name' as match_method,
        1 as method_priority
    FROM nonprofits n
    INNER JOIN counties c 
        ON n.state_code = c.state_code
        AND n.census_county_name IS NOT NULL
        AND (
            -- Exact match on original name
            n.census_county_name = c.name
            -- Match on cleaned name (without " County")
            OR n.county_name_clean = REPLACE(c.name, ' County', '')
        )
),

-- Identify single-county ZCTAs
single_county_zctas AS (
    SELECT 
        zcta,
        county_geoid,
        county_name,
        state_fips
    FROM {{ source('bronze', 'bronze_jurisdictions_zip_county') }}
    WHERE zcta IN (
        SELECT zcta 
        FROM {{ source('bronze', 'bronze_jurisdictions_zip_county') }}
        GROUP BY zcta 
        HAVING COUNT(DISTINCT county_geoid) = 1
    )
),

-- Method 2: Match via ZCTA (for nonprofits without census_county_name)
matched_via_zcta AS (
    SELECT 
        n.ein,
        n.org_name,
        n.city,
        n.state_code,
        n.census_county_name,
        n.zip_code,
        z.county_geoid as county_fips,
        z.county_name as matched_county_name,
        'zcta_single_county' as match_method,
        2 as method_priority
    FROM nonprofits n
    INNER JOIN single_county_zctas z 
        ON n.zip_code_5 = z.zcta
    WHERE n.ein NOT IN (SELECT ein FROM matched_via_county_name)  -- Don't duplicate Method 1 matches
),

-- Combine both methods
all_matches AS (
    SELECT * FROM matched_via_county_name
    UNION ALL
    SELECT * FROM matched_via_zcta
)

SELECT 
    ein,
    org_name,
    city,
    state_code,
    census_county_name,
    zip_code,
    county_fips,
    matched_county_name,
    match_method,
    CASE 
        WHEN county_fips IS NOT NULL THEN TRUE 
        ELSE FALSE 
    END as has_county_fips
FROM all_matches
ORDER BY ein

/*
Usage after materialization:

-- Add column to bronze table (run once)
ALTER TABLE bronze_organizations_nonprofits 
ADD COLUMN IF NOT EXISTS county_fips VARCHAR(5);

-- Update bronze table with matched FIPS codes
-- NOTE: Use the SQL script instead:
-- scripts/datasources/census/enrich_nonprofits_with_county_fips.sql

-- Check match statistics
SELECT 
    match_method,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM {{ this }}
GROUP BY match_method;
*/
