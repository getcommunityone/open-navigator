{{
  config(
    materialized='table',
    tags=['gold', 'jurisdictions', 'api']
  )
}}

/*
Gold Jurisdictions - API-Ready Final Table

This is the final, cleaned, and enriched jurisdiction table for API consumption.
Combines data from bronze and silver layers with additional business logic.

Purpose:
- Single source of truth for jurisdiction data
- Optimized for API queries
- Includes all necessary fields for frontend display
- Quality-filtered (excludes invalid records)

Target: API routes (api/routes/search_postgres.py)
*/

WITH silver_jurisdictions AS (
    SELECT *
    FROM {{ ref('int_jurisdictions_linked') }}
),

-- Filter out low-quality records
quality_filtered AS (
    SELECT *
    FROM silver_jurisdictions
    WHERE
        -- Must have essential identifiers
        NOT missing_name
        AND NOT missing_state_code
        AND NOT missing_geoid
        -- GEOID must be valid length for type
        AND NOT invalid_geoid_length
        -- Must have valid type
        AND type IS NOT NULL
),

-- Add API-specific fields
api_ready AS (
    SELECT
        -- Primary identifiers
        id AS jurisdiction_id,
        geoid_clean AS geoid,
        fips_code_clean AS fips_code,
        ansicode,
        
        -- Display fields
        name,
        name_clean AS display_name,
        type AS jurisdiction_type,
        jurisdiction_category,
        
        -- Geographic hierarchy
        state_code,
        state AS state_name,
        county AS county_name,
        
        -- Demographic data
        population,
        area_sq_miles,
        
        -- Location
        latitude,
        longitude,
        
        -- Links
        website_url,
        
        -- Metadata for search
        search_text,
        
        -- Data provenance
        source AS data_source,
        match_confidence,
        
        -- Timestamps
        created_at,
        updated_at,
        transformed_at,
        linked_at,
        CURRENT_TIMESTAMP AS published_at
        
    FROM quality_filtered
)

SELECT * FROM api_ready

-- This table should be queried by:
-- - api/routes/search_postgres.py
-- - Frontend search components
-- - Data exports and downloads
