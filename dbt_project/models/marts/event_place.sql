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
public.event_place — places the AI extracted/geocoded from analyzed events.

GRAIN: one row per (analysis, place). The event's jurisdiction lives in the
standard state_code/state/jurisdiction_* block (from c1_event); the place's OWN
resolved location is place_city / place_state_code / lat-long.

SOURCE : bronze.bronze_places_from_ai      BRIDGE : source_event_id -> analysis.id -> c1_event.legacy_id
TARGET : public.event_place (range-partitioned by extracted_at; bootstrap_event_place; APPEND only).
*/

with src_raw as (
    select *
    from {{ ref('bronze_places_from_ai') }}
    {% if is_incremental() %}
    where extracted_at > (select coalesce(max(extracted_at), '1900-01-01'::timestamp) from {{ this }})
    {% endif %}
),

src as (
    select * from (
        select *, row_number() over (
            partition by source_event_id_place_id order by extracted_at desc, mention_count desc nulls last
        ) as _rn
        from src_raw
    ) d where _rn = 1
),

analysis as (
    select id as analysis_id, event_id as legacy_event_id
    from {{ source('bronze', 'bronze_events_analysis_ai') }}
),

events as (
    select legacy_id, id as c1_event_id, state as state_code,
           jurisdiction_name, jurisdiction_type, city
    from {{ source('civic_core', 'c1_event') }}
)

select
    md5(s.source_event_id_place_id)             as event_place_id,
    s.source_event_id_place_id                  as extraction_key,
    s.source_event_id                           as analysis_id,
    a.legacy_event_id,
    e.c1_event_id,

    e.state_code,
    {{ state_code_to_name('e.state_code') }}    as state,
    e.jurisdiction_name,
    e.jurisdiction_type,
    e.city,

    s.place_id,
    s.raw_text,
    s.normalized_address,
    s.place_type,
    s.street_address,
    s.city                                      as place_city,
    s.state_code                                as place_state_code,
    s.geocode_query,
    s.latitude,
    s.longitude,
    s.geocode_status,
    s.linked_decision_ids,
    s.linked_item_ids,
    s.mention_count,

    s.source_ai_model,
    s.extracted_at

from src s
left join analysis a on a.analysis_id = s.source_event_id
left join events   e on e.legacy_id   = a.legacy_event_id
