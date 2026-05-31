{{ config(materialized='view') }}

/*
    Staging: GivingTuesday 990 Part VII-A officers/directors/key-employees.

    One row per (ein, tax_year, person, title) — person-level compensation from
    Form 990 Part VII, Section A. Reads the bronze table landed by
    ingestion.givingtuesday.load (990Part7AOfficers datamart). Light cleaning
    only; person-level grain is preserved. Four-CTE template.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_organizations_990_officers') }}
),

renamed as (
    select
        nullif(trim(ein), '')          as ein,
        tax_year                       as tax_year,
        nullif(trim(org_name), '')     as org_name,
        nullif(trim(person_name), '')  as person_name,
        nullif(trim(title), '')        as title,
        avg_hours_org                  as avg_hours_org,
        avg_hours_related              as avg_hours_related,
        is_officer                     as is_officer,
        is_director_trustee            as is_director_trustee,
        is_institutional_trustee       as is_institutional_trustee,
        is_key_employee                as is_key_employee,
        is_highest_comp                as is_highest_comp,
        is_former                      as is_former,
        reportable_comp_org            as reportable_comp_org,
        reportable_comp_related        as reportable_comp_related,
        other_comp                     as other_comp,
        -- convenience: total reportable + estimated other comp
        coalesce(reportable_comp_org, 0)
            + coalesce(reportable_comp_related, 0)
            + coalesce(other_comp, 0)  as total_comp,
        nullif(trim(source_url), '')   as source_url
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
