{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): OpenStates legislators from
    bronze_jurisdiction_openstates (2,463 people, AL validation pull), mapped onto
    the shared person contract so they join the conformed person pool the marts
    serve (mdm_person) and become a real FK target for bill sponsorships.

    This source provides explicit given_name / family_name (carried through) and a
    stable OCD person id. Unlike the legacy stg_openstates__person (which scrapes
    bronze_persons_scraped and mistakenly puts a division id in external_id), here
    external_id IS the OCD person id (ocd-person/..) — the same id that
    sponsorships[].person_id carries on the bills source — so downstream bill ->
    person resolution keys on it and FKs back to mdm_person.person_uid via
    person_uid = md5('bronze_jurisdiction_openstates|' || openstates_person_id).

    Name-quality gate: classify_name_entity_type routes org-shaped names out of the
    person match pool, and the normalize_person_name-not-null filter drops UI chrome
    / unusable strings — the same gate the other stg_*__person models apply.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, person pipeline).
    Four-CTE template: source -> parsed -> filtered -> final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_jurisdiction_openstates') }}
),

parsed as (
    select
        openstates_person_id,
        {{ classify_name_entity_type('name') }}                as entity_type,
        name                                                   as raw_name,
        {{ normalize_person_name('name') }}                    as name_norm,
        nullif(lower(trim(unaccent(given_name))), '')          as given_name_norm,
        nullif(lower(trim(unaccent(family_name))), '')         as family_name_norm,
        {{ name_phonetic_first('name') }}                      as name_phonetic_first,
        {{ name_phonetic_key('name') }}                        as name_phonetic_last,
        nullif(lower(trim(email)), '')                         as email,
        upper(left(trim(state_code), 2))                       as state_code
    from source
    where {{ normalize_person_name('name') }} is not null
      and openstates_person_id is not null
),

filtered as (
    -- one row per legislator (openstates_person_id is the natural key)
    select distinct on (openstates_person_id) *
    from parsed
    order by openstates_person_id, raw_name
),

final as (
    select
        'bronze_jurisdiction_openstates'                       as source_system,
        openstates_person_id                                   as source_pk,
        entity_type,
        raw_name,
        name_norm,
        given_name_norm,
        family_name_norm,
        name_phonetic_first,
        name_phonetic_last,
        email,
        null::text                                             as phone,
        null::text                                             as ein,
        openstates_person_id                                   as external_id,
        null::text                                             as city_norm,
        state_code,
        null::text                                             as zip5
    from filtered
)

select * from final
