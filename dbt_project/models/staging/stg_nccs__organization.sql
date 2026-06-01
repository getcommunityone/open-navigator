{{ config(materialized='view') }}

/*
    Staging: NCCS Unified BMF organization-years (1 row per (ein, org_year_last)).

    Reads the raw history table landed by ingestion.nccs.bulk. Light cleaning +
    type stabilization only — the "current per EIN" collapse happens downstream
    in int_nccs__current_orgs (previously done in Python; moved to dbt per
    dbt_project/CONVENTIONS.md). Four-CTE template: source → renamed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_organizations_nonprofits_nccs_history') }}
),

renamed as (
    select
        ein                                                  as ein,
        nullif(trim(ntee_irs), '')                           as ntee_irs,
        nullif(trim(ntee_nccs), '')                          as ntee_nccs,
        nullif(trim(nccs_level_1), '')                       as nccs_level_1,
        nullif(trim(org_name_current), '')                   as org_name_current,
        nullif(trim(f990_org_addr_city), '')                 as city,
        upper(nullif(trim(f990_org_addr_state), ''))         as state_code,
        -- calendar years -> integer at the staging boundary (project convention);
        -- guarded so a future non-numeric value yields NULL instead of erroring.
        case when trim(org_year_first) ~ '^[0-9]{4}$' then trim(org_year_first)::int end as org_year_first,
        case when trim(org_year_last)  ~ '^[0-9]{4}$' then trim(org_year_last)::int  end as org_year_last,
        latitude                                             as latitude,
        longitude                                            as longitude,
        f990_total_revenue_recent                            as total_revenue_recent,
        f990_total_assets_recent                             as total_assets_recent,
        loaded_at                                            as source_ingested_at
    from source
),

filtered as (
    -- Business rule: drop rows with no EIN (the natural key component).
    select *
    from renamed
    where ein is not null
      and length(ein) > 0
),

final as (
    select
        ein,
        ntee_irs,
        ntee_nccs,
        nccs_level_1,
        org_name_current,
        city,
        state_code,
        org_year_first,
        org_year_last,
        latitude,
        longitude,
        total_revenue_recent,
        total_assets_recent,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
