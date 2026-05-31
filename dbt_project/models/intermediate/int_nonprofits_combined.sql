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
        org_name_current AS name,  -- bronze nccs renamed `name` -> `org_name_current` (NCCS refactor)
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
),

-- GivingTuesday 990 datamart: latest filing per EIN (financials)
gt_financials AS (
    SELECT ein, tax_year, total_revenue, total_expenses, total_assets,
           total_liabilities, net_assets, total_contributions,
           program_service_revenue, source_url
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY ein ORDER BY tax_year DESC NULLS LAST) AS rn
        FROM {{ ref('stg_givingtuesday__990_financials') }}
    ) ranked
    WHERE rn = 1
),

-- GivingTuesday 990 datamart: latest mission statement per EIN
gt_missions AS (
    SELECT ein, tax_year, mission
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY ein ORDER BY tax_year DESC NULLS LAST) AS rn
        FROM {{ ref('stg_givingtuesday__990_missions') }}
    ) ranked
    WHERE rn = 1
),

base AS (
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
)

-- Enrich each org with its latest GivingTuesday 990 datamart filing (additive,
-- non-destructive: gt990_* columns sit alongside the IRS/NCCS financials above).
SELECT
    base.*,
    gtf.tax_year                 AS gt990_tax_year,
    gtf.total_revenue            AS gt990_total_revenue,
    gtf.total_expenses           AS gt990_total_expenses,
    gtf.total_assets             AS gt990_total_assets,
    gtf.total_liabilities        AS gt990_total_liabilities,
    gtf.net_assets               AS gt990_net_assets,
    gtf.total_contributions      AS gt990_total_contributions,
    gtf.program_service_revenue  AS gt990_program_service_revenue,
    gtf.source_url               AS gt990_source_url,
    gtm.mission                  AS gt990_mission,
    (gtf.ein IS NOT NULL OR gtm.ein IS NOT NULL) AS has_gt990_data
FROM base
LEFT JOIN gt_financials gtf ON base.ein = gtf.ein
LEFT JOIN gt_missions   gtm ON base.ein = gtm.ein
