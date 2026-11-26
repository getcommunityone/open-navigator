{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Data center payroll employment (#1019), from the BLS Quarterly Census of Employment and Wages. Grain: one row per
    area (national, state, county) per year, private ownership, NAICS 518210 ("Computing Infrastructure Providers,
    Data Processing, Web Hosting, and Related Services": the industry BLS counts data center employment under, and
    broader than data centers alone). Counts are employers' payroll filings, annual averages.

    A withheld figure is NULL with disclosed = false, never 0. Nothing is estimated or filled in.
*/

with s as (
    select * from {{ ref('stg_bls__qcew_industry') }}
    where own_code = '5'
      and industry_code = '518210'
      and size_code = '0'
      and area_level in ('national', 'state', 'county')
)

select
    md5(area_fips || '|' || year::text)::text                         as data_center_employment_id,
    area_fips,
    area_level,
    case when state_fips is not null then {{ state_fips_to_code('state_fips') }} end::text  as state_code,
    case when state_fips is not null then {{ state_code_to_name(state_fips_to_code('state_fips')) }} end::text as state,
    case when area_level = 'county' then area_fips end::text            as county_fips,
    year,
    establishments,
    employment,
    total_annual_wages,
    avg_annual_pay,
    employment_change_pct,
    (not suppressed)                                                    as disclosed,
    industry_code,
    source_url
from s
