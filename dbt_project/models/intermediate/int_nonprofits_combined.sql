{{
  config(
    materialized='table',
    tags=['silver', 'nonprofits']
  )
}}

/*
Silver Nonprofits Combined - Merge IRS and NCCS Data

Combines data from IRS BMF and NCCS sources, deduplicating by EIN.
Priority: NCCS data preferred for financials (more detailed), IRS for base info.

Source tables:
- bronze_organizations_nonprofits_irs
- bronze_organizations_nonprofits_nccs
*/

WITH irs_data AS (
    SELECT
        ein,
        name,
        COALESCE(street, '') AS street_address,
        city,
        state_code,
        zip_code,
        ntee_cd AS ntee_code,
        subsection,
        affiliation,
        classification,
        ruling,
        foundation,
        deductibility,
        status,
        tax_period,
        asset_amt AS assets,
        income_amt AS income,
        revenue_amt AS revenue,
        acct_pd AS accounting_period,
        asset_cd AS asset_code,
        income_cd AS income_code,
        filing_req_cd AS filing_requirement_code,
        pf_filing_req_cd AS pf_filing_requirement_code,
        'irs_bmf' AS datasource,
        ein AS datasource_id,
        loaded_at
    FROM {{ source('bronze', 'bronze_organizations_nonprofits_irs') }}
    WHERE ein IS NOT NULL
),

nccs_data AS (
    SELECT
        ein,
        name,
        COALESCE(f990_org_addr_street, '') AS street_address,
        f990_org_addr_city AS city,
        f990_org_addr_state AS state_code,
        f990_org_addr_zip AS zip_code,
        census_county_name AS county,
        COALESCE(ntee_nccs, ntee_irs) AS ntee_code,
        bmf_subsection_code AS subsection,
        bmf_status_code AS status,
        'nccs' AS datasource,
        ein AS datasource_id,
        loaded_at
    FROM {{ source('bronze', 'bronze_organizations_nonprofits_nccs') }}
    WHERE ein IS NOT NULL
),

-- Combine with IRS as base, NCCS as enrichment
combined AS (
    SELECT
        COALESCE(irs.ein, nccs.ein) AS ein,
        COALESCE(nccs.name, irs.name) AS name,
        COALESCE(nccs.street_address, irs.street_address) AS street_address,
        COALESCE(nccs.city, irs.city) AS city,
        COALESCE(nccs.state_code, irs.state_code) AS state_code,
        COALESCE(nccs.zip_code, irs.zip_code) AS zip_code,
        nccs.county,
        COALESCE(nccs.ntee_code, irs.ntee_code) AS ntee_code,
        irs.subsection,
        irs.affiliation,
        irs.classification,
        irs.ruling,
        irs.foundation,
        irs.deductibility,
        COALESCE(nccs.status, irs.status) AS status,
        irs.tax_period,
        irs.assets,
        irs.income,
        irs.revenue,
        irs.accounting_period,
        irs.asset_code,
        irs.income_code,
        irs.filing_requirement_code,
        irs.pf_filing_requirement_code,
        CASE 
            WHEN irs.ein IS NOT NULL AND nccs.ein IS NOT NULL THEN 'irs_bmf,nccs'
            WHEN nccs.ein IS NOT NULL THEN 'nccs'
            ELSE 'irs_bmf'
        END AS datasource,
        COALESCE(irs.ein, nccs.ein) AS datasource_id,
        GREATEST(
            COALESCE(irs.loaded_at, '1970-01-01'::timestamp),
            COALESCE(nccs.loaded_at, '1970-01-01'::timestamp)
        ) AS last_updated
    FROM irs_data irs
    FULL OUTER JOIN nccs_data nccs ON irs.ein = nccs.ein
)

SELECT
    ein,
    name,
    street_address,
    city,
    state_code,
    UPPER(state_code) AS state_code_clean,
    zip_code,
    county,
    ntee_code,
    subsection,
    affiliation,
    classification,
    ruling,
    foundation,
    deductibility,
    status,
    tax_period,
    assets,
    income,
    revenue,
    accounting_period,
    asset_code,
    income_code,
    filing_requirement_code,
    pf_filing_requirement_code,
    datasource,
    datasource_id,
    last_updated,
    CURRENT_TIMESTAMP AS transformed_at
FROM combined
WHERE name IS NOT NULL  -- Must have a name
  AND ein IS NOT NULL   -- Must have EIN
  AND LENGTH(ein) >= 9  -- Valid EIN format
