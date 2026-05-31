{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): parcel owners from bronze_addresses.owner_name,
    mapped onto the shared person contract. Pairs with stg_parcels__address (same
    source rows, the address side).

    owner_name is "SURNAME FIRSTNAME" with NO comma. normalize_person_name only
    flips comma-delimited "Last, First", so here we flip person names explicitly by
    moving the first token (surname) to the end -> "GIVEN SURNAME". This fixes the
    display name (full_name), the first/last phonetic keys, AND makes parcels
    consistent with the comma-flipped contributor names for cross-source matching.
    Organizations (City Of X, ... LLC) keep their order. Surname/given are also
    split out from the original (surname = first token).

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2; Watch-outs: name order).
    Template: source → classified → flipped → parsed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_addresses') }}
),

classified as (
    select
        *,
        {{ classify_name_entity_type('owner_name') }} as entity_type
    from source
),

flipped as (
    select
        *,
        -- move first token (surname) to the end, persons only
        case
            when entity_type = 'person'
                then regexp_replace(btrim(owner_name), '^([^ ]+) +(.+)$', '\2 \1')
            else owner_name
        end                                                            as owner_name_display,
        case when entity_type = 'person'
             then nullif(lower(unaccent(split_part(btrim(owner_name), ' ', 1))), '')
        end                                                            as family_norm,
        case when entity_type = 'person'
             then nullif(lower(unaccent(regexp_replace(btrim(owner_name), '^[^ ]+ +', ''))), '')
        end                                                            as given_norm
    from classified
),

parsed as (
    select
        'bronze_addresses'                                     as source_system,
        id::text                                               as source_pk,
        entity_type,

        owner_name                                             as raw_name,  -- original (surname-first)
        {{ normalize_person_name('owner_name_display') }}      as name_norm,
        given_norm                                             as given_name_norm,
        family_norm                                            as family_name_norm,
        {{ name_phonetic_first('owner_name_display') }}        as name_phonetic_first,
        {{ name_phonetic_key('owner_name_display') }}          as name_phonetic_last,

        null::text                                             as email,
        null::text                                             as phone,
        null::text                                             as ein,
        null::text                                             as external_id,

        nullif(lower(trim(unaccent(city))), '')                as city_norm,
        upper(left(trim(coalesce(state_abbr, state_code)), 2)) as state_code,
        {{ zip5('postal_code') }}                              as zip5
    from flipped
),

filtered as (
    select * from parsed where name_norm is not null
),

final as (
    select * from filtered
)

select * from final
