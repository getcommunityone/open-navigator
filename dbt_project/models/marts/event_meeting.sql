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
public.event_meeting — the meeting-level parent for the AI-extraction family.

GRAIN: one row per analysis (= one analyzed meeting). This is the PARENT that
the child extraction marts (event_person/event_decision/event_bill/event_place/
event_financial_item/event_topic) reference via their analysis_id -> event_meeting_id.

SOURCE : bronze.bronze_meetings_from_ai   BRIDGE : source_event_id == analysis.id;
         analysis.event_id -> civic_event.legacy_id (enforced FK)
TARGET : public.event_meeting — NON-partitioned (single-column PK so children can
         FK into it). Created by `bootstrap_event_meeting`; APPEND only.

Unlike the partitioned children, event_meeting is a plain table keyed on
event_meeting_id (= the analysis id). Keep the parent DDL in bootstrap_event_meeting
in sync with this SELECT.
*/

with src_raw as (
    select *
    from {{ ref('bronze_meetings_from_ai') }}
    {% if is_incremental() %}
    where extracted_at > (select coalesce(max(extracted_at), '1900-01-01'::timestamp) from {{ this }})
    {% endif %}
),

src as (
    select * from (
        select *, row_number() over (
            partition by source_event_id order by extracted_at desc
        ) as _rn
        from src_raw
    ) d where _rn = 1
),

analysis as (
    select id as analysis_id, event_id as legacy_event_id
    from {{ source('bronze', 'bronze_events_analysis_ai') }}
    where {{ is_publishable_governance_analysis('structured_analysis') }}
),

events as (
    select legacy_id, id as c1_event_id, state as state_code,
           jurisdiction_name, jurisdiction_type, city
    from {{ source('civic_core', 'civic_event') }}
)

select
    s.source_event_id                           as event_meeting_id,
    a.legacy_event_id,
    e.c1_event_id,

    e.state_code,
    {{ state_code_to_name('e.state_code') }}    as state,
    e.jurisdiction_name,
    e.jurisdiction_type,
    e.city,

    s.meeting_id,
    s.body_name,
    s.meeting_date,
    s.event_date,
    s.jurisdiction,
    s.meeting_summary,
    s.agenda_summary,
    s.session_info,

    s.video_id,
    s.source_ai_model,
    s.extracted_at

from src s
inner join analysis a on a.analysis_id = s.source_event_id
left join events   e on e.legacy_id   = a.legacy_event_id
