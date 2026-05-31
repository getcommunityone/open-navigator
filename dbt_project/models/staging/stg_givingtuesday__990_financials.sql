{{ config(materialized='view') }}

/*
    Staging: GivingTuesday 990 datamart financials (1 row per (ein, tax_year)).

    Reads the bronze table landed by ingestion.givingtuesday.load (990CN120Fields
    datamart). Light cleaning + type stabilization only — the "latest filing per
    EIN" collapse happens downstream in int_nonprofits_combined, matching the NCCS
    pattern. Four-CTE template: source → renamed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_organizations_990_financials') }}
),

renamed as (
    select
        nullif(trim(ein), '')                  as ein,
        tax_year                               as tax_year,
        nullif(trim(name), '')                 as name,
        upper(nullif(trim(state_code), ''))    as state_code,
        total_revenue                          as total_revenue,
        total_expenses                         as total_expenses,
        total_assets                           as total_assets,
        total_liabilities                      as total_liabilities,
        net_assets                             as net_assets,
        total_contributions                    as total_contributions,
        program_service_revenue                as program_service_revenue,
        nullif(trim(source_url), '')           as source_url
    from source
),

filtered as (
    select *
    from renamed
    where ein is not null
      and length(ein) >= 9
),

final as (
    select * from filtered
)

select * from final
