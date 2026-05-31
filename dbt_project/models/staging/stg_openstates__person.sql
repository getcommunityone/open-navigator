{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): scraped officials / OpenStates people from
    bronze_persons_scraped, mapped onto the shared person contract that
    int_persons__unioned unions. One row per source row.

    This source uniquely provides explicit given_name / family_name columns, so
    they are carried through directly (other sources leave them null and rely on
    the first/last phonetic keys). External id = openstates_person_id.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, person pipeline).
    Four-CTE template: source → parsed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_persons_scraped') }}
),

parsed as (
    select
        'bronze_persons_scraped'                               as source_system,
        id::text                                               as source_pk,
        'person'                                               as entity_type,

        name                                                   as raw_name,
        {{ normalize_person_name('name') }}                    as name_norm,
        nullif(lower(trim(unaccent(given_name))), '')          as given_name_norm,
        nullif(lower(trim(unaccent(family_name))), '')         as family_name_norm,
        {{ name_phonetic_first('name') }}                      as name_phonetic_first,
        {{ name_phonetic_key('name') }}                        as name_phonetic_last,

        nullif(lower(trim(email)), '')                         as email,
        nullif(regexp_replace(coalesce(phone, ''), '[^0-9]', '', 'g'), '') as phone,
        null::text                                             as ein,
        coalesce(nullif(openstates_person_id, ''), nullif(ocd_id, '')) as external_id,

        null::text                                             as city_norm,  -- mailing_address unparsed
        upper(left(trim(state_code), 2))                       as state_code,
        null::text                                             as zip5
    from source
),

filtered as (
    select * from parsed where name_norm is not null
),

final as (
    select * from filtered
)

select * from final
