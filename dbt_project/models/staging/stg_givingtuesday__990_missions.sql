{{ config(materialized='view') }}

/*
    Staging: GivingTuesday 990 datamart mission statements (1 row per (ein, tax_year)).

    Reads the bronze table landed by ingestion.givingtuesday.load (990Part1Missions
    datamart). Light cleaning only — the "latest filing per EIN" collapse happens
    downstream in int_nonprofits_combined. Four-CTE template.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_organizations_990_missions') }}
),

renamed as (
    select
        nullif(trim(ein), '')          as ein,
        tax_year                       as tax_year,
        nullif(trim(name), '')         as name,
        nullif(trim(mission), '')      as mission,
        nullif(trim(source_url), '')   as source_url
    from source
),

filtered as (
    select *
    from renamed
    where ein is not null
      and length(ein) >= 9
      and mission is not null
),

final as (
    select * from filtered
)

select * from final
