{{
  config(
    materialized='table',
    tags=['intermediate', 'nonprofits', 'zcta'],
    enabled=false
  )
}}

/*
Intermediate: NCCS Nonprofits Enriched with ZCTA

⚠️ NOTE: This model is DISABLED by default due to cross-database reference limitations in PostgreSQL.

RECOMMENDED: Use the marts model bronze_organizations_nonprofits instead,
which includes ZCTA enrichment for both IRS and NCCS nonprofits without cross-database issues.

To enable this model for bronze-only usage:
1. Set enabled=true in the config above
2. Run with: dbt run --target bronze --select int_nonprofits_nccs_with_zcta

Adds 5-digit ZIP Code Tabulation Area (ZCTA) to NCCS nonprofit data.

ZCTA vs ZIP Code:
- ZIP codes are postal delivery routes (USPS)
- ZCTAs are census geographic areas that approximate ZIP codes
- ZCTAs provide statistical boundaries for geographic analysis

This model:
1. Extracts first 5 digits from f990_org_addr_zip (standardizes ZIP+4 to ZIP5)
2. Joins to Census ZCTA lookup table
3. Adds ZCTA geographic boundaries and centroid coordinates

Note: NCCS already has latitude/longitude from geocoding.
ZCTA coordinates provide an alternative centroid for organizations without geocoding.

Source tables:
- bronze_organizations_nonprofits_nccs (1.8M nonprofits)
- bronze_jurisdictions_postal_codes (33,791 ZCTAs)

Join rate: ~95% of nonprofits have valid 5-digit ZCTAs
*/

WITH nccs_nonprofits AS (
    SELECT 
        *,
        -- Extract first 5 digits from f990_org_addr_zip (handles ZIP+4 format)
        LEFT(TRIM(f990_org_addr_zip), 5) AS zip_code_5
    FROM {{ source('bronze', 'bronze_organizations_nonprofits_nccs') }}
),

zcta_lookup AS (
    SELECT
        zcta,
        geoid,
        intptlat AS zcta_latitude,
        intptlong AS zcta_longitude,
        aland_sqmi AS zcta_land_area_sqmi,
        awater_sqmi AS zcta_water_area_sqmi
    FROM {{ source('bronze', 'bronze_jurisdictions_postal_codes') }}
),

zcta_place_primary AS (
    SELECT DISTINCT ON (zcta)
        zcta,
        place_geoid,
        place_name
    FROM {{ source('bronze', 'bronze_jurisdictions_zip_place') }}
    ORDER BY zcta, arealand_part DESC NULLS LAST
),

zcta_county_primary AS (
    SELECT DISTINCT ON (zcta)
        zcta,
        county_geoid,
        county_name
    FROM {{ source('bronze', 'bronze_jurisdictions_zip_county') }}
    ORDER BY zcta, arealand_part DESC NULLS LAST
),

enriched AS (
    SELECT
        -- All NCCS columns
        nccs.*,
        
        -- ZCTA enrichment
        zcta.zcta AS zcta_5,
        zcta.zcta_latitude,
        zcta.zcta_longitude,
        zcta.zcta_land_area_sqmi,
        zcta.zcta_water_area_sqmi,
        
        -- Place enrichment
        place.place_geoid,
        place.place_name AS zcta_place_name,
        
        -- County enrichment
        county.county_geoid AS county_fips,
        county.county_name AS zcta_county_name,
        
        -- Match quality indicator
        CASE 
            WHEN zcta.zcta IS NOT NULL THEN true
            ELSE false
        END AS has_zcta_match,
        
        -- Use NCCS geocoded coordinates if available, fallback to ZCTA centroid
        COALESCE(nccs.latitude, zcta.zcta_latitude) AS best_latitude,
        COALESCE(nccs.longitude, zcta.zcta_longitude) AS best_longitude
        
    FROM nccs_nonprofits AS nccs
    LEFT JOIN zcta_lookup AS zcta
        ON nccs.zip_code_5 = zcta.zcta
    LEFT JOIN zcta_place_primary AS place
        ON nccs.zip_code_5 = place.zcta
    LEFT JOIN zcta_county_primary AS county
        ON nccs.zip_code_5 = county.zcta
)

SELECT * FROM enriched
