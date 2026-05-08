{{
  config(
    materialized='table',
    tags=['silver', 'jurisdictions']
  )
}}

/*
Silver Jurisdictions - Cleaned & Standardized

This model replaces fix_geoid_format.py by applying data quality fixes
in the transformation layer (bronze → silver).

Data Quality Fixes:
1. Pad GEOIDs to correct length (2, 5, or 7 digits)
2. Ensure FIPS codes are properly formatted
3. Clean and standardize names
4. Add derived fields

Source: bronze_jurisdictions (in `open_navigator.bronze` schema)
*/

WITH source_data AS (
    SELECT *
    FROM {{ source('bronze', 'bronze_jurisdictions') }}
),

cleaned AS (
    SELECT
        id,
        name,
        type,
        state_code,
        state,
        county,
        
        -- Fix GEOID padding to Census Bureau standards
        CASE 
            WHEN type = 'state' THEN LPAD(geoid, 2, '0')
            WHEN type = 'county' THEN LPAD(geoid, 5, '0')
            WHEN type IN ('city', 'town', 'village', 'borough', 'cdp', 'place') THEN LPAD(geoid, 7, '0')
            WHEN type = 'township' THEN LPAD(geoid, 10, '0')
            WHEN type = 'school_district' THEN LPAD(geoid, 7, '0')
            ELSE geoid
        END AS geoid_clean,
        
        geoid AS geoid_raw,
        
        -- FIPS code (same as GEOID for most jurisdiction types)
        CASE 
            WHEN type = 'state' THEN LPAD(fips_code, 2, '0')
            WHEN type = 'county' THEN LPAD(fips_code, 5, '0')
            ELSE fips_code
        END AS fips_code_clean,
        
        fips_code AS fips_code_raw,
        
        -- ANSI standard code (8-digit for places)
        ansicode,
        
        -- Legacy ncsid column
        ncsid,
        
        population,
        area_sq_miles,
        latitude,
        longitude,
        website_url,
        source,
        created_at,
        updated_at,
        
        -- Derived fields
        CASE 
            WHEN type IN ('city', 'town', 'village', 'borough') THEN 'municipality'
            WHEN type = 'cdp' THEN 'census_designated_place'
            WHEN type = 'county' THEN 'county'
            WHEN type = 'state' THEN 'state'
            WHEN type = 'township' THEN 'township'
            WHEN type = 'school_district' THEN 'school_district'
            ELSE 'other'
        END AS jurisdiction_category,
        
        -- Extract state FIPS from GEOID
        CASE 
            WHEN LENGTH(geoid) >= 2 THEN LEFT(geoid, 2)
            ELSE NULL
        END AS state_fips_from_geoid,
        
        CURRENT_TIMESTAMP AS transformed_at
        
    FROM source_data
),

with_quality_flags AS (
    SELECT
        *,
        
        -- Data quality flags
        CASE WHEN geoid_clean IS NULL THEN TRUE ELSE FALSE END AS missing_geoid,
        CASE WHEN state_code IS NULL THEN TRUE ELSE FALSE END AS missing_state_code,
        CASE WHEN name IS NULL OR TRIM(name) = '' THEN TRUE ELSE FALSE END AS missing_name,
        
        -- GEOID format validation
        CASE 
            WHEN type = 'state' AND LENGTH(geoid_clean) != 2 THEN TRUE
            WHEN type = 'county' AND LENGTH(geoid_clean) != 5 THEN TRUE
            WHEN type IN ('city', 'town', 'village', 'borough', 'place') AND LENGTH(geoid_clean) != 7 THEN TRUE
            ELSE FALSE
        END AS invalid_geoid_length
        
    FROM cleaned
)

SELECT * FROM with_quality_flags

-- dbt doesn't support comments in the final SELECT, so adding them here:
-- This table should be used for:
-- 1. Linking with other jurisdiction tables
-- 2. Joining with demographic data
-- 3. Building gold-layer aggregated views
