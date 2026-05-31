{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): parcel owners from bronze_addresses.owner_name,
    mapped onto the shared person contract. Pairs with stg_parcels__address (same
    source rows, the address side).

    owner_name is "SURNAME FIRSTNAME" with NO comma (so normalize_person_name does
    not flip it — the first/last phonetic keys handle order downstream) and often
    a business or estate/trust, so entity_type is classified. Situs city/state/zip
    are carried as blocking keys.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, person pipeline;
    Watch-outs: name token order).
    Four-CTE template: source → parsed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_addresses') }}
),

parsed as (
    select
        'bronze_addresses'                                     as source_system,
        id::text                                               as source_pk,
        {{ classify_name_entity_type('owner_name') }}          as entity_type,

        owner_name                                             as raw_name,
        {{ normalize_person_name('owner_name') }}              as name_norm,
        null::text                                             as given_name_norm,
        null::text                                             as family_name_norm,
        {{ name_phonetic_first('owner_name') }}                as name_phonetic_first,
        {{ name_phonetic_key('owner_name') }}                  as name_phonetic_last,

        null::text                                             as email,
        null::text                                             as phone,
        null::text                                             as ein,
        null::text                                             as external_id,

        nullif(lower(trim(unaccent(city))), '')                as city_norm,
        upper(left(trim(coalesce(state_abbr, state_code)), 2)) as state_code,
        {{ zip5('postal_code') }}                              as zip5
    from source
),

filtered as (
    select * from parsed where name_norm is not null
),

final as (
    select * from filtered
)

select * from final
