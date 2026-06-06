{{ config(materialized='table') }}

/*
    Intermediate (MDM): the conformed organization pool — government, church,
    healthcare, nonprofit, business, etc. from every org source on one contract.
    Grain: one row per source org occurrence.

    Org sources wired so far:
      - stg_jurisdictions__org (states/counties/cities/townships/school districts)
      - stg_orgs_ai__org       (bronze_organizations_from_ai; typed, some EIN)
      - stg_locations__org     (bronze_locations; police/fire/church/hospital)
      - stg_nccs__org          (nonprofits, EIN-keyed)
      - stg_irs__org           (IRS BMF nonprofits, EIN-keyed; merges with NCCS by
                                EIN and adds the ~290k IRS-only nonprofits)
      - stg_parcels__org       (bronze_addresses owner_name flagged as org; the
                                business/government parcel owners)
      - stg_data_gov__org      (bronze_organizations_gov; Data.gov/CKAN publishing
                                governments — federal/state/county/city agencies.
                                Keyed `gov:<ckan_id>` in clustered; detail in the
                                mdm_organization_government satellite)

    TODO: contribution committees/businesses.
*/

with unioned as (
    select * from {{ ref('stg_jurisdictions__org') }}
    union all
    select * from {{ ref('stg_schools__org') }}
    union all
    select * from {{ ref('stg_orgs_ai__org') }}
    union all
    select * from {{ ref('stg_locations__org') }}
    union all
    select * from {{ ref('stg_nccs__org') }}
    union all
    select * from {{ ref('stg_irs__org') }}
    union all
    select * from {{ ref('stg_parcels__org') }}
    union all
    select * from {{ ref('stg_data_gov__org') }}
)

select
    md5(source_system || '|' || source_pk)  as org_uid,
    source_system,
    source_pk,
    org_name,
    org_name_norm,
    org_type,
    org_subtype,
    ein,
    city_norm,
    state_code,
    zip5,
    lat,
    lon,
    website,
    as_of_year
from unioned
