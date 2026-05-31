{{ config(materialized='view') }}

/*
    Staging (MDM org conformance): organization parcel owners from
    bronze_addresses.owner_name, onto the shared org contract. Pairs with
    stg_parcels__person (the person owners) and stg_parcels__address (the address
    side, same source rows).

    classify_name_entity_type splits owner_name into person vs organization;
    stg_parcels__person takes the people, this takes the businesses / governments
    ("... LLC", "CITY OF X", "... TRUST"). Routing them into the org pool lets them
    resolve to mdm_organization (clustered by name+city+state, or by EIN/jurisdiction
    if they also appear in a typed source) and link to the parcel address through
    mdm_bridge_org_address. Orgs keep their name order (no surname flip).

    No type/geocode/date signal on parcels: org_type falls back to 'other' (the
    cluster type-vote upgrades it if the org matches a typed source); lat/lon and
    as_of_year are null. Column order mirrors the other stg_*__org models — the
    pool is `union all`, which matches by position.
*/

with source as (
    select * from {{ source('bronze', 'bronze_addresses') }}
),

classified as (
    select
        *,
        {{ classify_name_entity_type('owner_name') }} as entity_type
    from source
)

select
    'bronze_addresses'                                     as source_system,
    id::text                                               as source_pk,
    owner_name                                             as org_name,
    {{ normalize_org_name('owner_name') }}                 as org_name_norm,
    'other'                                                as org_type,
    null::text                                             as org_subtype,
    null::text                                             as ein,
    nullif(lower(trim(unaccent(city))), '')                as city_norm,
    upper(left(trim(coalesce(state_abbr, state_code)), 2)) as state_code,
    {{ zip5('postal_code') }}                              as zip5,
    null::double precision                                 as lat,
    null::double precision                                 as lon,
    null::text                                             as website,
    null::int                                              as as_of_year
from classified
where entity_type = 'organization'
  and {{ normalize_org_name('owner_name') }} is not null
