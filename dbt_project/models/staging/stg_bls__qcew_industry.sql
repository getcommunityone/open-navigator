{{ config(materialized='view') }}

/*
    Staging (#1019): BLS QCEW annual averages, typed. Year cast to integer (CLAUDE.md, calendar years). A withheld
    cell (disclosure_code 'N') keeps its row but its figures are NULL: BLS publishes 0 there as a placeholder, and
    0 would read as "no jobs". Area level from the area code: national (US000), state (SS000), county (5-digit
    county FIPS); MSAs and other aggregates are tagged 'other'.
*/

with src as (
    select * from {{ ref('bronze_bls_qcew_industry') }}
    where qtr = 'A'
),

typed as (
    select
        area_fips::text                                                         as area_fips,
        own_code::text                                                          as own_code,
        industry_code::text                                                     as industry_code,
        size_code::text                                                         as size_code,
        year::int                                                               as year,
        coalesce(disclosure_code = 'N', false)                                  as suppressed,
        case
            when area_fips = 'US000' then 'national'
            when area_fips ~ '^[0-9]{2}000$' then 'state'
            when area_fips ~ '^[0-9]{5}$' and right(area_fips, 3) not in ('000', '999') then 'county'
            else 'other'
        end                                                                     as area_level,
        case when disclosure_code = 'N' then null else nullif(annual_avg_estabs, '')::int end      as establishments,
        case when disclosure_code = 'N' then null else nullif(annual_avg_emplvl, '')::int end      as employment,
        case when disclosure_code = 'N' then null else nullif(total_annual_wages, '')::bigint end  as total_annual_wages,
        case when disclosure_code = 'N' then null else nullif(avg_annual_pay, '')::int end         as avg_annual_pay,
        case when disclosure_code = 'N' then null
             else nullif(oty_annual_avg_emplvl_pct_chg, '')::numeric end                           as employment_change_pct,
        source_url::text                                                        as source_url
    from src
)

select
    *,
    case when area_level in ('state', 'county') then left(area_fips, 2) end    as state_fips
from typed
