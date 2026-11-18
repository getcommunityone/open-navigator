{{ config(materialized='view') }}

/*
    Staging (MDM org conformance): individual schools from the NCES CCD school
    directory (bronze_schools_nces, ~102k), onto the org contract.
    org_type='education', org_subtype from the CCD school type. Each school keeps
    its own location address and its district id (leaid) for roll-up.

    When bronze_schools_nces hasn't been loaded (e.g. a local warehouse), the view is
    empty instead of missing, so int_organizations__unioned still builds (#531).
*/

{%- set src = source('bronze', 'bronze_schools_nces') -%}
{%- set src_exists = execute and adapter.get_relation(
        database=src.database, schema=src.schema, identifier=src.identifier) is not none %}

{%- if src_exists %}
with source as (
    select * from {{ src }}
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
{%- else %}
select
    null::text as source_system, null::text as source_pk, null::text as org_name,
    null::text as org_name_norm, null::text as org_type, null::text as org_subtype,
    null::text as ein, null::text as city_norm, null::text as state_code, null::text as zip5,
    null::double precision as lat, null::double precision as lon, null::text as website,
    null::int as as_of_year
where false
{%- endif %}
