{{
    config(
        materialized='table',
        unique_key='ein'
    )
}}

/*
    Combined Nonprofit Organizations - IRS + NCCS Enrichment
    
    Base: IRS Business Master File (BMF) - 1.95M organizations
    Enrichment: NCCS Core data - adds geographic coordinates, CBSA, detailed financials
    
    Join Strategy: LEFT JOIN on EIN (all IRS records + NCCS enrichment where available)
    Coverage: ~794k organizations have both IRS and NCCS data
    
    Column Selection:
    - IRS columns: Primary source for basic nonprofit data
    - NCCS-only columns: Geographic enrichment, detailed financials, metadata
    - Conflicts: IRS columns take precedence (e.g., ntee_cd from IRS, not NCCS)
*/

WITH irs_base AS (
    SELECT * FROM {{ source('bronze', 'bronze_organizations_nonprofits_irs') }}
),

nccs_enrichment AS (
    SELECT * FROM {{ source('bronze', 'bronze_organizations_nonprofits_nccs') }}
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
        
        -- Data quality flags
        CASE 
            WHEN nccs.ein IS NOT NULL THEN true 
            ELSE false 
        END as has_nccs_data,
        
        CASE 
            WHEN nccs.latitude IS NOT NULL AND nccs.longitude IS NOT NULL THEN true
            ELSE false
        END as has_geocoding,
        
        -- Timestamps
        irs.loaded_at as irs_loaded_at,
        nccs.loaded_at as nccs_loaded_at,
        GREATEST(irs.loaded_at, COALESCE(nccs.loaded_at, irs.loaded_at)) as last_updated
        
    FROM irs_base irs
    LEFT JOIN nccs_enrichment nccs ON irs.ein = nccs.ein
)

SELECT * FROM combined
