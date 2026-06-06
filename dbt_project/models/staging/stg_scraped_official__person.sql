{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): scraped municipal council members from
    bronze_officials_scraped (landed by ingestion.municipal.load_council_officials,
    rows from scrapers.municipal.council_roster — e.g. the Boston City Council),
    mapped onto the shared person contract so they join the conformed person pool
    the marts serve (mdm_person) and become resolvable identities — not just
    role-grain rows in contact_official.

    Reads the already-cleaned ref('stg_scraped__official') (trimmed names, UPPER
    state_code, lowercased email) rather than bronze, so this model only adds the
    person-conformance projection: name classification, normalization, phonetics.

    source_system = 'bronze_officials_scraped'; source_pk / external_id = the
    deterministic ocd_membership_id (md5 of jurisdiction|name|district|title), so a
    re-scrape keys to the same person occurrence and stays idempotent through Splink.

    The scraped roster carries no parsed given/family name, so those are null —
    Splink blocks on name_norm + phonetics like the other single-name sources.

    Name-quality gate: classify_name_entity_type routes org-shaped strings out of
    the person match pool; the normalize_person_name-not-null filter drops unusable
    strings — the same gate the other stg_*__person models apply.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, person pipeline).
    Four-CTE template: source -> parsed -> filtered -> final.
*/

with

source as (
    select * from {{ ref('stg_scraped__official') }}
),

parsed as (
    select
        ocd_membership_id,
        {{ classify_name_entity_type('full_name') }}          as entity_type,
        full_name                                             as raw_name,
        {{ normalize_person_name('full_name') }}              as name_norm,
        {{ name_phonetic_first('full_name') }}                as name_phonetic_first,
        {{ name_phonetic_key('full_name') }}                  as name_phonetic_last,
        nullif(lower(trim(email)), '')                        as email,
        nullif(trim(phone), '')                               as phone,
        upper(left(trim(state_code), 2))                      as state_code
    from source
    where {{ normalize_person_name('full_name') }} is not null
      and ocd_membership_id is not null
),

filtered as (
    -- one row per scraped membership (ocd_membership_id is the natural key)
    select distinct on (ocd_membership_id) *
    from parsed
    order by ocd_membership_id, raw_name
),

final as (
    select
        'bronze_officials_scraped'                            as source_system,
        ocd_membership_id                                     as source_pk,
        entity_type,
        raw_name,
        name_norm,
        null::text                                            as given_name_norm,
        null::text                                            as family_name_norm,
        name_phonetic_first,
        name_phonetic_last,
        email,
        phone,
        null::text                                            as ein,
        ocd_membership_id                                     as external_id,
        null::text                                            as city_norm,
        state_code,
        null::text                                            as zip5
    from filtered
)

select * from final
