{{ config(materialized='view') }}

/*
    Staging (MDM org conformance): individual schools from the NCES CCD school
    directory (bronze_schools_nces, ~102k), onto the org contract.
    org_type='education', org_subtype from the CCD school type. Each school keeps
    its own location address and its district id (leaid) for roll-up.
*/

with source as (
    select * from {{ source('bronze', 'bronze_schools_nces') }}
)

select
    'bronze_schools_nces'                                  as source_system,
    ncessch                                                as source_pk,
    name                                                   as org_name,
    {{ normalize_org_name('name') }}                       as org_name_norm,
    'education'                                             as org_type,
    coalesce(nullif(lower(school_type), ''), 'school')     as org_subtype,
    null::text                                             as ein,
    nullif(lower(trim(unaccent(city))), '')                as city_norm,
    upper(left(trim(coalesce(state_code, location_state)), 2)) as state_code,
    {{ zip5('zip') }}                                      as zip5,
    null::double precision                                 as lat,
    null::double precision                                 as lon,
    nullif(website, '')                                    as website,
    nullif(left(school_year, 4), '')::int                  as as_of_year
from source
where {{ normalize_org_name('name') }} is not null
