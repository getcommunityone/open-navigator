{{
    config(
        materialized='table',
        unique_key='ein'
    )
}}

/*
    Combined Nonprofit Organizations - IRS + NCCS + ZCTA Enrichment
    
    Base: IRS Business Master File (BMF) - 1.95M organizations
    Enrichment: 
      - NCCS Core data: geographic coordinates, CBSA, detailed financials
      - Census ZCTA: ZIP Code Tabulation Areas for geographic analysis
    
    Join Strategy: LEFT JOIN on EIN (all IRS records + NCCS enrichment where available)
    Coverage: 
      - ~794k organizations have both IRS and NCCS data
      - ~95% have valid ZCTA matches
    
    Column Selection:
    - IRS columns: Primary source for basic nonprofit data
    - NCCS-only columns: Geographic enrichment, detailed financials, metadata
    - ZCTA columns: Census geographic boundaries and centroids
    - Conflicts: IRS columns take precedence (e.g., ntee_cd from IRS, not NCCS)
*/

WITH irs_base AS (
    SELECT 
        *,
        LEFT(TRIM(zip_code), 5) AS zip_code_5
    FROM {{ source('bronze', 'bronze_organizations_nonprofits_irs') }}
),

nccs_enrichment AS (
    SELECT 
        *,
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

-- Get primary place for each ZCTA (largest by land area)
zcta_place_primary AS (
    SELECT DISTINCT ON (zcta)
        zcta,
        place_geoid,
        place_name
    FROM {{ source('bronze', 'bronze_jurisdictions_zip_place') }}
    ORDER BY zcta, arealand_part DESC NULLS LAST
),

-- Get primary county for each ZCTA (largest by land area)  
zcta_county_primary AS (
    SELECT DISTINCT ON (zcta)
        zcta,
        county_geoid,
        county_name
    FROM {{ source('bronze', 'bronze_jurisdictions_zip_county') }}
    ORDER BY zcta, arealand_part DESC NULLS LAST
),

combined AS (
    SELECT
        -- Primary key
        irs.ein,
        
        -- IRS Core columns (base data)
        irs.id as irs_id,
        irs.name as org_name,
        irs.ico,
        irs.street,
        irs.city,
        irs.state_code,
        irs.zip_code,
        irs.country,
        
        -- IRS Classification
        irs.ntee_cd,
        irs.subsection,
        irs.affiliation,
        irs.classification,
        irs.ruling,
        irs.deductibility,
        irs.foundation,
        irs.activity,
        irs.organization,
        irs.status,
        
        -- IRS Financials (current)
        irs.asset_amt as irs_asset_amt,
        irs.income_amt as irs_income_amt,
        irs.revenue_amt as irs_revenue_amt,
        irs.asset_cd,
        irs.income_cd,
        
        -- IRS Administrative
        irs.group_exemption,
        irs.filing_req_cd,
        irs.pf_filing_req_cd,
        irs.tax_period,
        irs.acct_pd,
        irs.sort_name,
        
        -- NCCS Enrichment: Geographic data
        nccs.latitude,
        nccs.longitude,
        nccs.geocoder_score,
        nccs.geocoder_match,
        nccs.census_cbsa_fips,
        nccs.census_cbsa_name,
        nccs.census_block_fips,
        nccs.census_urban_area,
        nccs.census_state_abbr,
        nccs.census_county_name,
        
        -- NCCS Enrichment: Additional NTEE classifications
        nccs.ntee_nccs,
        nccs.nteev2,
        nccs.nccs_level_1,
        nccs.nccs_level_2,
        nccs.nccs_level_3,
        
        -- NCCS Enrichment: 990 Financials (more recent/detailed)
        nccs.f990_total_revenue_recent,
        nccs.f990_total_income_recent,
        nccs.f990_total_assets_recent,
        nccs.f990_total_expenses_recent,
        
        -- NCCS Enrichment: Organization metadata
        nccs.org_name_current,
        nccs.org_name_sec as org_name_secondary,
        nccs.org_pers_ico as org_person_in_care_of,
        nccs.org_ruling_date,
        nccs.org_ruling_year,
        nccs.org_fiscal_year,
        nccs.org_fiscal_period,
        nccs.org_year_first,
        nccs.org_year_last,
        nccs.org_year_count,
        
        -- NCCS Enrichment: Address fields (F990 version, may be more current)
        nccs.f990_org_addr_street,
        nccs.f990_org_addr_city,
        nccs.f990_org_addr_state,
        nccs.f990_org_addr_zip,
        nccs.org_addr_full,
        nccs.org_addr_match,
        
        -- ZCTA Enrichment: Census geographic areas
        -- Prefer IRS ZCTA if available (from IRS zip_code), fallback to NCCS ZCTA
        COALESCE(irs_zcta.zcta, nccs_zcta.zcta) as zcta_5,
        COALESCE(irs_zcta.zcta_latitude, nccs_zcta.zcta_latitude) as zcta_latitude,
        COALESCE(irs_zcta.zcta_longitude, nccs_zcta.zcta_longitude) as zcta_longitude,
        COALESCE(irs_zcta.zcta_land_area_sqmi, nccs_zcta.zcta_land_area_sqmi) as zcta_land_area_sqmi,
        COALESCE(irs_zcta.zcta_water_area_sqmi, nccs_zcta.zcta_water_area_sqmi) as zcta_water_area_sqmi,
        
        -- Place (city/town) from ZCTA - primary place by largest land area
        COALESCE(irs_place.place_geoid, nccs_place.place_geoid) as place_geoid,
        COALESCE(irs_place.place_name, nccs_place.place_name) as zcta_place_name,
        
        -- County from ZCTA - primary county by largest land area  
        COALESCE(irs_county.county_geoid, nccs_county.county_geoid) as county_fips,
        COALESCE(irs_county.county_name, nccs_county.county_name) as zcta_county_name,
        
        -- Best available coordinates (NCCS geocoded > IRS ZCTA > NCCS ZCTA)
        COALESCE(nccs.latitude, irs_zcta.zcta_latitude, nccs_zcta.zcta_latitude) as best_latitude,
        COALESCE(nccs.longitude, irs_zcta.zcta_longitude, nccs_zcta.zcta_longitude) as best_longitude,
        
        -- Data quality flags
        CASE 
            WHEN nccs.ein IS NOT NULL THEN true 
            ELSE false 
        END as has_nccs_data,
        
        CASE 
            WHEN nccs.latitude IS NOT NULL AND nccs.longitude IS NOT NULL THEN true
            ELSE false
        END as has_geocoding,
        
        CASE
            WHEN COALESCE(irs_zcta.zcta, nccs_zcta.zcta) IS NOT NULL THEN true
            ELSE false
        END as has_zcta_match,
        
        -- Timestamps
        irs.loaded_at as irs_loaded_at,
        nccs.loaded_at as nccs_loaded_at,
        GREATEST(irs.loaded_at, COALESCE(nccs.loaded_at, irs.loaded_at)) as last_updated
        
    FROM irs_base irs
    LEFT JOIN nccs_enrichment nccs ON irs.ein = nccs.ein
    LEFT JOIN zcta_lookup irs_zcta ON irs.zip_code_5 = irs_zcta.zcta
    LEFT JOIN zcta_lookup nccs_zcta ON nccs.zip_code_5 = nccs_zcta.zcta
    LEFT JOIN zcta_place_primary irs_place ON irs.zip_code_5 = irs_place.zcta
    LEFT JOIN zcta_place_primary nccs_place ON nccs.zip_code_5 = nccs_place.zcta
    LEFT JOIN zcta_county_primary irs_county ON irs.zip_code_5 = irs_county.zcta
    LEFT JOIN zcta_county_primary nccs_county ON nccs.zip_code_5 = nccs_county.zcta
)

SELECT * FROM combined
