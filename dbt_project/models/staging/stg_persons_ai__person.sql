{{ config(materialized='view') }}

/*
    Staging (MDM person conformance): AI-extracted people from
    bronze_persons_from_ai (the RAW source behind the event_person mart — read
    here at bronze, NOT from the mart, to keep the medallion DAG one-directional).

    Lowest-trust person source (LLM-extracted, no strong keys beyond a sometimes-
    resolved person_id/wikidata_qid); rank last in survivorship downstream.
    full_name is the parsed name when the model resolved one, else fall back to
    the verbatim mention in appeared_as.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, person pipeline).
    Four-CTE template: source → parsed → filtered → final.
*/

with

source as (
    -- the AI sometimes lists the same person twice in one event, so
    -- source_event_id_person_id is not unique; collapse to the intended grain
    select distinct on (source_event_id_person_id) *
    from {{ ref('bronze_persons_from_ai') }}
    order by source_event_id_person_id, extracted_at desc
),

parsed as (
    select
        'bronze_persons_from_ai'                               as source_system,
        source_event_id_person_id                              as source_pk,
        'person'                                               as entity_type,

        coalesce(full_name, appeared_as)                       as raw_name,
        {{ normalize_person_name('coalesce(full_name, appeared_as)') }}     as name_norm,
        null::text                                             as given_name_norm,
        null::text                                             as family_name_norm,
        {{ name_phonetic_first('coalesce(full_name, appeared_as)') }}       as name_phonetic_first,
        {{ name_phonetic_key('coalesce(full_name, appeared_as)') }}         as name_phonetic_last,

        null::text                                             as email,
        null::text                                             as phone,
        null::text                                             as ein,
        coalesce(nullif(person_id, ''), nullif(wikidata_qid, '')) as external_id,

        null::text                                             as city_norm,
        null::text                                             as state_code,
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
