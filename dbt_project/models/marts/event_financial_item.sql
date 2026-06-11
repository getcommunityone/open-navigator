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
public.event_financial_item — dollar amounts/items the AI extracted from events.

GRAIN: one row per (analysis, financial_item).

SOURCE : bronze.bronze_financial_items_from_ai   BRIDGE : source_event_id -> analysis.id -> civic_event.legacy_id
TARGET : public.event_financial_item (range-partitioned by extracted_at; bootstrap_event_financial_item; APPEND only).
*/

with src_raw as (
    select *
    from {{ ref('bronze_financial_items_from_ai') }}
    {% if is_incremental() %}
    where extracted_at > (select coalesce(max(extracted_at), '1900-01-01'::timestamp) from {{ this }})
    {% endif %}
),

src as (
    select * from (
        select *, row_number() over (
            partition by source_event_id_financial_item_id order by extracted_at desc, amount desc nulls last
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
),

-- Parent guard: only emit child rows whose analysis_id has a matching
-- event_meeting parent (satisfies the enforced FK; analysis-cache -> bronze
-- promotion can leave orphan child extractions without a meeting-level row).
meeting_keys as (
    select event_meeting_id from {{ ref('event_meeting') }}
)

select
    md5(s.source_event_id_financial_item_id)    as event_financial_item_id,
    s.source_event_id_financial_item_id         as extraction_key,
    s.source_event_id                           as analysis_id,
    a.legacy_event_id,
    e.c1_event_id,

    e.state_code,
    {{ state_code_to_name('e.state_code') }}    as state,
    e.jurisdiction_name,
    e.jurisdiction_type,
    e.city,

    s.financial_item_id,
    s.event_description,
    s.amount,
    s.amount_type,
    s.currency,
    s.funding_source,

    s.source_ai_model,
    s.extracted_at,

    -- Date the dollars are dated to (contract award / payment / budget-effective).
    -- Null until the analysis prompt populates it (policy_analysis_part_1.md).
    s.item_date,
    s.item_date_type

from src s
join meeting_keys mk on mk.event_meeting_id = s.source_event_id
left join analysis a on a.analysis_id = s.source_event_id
left join events   e on e.legacy_id   = a.legacy_event_id
