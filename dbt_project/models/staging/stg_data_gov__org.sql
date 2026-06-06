{{ config(materialized='view') }}

/*
    Staging (MDM org conformance): Data.gov (CKAN) publishing organizations onto
    the shared organization contract, so they fold into mdm_organization as a
    government subtype (satellite: mdm_organization_government).

    Reads the cleaned Data.gov staging model (stg_data_gov__organizations), which
    already extracts government_level from the CKAN extras and disambiguates the
    CKAN lifecycle/type columns. This adapter only re-shapes those rows onto the
    14-column union contract shared by every stg_*__org model (matched BY POSITION
    in int_organizations__unioned -> `union all`).

    Keying: gov orgs have NO EIN. int_organizations__clustered mints a stable
    deterministic master_org_id of `gov:<ckan_id>` for source_system =
    'bronze_organizations_gov' (mirrors the `jur:`/`sch:` namespaced schemes for
    the other government/school populations). The mdm_organization_government
    satellite mints the SAME value to attach 1:1.

    org_type is forced to 'government' (these are, by definition, the government
    bodies that publish on Data.gov) so the cluster type-vote in mdm_organization
    resolves them to the government discriminator. No location/geocode signal on
    CKAN orgs: city/state/zip/lat/lon are null. as_of_year is the CKAN creation
    calendar year (source_created_at is a real timestamp; only the bare year is
    carried into the union contract's integer as_of_year column).
*/

with source as (
    select * from {{ ref('stg_data_gov__organizations') }}
)

select
    'bronze_organizations_gov'                     as source_system,
    id::text                                       as source_pk,
    title                                          as org_name,
    {{ normalize_org_name('title') }}             as org_name_norm,
    'government'                                   as org_type,
    nullif(government_level, '')                   as org_subtype,
    null::text                                     as ein,
    null::text                                     as city_norm,
    null::text                                     as state_code,
    null::text                                     as zip5,
    null::double precision                        as lat,
    null::double precision                        as lon,
    website_url                                    as website,
    extract(year from source_created_at)::int     as as_of_year
from source
where {{ normalize_org_name('title') }} is not null
