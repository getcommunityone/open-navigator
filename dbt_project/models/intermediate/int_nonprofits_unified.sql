{{
    config(
        materialized='table',
        tags=['silver', 'nonprofits']
    )
}}

/*
Unified Nonprofits — reproducible builder for the (formerly phantom) consolidated
nonprofit table.

Background
----------
`marts/jurisdiction_state_aggregate.sql` and
`intermediate/int_nonprofits_with_county_fips.sql` used to read
`source('bronze','bronze_organizations_nonprofits')` — a physically materialized
table that had NO reproducible dbt builder (it was loaded once by a legacy
script). This model reproduces that table column-for-column from the shard
sources so the consolidated grain is fully owned by dbt.

Build
-----
IRS Business Master File (1.95M orgs, one row per EIN) is the base; NCCS Core
(one row per EIN) is LEFT JOINed on EIN for geographic enrichment
(census_county_name). EIN is unique in BOTH shards (verified), so the join does
not fan out — grain stays one row per IRS EIN.

Columns are named to match the legacy phantom table EXACTLY so the two consumer
models keep identical semantics (counts / revenue / assets unchanged):
  ein, irs_id, org_name, city, state_code, zip_code, ntee_cd,
  irs_asset_amt, irs_income_amt, irs_revenue_amt, census_county_name.

This is intentionally distinct from `int_nonprofits_combined` (which renames
columns to org_name->name, census_county_name->county, revenue_amt->revenue and
layers on GivingTuesday 990 financials) and from `marts/organizations_nonprofits`
(which additionally joins Census ZCTA/postal sources that are not present in
every environment). Keeping this builder dependency-light means the
nonprofits -> jurisdiction_state_aggregate chain builds from the shards alone.
*/

WITH irs_base AS (
    SELECT
        ein,
        id        AS irs_id,
        name      AS org_name,
        city,
        state_code,
        zip_code,
        ntee_cd,
        asset_amt   AS irs_asset_amt,
        income_amt  AS irs_income_amt,
        revenue_amt AS irs_revenue_amt
    FROM {{ source('bronze', 'bronze_organizations_nonprofits_irs') }}
    WHERE ein IS NOT NULL
),

nccs_enrichment AS (
    SELECT
        ein,
        census_county_name
    FROM {{ source('bronze', 'bronze_organizations_nonprofits_nccs') }}
    WHERE ein IS NOT NULL
)

SELECT
    irs.ein,
    irs.irs_id,
    irs.org_name,
    irs.city,
    irs.state_code,
    irs.zip_code,
    irs.ntee_cd,
    irs.irs_asset_amt,
    irs.irs_income_amt,
    irs.irs_revenue_amt,
    nccs.census_county_name
FROM irs_base irs
LEFT JOIN nccs_enrichment nccs ON irs.ein = nccs.ein
