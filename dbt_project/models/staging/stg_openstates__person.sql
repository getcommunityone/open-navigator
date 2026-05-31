{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): scraped officials / OpenStates people.

    Reads stg_bronze_persons_scraped (not the raw bronze table) and keeps only
    is_usable_person — reusing the existing name-quality classification that drops
    UI chrome, titles, dates, "hours of operation", org/place names, non-Latin
    script, etc. This is the same gate int_persons_scraped applies; without it the
    pool fills with ~12k non-name strings per the audit.

    Trade-off: this cleaned staging exposes name_clean + ocd_id but not the raw
    given_name/family_name/openstates_person_id, so given/family are left null
    (the first/last phonetic keys carry name matching) and external_id = ocd_id.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, person pipeline).
    Four-CTE template: source → parsed → filtered → final.
*/

with

source as (
    select * from {{ ref('stg_bronze_persons_scraped') }}
),

parsed as (
    select
        'bronze_persons_scraped'                               as source_system,
        bronze_person_id::text                                 as source_pk,
        'person'                                               as entity_type,

        name_clean                                             as raw_name,
        {{ normalize_person_name('name_clean') }}              as name_norm,
        null::text                                             as given_name_norm,
        null::text                                             as family_name_norm,
        {{ name_phonetic_first('name_clean') }}                as name_phonetic_first,
        {{ name_phonetic_key('name_clean') }}                  as name_phonetic_last,

        nullif(lower(trim(email)), '')                         as email,
        nullif(regexp_replace(coalesce(phone, ''), '[^0-9]', '', 'g'), '') as phone,
        null::text                                             as ein,
        nullif(ocd_id, '')                                     as external_id,

        null::text                                             as city_norm,  -- mailing_address unparsed
        upper(left(trim(state_code), 2))                       as state_code,
        null::text                                             as zip5
    from source
    where is_usable_person
),

filtered as (
    select * from parsed where name_norm is not null
),

final as (
    select * from filtered
)

select * from final
