{{
  config(
    materialized='incremental',
    incremental_strategy='append',
    full_refresh=false,
    on_schema_change='ignore',
    tags=['marts', 'event-extraction', 'ai']
  )
}}

/*
public.event_person — people the AI extracted from analyzed meeting events.

GRAIN: one row per (analysis, person) — a *mention/appearance* of a person in
one event, NOT a canonical de-duplicated human. Resolve to the canonical
`civic_person` later via person_id; resolve to the canonical event via c1_event_id.

SOURCE : bronze.bronze_persons_from_ai (LLM extraction of structured_analysis->'people')
BRIDGE : bronze_persons_from_ai.source_event_id = bronze_events_analysis_ai.id
         bronze_events_analysis_ai.event_id     = civic_event.legacy_id   (enforced FK)
TARGET : public.event_person — native range-partitioned by extracted_at (monthly).

The partitioned parent is created by the `bootstrap_event_person` run-operation
(see macros/event_extractions.sql). This model only ever APPENDS into it.
*/

with persons_raw as (
    select *
    from {{ ref('bronze_persons_from_ai') }}
    {% if is_incremental() %}
    where extracted_at > (
        select coalesce(max(extracted_at), '1900-01-01'::timestamp) from {{ this }}
    )
    {% endif %}
),

-- The AI sometimes lists the same person_id twice in one event, so
-- source_event_id_person_id is not unique in the source. Collapse to the
-- intended grain (one row per analysis+person) before promoting.
persons as (
    select *
    from (
        select
            *,
            row_number() over (
                partition by source_event_id_person_id
                order by extracted_at desc, full_name
            ) as _rn
        from persons_raw
    ) d
    where _rn = 1
),

analysis as (
    select
        id        as analysis_id,
        event_id  as legacy_event_id
    from {{ source('bronze', 'bronze_events_analysis_ai') }}
),

events as (
    select
        legacy_id,
        id                 as c1_event_id,
        state              as state_code,
        jurisdiction_name,
        jurisdiction_type,
        city
    from {{ source('civic_core', 'civic_event') }}
),

-- Parent guard: only emit child rows whose analysis_id has a matching
-- event_meeting parent (satisfies the enforced FK; analysis-cache -> bronze
-- promotion can leave orphan child extractions without a meeting-level row).
meeting_keys as (
    select event_meeting_id from {{ ref('event_meeting') }}
)

select
    -- keys
    md5(p.source_event_id_person_id)            as event_person_id, -- surrogate PK
    p.source_event_id_person_id                 as extraction_key,  -- stable dedup key
    p.source_event_id                           as analysis_id,
    a.legacy_event_id,
    e.c1_event_id,                                                  -- resolved canonical event (nullable)

    -- geography (for partition-adjacent filtering)
    e.state_code,
    {{ state_code_to_name('e.state_code') }}    as state,
    e.jurisdiction_name,
    e.jurisdiction_type,
    e.city,

    -- person attributes
    p.person_id,
    p.full_name,
    -- best available human-readable name: the AI's parsed full_name when it
    -- could resolve one, else the verbatim mention (e.g. "Commissioner Gruber").
    -- appeared_as is always populated, so this is never null.
    coalesce(p.full_name, p.appeared_as)        as display_name,
    p.role,
    p.is_lobbyist,
    p.appeared_as,

    -- extraction provenance
    p.source_ai_model,
    p.extracted_at

from persons p
join meeting_keys mk on mk.event_meeting_id = p.source_event_id
left join analysis a on a.analysis_id    = p.source_event_id
left join events   e on e.legacy_id      = a.legacy_event_id
