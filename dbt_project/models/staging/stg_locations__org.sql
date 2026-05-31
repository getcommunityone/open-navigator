{{ config(materialized='view') }}

/*
    Staging (MDM org conformance): government / church / healthcare / etc.
    facilities from bronze_locations, onto the shared org contract. The HIFLD
    organization_type (place_of_worship, local_police_department, hospital, ...)
    drives the canonical org_type; carries address + geocode.
*/

with source as (
    select * from {{ source('bronze', 'bronze_locations') }}
)

select
    'bronze_locations'                                     as source_system,
    concat_ws(':', source_dataset, source_id::text)         as source_pk,
    name                                                   as org_name,
    {{ normalize_org_name('name') }}                       as org_name_norm,
    {{ canonical_org_type('organization_type') }}          as org_type,
    nullif(organization_type, '')                          as org_subtype,
    null::text                                             as ein,
    nullif(lower(trim(unaccent(city))), '')                as city_norm,
    upper(left(trim(state), 2))                            as state_code,
    {{ zip5('zip') }}                                      as zip5,
    latitude                                               as lat,
    longitude                                              as lon,
    nullif(website, '')                                    as website,
    extract(year from coalesce(updated_at, created_at))::int as as_of_year
from source
where {{ normalize_org_name('name') }} is not null
