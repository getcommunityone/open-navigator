{{ config(materialized='view') }}

/*
    Staging: GivingTuesday 990 Schedule J Part 2 detailed compensation.

    One row per (ein, tax_year, person, title) for individuals whose compensation
    is detailed on Schedule J (a subset of Part VII-A — typically the highest-paid).
    Reads the bronze table landed by ingestion.givingtuesday.load
    (ScheduleJPart2Officers datamart). Light cleaning only. Four-CTE template.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_organizations_990_schedule_j') }}
),

renamed as (
    select
        nullif(trim(ein), '')              as ein,
        tax_year                           as tax_year,
        nullif(trim(org_name), '')         as org_name,
        nullif(trim(person_name), '')      as person_name,
        nullif(trim(title), '')            as title,
        base_comp_org                      as base_comp_org,
        base_comp_related                  as base_comp_related,
        bonus_org                          as bonus_org,
        bonus_related                      as bonus_related,
        other_comp_org                     as other_comp_org,
        other_comp_related                 as other_comp_related,
        deferred_comp_org                  as deferred_comp_org,
        deferred_comp_related              as deferred_comp_related,
        nontaxable_benefits_org            as nontaxable_benefits_org,
        nontaxable_benefits_related        as nontaxable_benefits_related,
        total_comp_org                     as total_comp_org,
        total_comp_related                 as total_comp_related,
        prior_reported_org                 as prior_reported_org,
        prior_reported_related             as prior_reported_related,
        nullif(trim(source_url), '')       as source_url
    from source
),

filtered as (
    select *
    from renamed
    where ein is not null
      and length(ein) >= 9
      and person_name is not null
),

final as (
    select * from filtered
)

select * from final
