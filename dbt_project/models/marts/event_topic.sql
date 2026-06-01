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
public.event_topic — themes/topics the AI extracted from analyzed events.

GRAIN: one row per (analysis, decision) topic record. Carries COFOG + NTEE
classification for primary and secondary themes.

SOURCE : bronze.bronze_topics_from_ai   BRIDGE : source_event_id -> analysis.id -> civic_event.legacy_id
TARGET : public.event_topic (range-partitioned by extracted_at; bootstrap_event_topic; APPEND only).
*/

with src_raw as (
    select *
    from {{ ref('bronze_topics_from_ai') }}
    {% if is_incremental() %}
    where extracted_at > (select coalesce(max(extracted_at), '1900-01-01'::timestamp) from {{ this }})
    {% endif %}
),

src as (
    select * from (
        select *, row_number() over (
            partition by source_event_id_decision_id order by extracted_at desc, headline
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
    from {{ source('civic_core', 'civic_event') }}
)

select
    md5(s.source_event_id_decision_id)          as event_topic_id,
    s.source_event_id_decision_id               as extraction_key,
    s.source_event_id                           as analysis_id,
    a.legacy_event_id,
    e.c1_event_id,

    e.state_code,
    {{ state_code_to_name('e.state_code') }}    as state,
    e.jurisdiction_name,
    e.jurisdiction_type,
    e.city,

    s.decision_id,
    s.primary_theme,
    s.headline,

    s.source_ai_model,
    s.extracted_at

from src s
left join analysis a on a.analysis_id = s.source_event_id
left join events   e on e.legacy_id   = a.legacy_event_id
