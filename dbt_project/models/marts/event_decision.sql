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
public.event_decision — decisions/actions the AI extracted from analyzed events.

GRAIN: one row per (analysis, decision). Scalar fields are typed columns; the
reference graph and rich narrative blocks stay JSONB (place_refs,
legislation_refs, financial_item_refs, vote_tally, human_element,
competing_views, smart_brevity, diagram_*).

SOURCE : bronze.bronze_decisions_from_ai (structured_analysis->'decisions')
BRIDGE : bronze_decisions_from_ai.source_event_id = bronze_events_analysis_ai.id
         bronze_events_analysis_ai.event_id        = civic_event.legacy_id   (enforced FK)
TARGET : public.event_decision — native range-partitioned by extracted_at (monthly),
         created by the `bootstrap_event_decision` run-operation. APPEND only.
*/

with decisions_raw as (
    select *
    from {{ ref('bronze_decisions_from_ai') }}
    {% if is_incremental() %}
    where extracted_at > (
        select coalesce(max(extracted_at), '1900-01-01'::timestamp) from {{ this }}
    )
    {% endif %}
),

-- source_event_id_decision_id is not strictly unique in the source; collapse to
-- the intended grain (one row per analysis+decision) before promoting.
decisions as (
    select *
    from (
        select
            *,
            row_number() over (
                partition by source_event_id_decision_id
                order by extracted_at desc, headline
            ) as _rn
        from decisions_raw
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

-- Parent guard: the analysis_id FK targets event_meeting(event_meeting_id). A
-- handful of analysis runs land child extractions in bronze without a matching
-- meeting-level row in bronze_meetings_from_ai (analysis-cache -> bronze promotion
-- gap). Inner-join to the parent so we never emit a child whose parent is absent,
-- which both satisfies the enforced FK and pins build order after event_meeting.
meeting_keys as (
    select event_meeting_id from {{ ref('event_meeting') }}
)

select
    -- keys
    md5(dd.source_event_id_decision_id)         as event_decision_id,
    dd.source_event_id_decision_id              as extraction_key,
    dd.source_event_id                          as analysis_id,
    a.legacy_event_id,
    e.c1_event_id,

    -- geography
    e.state_code,
    {{ state_code_to_name('e.state_code') }}    as state,
    e.jurisdiction_name,
    e.jurisdiction_type,
    e.city,

    -- decision identity & reference graph
    dd.decision_id,
    dd.subject_id,
    dd.primary_place_id,
    dd.place_refs,
    dd.legislation_refs,
    dd.financial_item_refs,

    -- headline narrative
    dd.headline,
    dd.decision_statement,
    dd.primary_theme,
    dd.outcome,
    dd.vote_tally,

    -- rich narrative blocks
    dd.human_element,
    dd.competing_views,
    dd.smart_brevity,

    -- rendered diagrams
    dd.diagram_timeline,
    dd.diagram_timeline_lines,
    dd.diagram_mindmap,
    dd.diagram_mindmap_lines,

    -- extraction provenance
    dd.source_ai_model,
    dd.extracted_at,

    -- Persisted full-text-search vector (PLAIN tsvector column, backed by the GIN
    -- index ix_event_decision_search_tsv from bootstrap_event_decision). Computed
    -- here in the SELECT so dbt's append insert (whose column list is derived from
    -- the target table) gets a matching value — a STORED generated column can't be
    -- used because that same append insert would try to write to it. Must stay in
    -- sync with the to_tsvector(...) expression in bootstrap_event_decision's
    -- back-fill UPDATE.
    to_tsvector('english',
        coalesce(dd.headline, '') || ' ' ||
        coalesce(dd.decision_statement, '') || ' ' ||
        coalesce(dd.primary_theme, ''))          as search_tsv

from decisions dd
join meeting_keys mk on mk.event_meeting_id = dd.source_event_id
left join analysis a on a.analysis_id = dd.source_event_id
left join events   e on e.legacy_id   = a.legacy_event_id
