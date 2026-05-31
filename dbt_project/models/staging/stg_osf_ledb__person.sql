{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): local-election candidates from
    bronze_persons_osf_ledb (OSF Local Elections Database), mapped onto the shared
    person contract.

    The source has one row per (candidate, contest, year) — 126,599 rows across
    77,853 distinct candidates — so it is collapsed to one row per candidate
    (ledb_candid, always populated). Like OpenStates this source provides explicit
    firstname / lastname, carried through; external_id = ledb_candid.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, person pipeline).
    Four-CTE template: source → parsed → deduped → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_persons_osf_ledb') }}
),

parsed as (
    select
        ledb_candid,
        year,
        full_name                                              as raw_name,
        {{ normalize_person_name('full_name') }}               as name_norm,
        nullif(lower(trim(unaccent(firstname))), '')           as given_name_norm,
        nullif(lower(trim(unaccent(lastname))), '')            as family_name_norm,
        {{ name_phonetic_first('full_name') }}                 as name_phonetic_first,
        {{ name_phonetic_key('full_name') }}                   as name_phonetic_last,
        nullif(lower(trim(unaccent(geo_name))), '')            as city_norm,
        upper(left(trim(state_abb), 2))                        as state_code
    from source
    where {{ normalize_person_name('full_name') }} is not null
      and ledb_candid is not null
),

deduped as (
    -- one row per candidate; keep the most recent contest's record
    select distinct on (ledb_candid) *
    from parsed
    order by ledb_candid, year desc nulls last
),

final as (
    select
        'bronze_persons_osf_ledb'                              as source_system,
        (ledb_candid::bigint)::text                            as source_pk,
        'person'                                               as entity_type,
        raw_name,
        name_norm,
        given_name_norm,
        family_name_norm,
        name_phonetic_first,
        name_phonetic_last,
        null::text                                             as email,
        null::text                                             as phone,
        null::text                                             as ein,
        (ledb_candid::bigint)::text                            as external_id,
        city_norm,
        state_code,
        null::text                                             as zip5
    from deduped
)

select * from final
