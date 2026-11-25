{{
  config(
    materialized='table',
    schema='bronze',
    tags=['bronze', 'ai-extraction']
  )
}}

/*
Extract uncontested (consent) items from the Gemini AI analysis JSONB (#932).

Source: bronze.bronze_events_analysis_ai.structured_analysis -> 'uncontested_items'
Target: bronze.bronze_uncontested_items_from_ai

GRAIN: one row per (analysis, uncontested item). The analysis prompts split a meeting's
actions in two: contested decisions go to decisions[] (-> event_decision), and items passed
without debate (minutes, consent agenda, routine approvals) go to uncontested_items[]. Each
element carries item_id (U001, ...), headline, outcome, vote ("voice vote", "5-0", ...),
primary_theme and the NTEE cause. Until this model, nothing in the warehouse read them, so
decisions like "Approve resolution to impose temporary moratorium on data center permitting"
were invisible.

Same source filter as bronze_public_participation_from_ai: publishable governance analyses
only (is_publishable_governance_analysis). source_event_id is the analysis id, the key
event_meeting uses. An item_id repeated within one analysis keeps its first occurrence, so
the key stays unique. A table (not incremental): the source is a few thousand analyses and a
full rebuild keeps a re-loaded analysis from leaving stale items beside its new ones.
*/

with source_events as (
    select
        id as event_id,
        structured_analysis,
        ai_model,
        created_at
    from {{ source('bronze', 'bronze_events_analysis_ai') }}
    where structured_analysis is not null
      and {{ is_publishable_governance_analysis('structured_analysis') }}
      and jsonb_typeof(structured_analysis->'uncontested_items') = 'array'
),

items as (
    select
        e.event_id as source_event_id,
        e.ai_model as source_ai_model,
        u.item,
        u.ordinality,
        e.created_at as extracted_at
    from source_events as e
    cross join lateral jsonb_array_elements(e.structured_analysis->'uncontested_items')
        with ordinality as u(item, ordinality)
    where jsonb_typeof(u.item) = 'object'
),

extracted as (
    select
        source_event_id,
        source_ai_model,
        nullif(btrim(item->>'item_id'), '')               as item_id,
        nullif(btrim(item->>'headline'), '')              as headline,
        nullif(btrim(item->>'outcome'), '')               as outcome,
        nullif(btrim(item->>'vote'), '')                  as vote,
        nullif(btrim(item->>'primary_theme'), '')         as primary_theme,
        nullif(btrim(item->>'primary_cause_ntee'), '')    as primary_cause_ntee,
        nullif(btrim(item->>'primary_cause_label'), '')   as primary_cause_label,
        ordinality,
        extracted_at
    from items
),

deduped as (
    select distinct on (source_event_id, item_id) *
    from extracted
    where item_id is not null
    order by source_event_id, item_id, ordinality
)

select
    (source_event_id || '_' || item_id)::text   as source_event_id_item_id,
    source_event_id::integer                    as source_event_id,
    source_ai_model::text                       as source_ai_model,
    item_id::text                               as item_id,
    headline::text                              as headline,
    outcome::text                               as outcome,
    vote::text                                  as vote,
    primary_theme::text                         as primary_theme,
    primary_cause_ntee::text                    as primary_cause_ntee,
    primary_cause_label::text                   as primary_cause_label,
    extracted_at::timestamp                     as extracted_at
from deduped
