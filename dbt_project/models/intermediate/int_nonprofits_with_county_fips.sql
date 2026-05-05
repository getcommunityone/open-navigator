{{
    config(
        materialized='view',
        schema='public'
    )
}}

/*
Enrich bronze_organizations_nonprofits with county FIPS codes

This model joins nonprofits with bronze_jurisdictions to add county_fips
based on matching census_county_name to county names.

Match logic:
1. Exact match on county name and state_code
2. Handles "County" suffix variations (e.g., "Macoupin County" vs "Macoupin")
3. Reports match statistics

Sources:
- bronze_organizations_nonprofits (has census_county_name from geocoding)
- bronze_jurisdictions (has county fips_code)
*/

WITH nonprofits AS (
    SELECT 
        ein,
        org_name,
        city,
        state_code,
        census_county_name,
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

matched AS (
    SELECT 
        n.ein,
        n.org_name,
        n.city,
        n.state_code,
        n.census_county_name,
        c.county_fips,
        c.name as matched_county_name,
        CASE 
            WHEN c.county_fips IS NOT NULL THEN TRUE 
            ELSE FALSE 
        END as has_county_fips
    FROM nonprofits n
    LEFT JOIN counties c 
        ON n.state_code = c.state_code
        AND (
            -- Exact match on original name
            n.census_county_name = c.name
            -- Match on cleaned name (without " County")
            OR n.county_name_clean = REPLACE(c.name, ' County', '')
        )
)

SELECT * FROM matched

/*
Usage after materialization:

-- Add column to bronze table (run once)
ALTER TABLE bronze_organizations_nonprofits 
ADD COLUMN IF NOT EXISTS county_fips VARCHAR(5);

-- Update bronze table with matched FIPS codes
UPDATE bronze_organizations_nonprofits AS b
SET county_fips = m.county_fips
FROM {{ this }} AS m
WHERE b.ein = m.ein;

-- Check match statistics
SELECT 
    COUNT(*) as total_nonprofits,
    COUNT(county_fips) as matched_with_fips,
    COUNT(*) - COUNT(county_fips) as unmatched,
    ROUND(100.0 * COUNT(county_fips) / COUNT(*), 2) as match_percentage
FROM bronze_organizations_nonprofits;
*/
