{{ config(materialized='table') }}

/*
    Intermediate (MDM): deterministic organization clustering.

    Orgs resolve deterministically, most-specific key first:
      1. EIN             — merges the same nonprofit across NCCS / AI.
      2. jurisdiction_id — each government jurisdiction is canonical & distinct
                           (so Adams county / township / borough don't collapse).
      2b. CKAN org id    — each Data.gov publishing government is canonical &
                           distinct (`gov:<ckan_id>`); detail in the
                           mdm_organization_government satellite, which mints the
                           same key.
      3. name+city+state — separates same-name orgs in different cities (two
                           "First Baptist Church" in a state stay distinct).
      4. org_uid         — singleton fallback when nothing keys it.
*/

select
    *,
    coalesce(
        nullif(ein, ''),
        case when source_system = 'bronze_jurisdictions' then 'jur:' || source_pk end,
        case when source_system = 'bronze_schools_nces' then 'sch:' || source_pk end,
        case when source_system = 'bronze_organizations_gov' then 'gov:' || source_pk end,
        case
            when org_name_norm is not null
                then md5(org_name_norm || '|' || coalesce(city_norm, '') || '|' || coalesce(state_code, ''))
        end,
        org_uid
    ) as master_org_id
from {{ ref('int_organizations__unioned') }}
