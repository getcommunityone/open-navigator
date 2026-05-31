{{ config(materialized='view') }}

/*
    Staging (MDM org conformance): government jurisdictions from int_jurisdictions
    (states, counties, municipalities, townships, school districts) onto the org
    contract. org_type='government', org_subtype=jurisdiction_type. These are the
    bulk of real government bodies (the bronze_locations facilities are only
    police/fire/agencies).
*/

with source as (
    select * from {{ ref('int_jurisdictions') }}
)

select
    'bronze_jurisdictions'                         as source_system,
    jurisdiction_id                                as source_pk,
    name                                           as org_name,
    {{ normalize_org_name('name') }}               as org_name_norm,
    'government'                                    as org_type,
    nullif(jurisdiction_type, '')                  as org_subtype,
    null::text                                     as ein,
    null::text                                     as city_norm,  -- the jurisdiction IS the place
    upper(left(trim(state_code), 2))               as state_code,
    {{ zip5('zip') }}                              as zip5,
    latitude                                       as lat,
    longitude                                      as lon,
    null::text                                     as website,
    extract(year from ingestion_date)::int         as as_of_year
from source
where {{ normalize_org_name('name') }} is not null
