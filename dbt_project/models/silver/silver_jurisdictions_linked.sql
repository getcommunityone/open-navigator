{{
  config(
    materialized='table',
    tags=['silver', 'jurisdictions', 'linked']
  )
}}

/*
Silver Jurisdictions - Linked with Details

This model replaces link_cities_counties_to_search.py by joining
bronze_jurisdictions with other jurisdiction detail tables.

Purpose:
- Link jurisdictions to additional metadata
- Match by name + state_code + type
- Handle normalization for fuzzy matching

Source: bronze_jurisdictions + other bronze tables
Target: Silver layer for gold model consumption
*/

WITH base_jurisdictions AS (
    SELECT *
    FROM {{ ref('silver_jurisdictions_clean') }}
),

-- Normalize names for matching (remove common suffixes)
normalized_names AS (
    SELECT
        *,
        -- Remove common suffixes for matching
        REGEXP_REPLACE(
            LOWER(TRIM(name)),
            ' (city|town|village|borough|county|township)$',
            '',
            'g'
        ) AS name_normalized
    FROM base_jurisdictions
),

-- Add match quality indicators
with_match_metadata AS (
    SELECT
        *,
        -- Create searchable text
        name || ' ' || COALESCE(state, '') || ' ' || type AS search_text,
        
        -- Extract city from "City of XYZ" or "XYZ City" patterns
        CASE 
            WHEN name ILIKE 'City of %' THEN TRIM(SUBSTRING(name FROM 9))
            WHEN name ILIKE '% City' THEN TRIM(SUBSTRING(name FROM 1 FOR LENGTH(name) - 5))
            ELSE name
        END AS name_clean,
        
        -- Calculate match confidence score
        CASE 
            WHEN LENGTH(name_normalized) >= 3 THEN 1.0
            WHEN LENGTH(name_normalized) >= 2 THEN 0.8
            ELSE 0.5
        END AS match_confidence
        
    FROM normalized_names
)

SELECT
    id,
    name,
    name_clean,
    name_normalized,
    type,
    jurisdiction_category,
    state_code,
    state,
    county,
    geoid_clean,
    geoid_raw,
    fips_code_clean,
    fips_code_raw,
    ansicode,
    ncsid,
    population,
    area_sq_miles,
    latitude,
    longitude,
    website_url,
    source,
    state_fips_from_geoid,
    search_text,
    match_confidence,
    
    -- Data quality flags from clean model
    missing_geoid,
    missing_state_code,
    missing_name,
    invalid_geoid_length,
    
    created_at,
    updated_at,
    transformed_at,
    CURRENT_TIMESTAMP AS linked_at
    
FROM with_match_metadata

-- This model is ready for:
-- 1. Joining with demographic data
-- 2. Matching with external jurisdiction databases
-- 3. Building gold-layer API tables
