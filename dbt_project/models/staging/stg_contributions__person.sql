{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): campaign contributors from
    bronze_campaigns_contributions, mapped onto the shared person contract.

    bronze_campaigns_contributions has ~24.5M transaction rows, but a donor who
    gave 500 times is ONE entity for resolution — so this collapses to one row
    per distinct contributor identity (name_norm + city + state + zip) instead of
    one per contribution. source_pk is a deterministic hash of that identity; the
    transaction-level link back lives in a separate xref, not the person pool.

    contributor_name is "LAST, FIRST" for individuals (normalize_person_name
    flips it) but also frequently a PAC / committee / business — classified into
    entity_type so org rows stay in a separate match pool from people.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, person pipeline).
    Four-CTE template: source → parsed → deduped → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_campaigns_contributions') }}
),

parsed as (
    select
        {{ classify_name_entity_type('contributor_name') }}    as entity_type,
        contributor_name                                       as raw_name,
        {{ normalize_person_name('contributor_name') }}        as name_norm,
        {{ name_phonetic_first('contributor_name') }}          as name_phonetic_first,
        {{ name_phonetic_key('contributor_name') }}            as name_phonetic_last,
        nullif(lower(trim(unaccent(contributor_city))), '')    as city_norm,
        upper(left(trim(contributor_state), 2))                as state_code,
        {{ zip5('contributor_zip') }}                          as zip5
    from source
    where {{ normalize_person_name('contributor_name') }} is not null
),

deduped as (
    -- one row per distinct contributor identity
    select distinct on (
        name_norm,
        coalesce(city_norm, ''),
        coalesce(state_code, ''),
        coalesce(zip5, '')
    ) *
    from parsed
    order by
        name_norm,
        coalesce(city_norm, ''),
        coalesce(state_code, ''),
        coalesce(zip5, ''),
        raw_name
),

final as (
    select
        'bronze_campaigns_contributions'                       as source_system,
        md5(
            name_norm || '|' || coalesce(city_norm, '') || '|'
            || coalesce(state_code, '') || '|' || coalesce(zip5, '')
        )                                                      as source_pk,
        entity_type,
        raw_name,
        name_norm,
        null::text                                             as given_name_norm,
        null::text                                             as family_name_norm,
        name_phonetic_first,
        name_phonetic_last,
        null::text                                             as email,
        null::text                                             as phone,
        null::text                                             as ein,
        null::text                                             as external_id,
        city_norm,
        state_code,
        zip5
    from deduped
)

select * from final
