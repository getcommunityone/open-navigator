{{
  config(
    materialized='incremental',
    unique_key='source_event_id_decision_id',
    schema='bronze',
    on_schema_change='sync_all_columns',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract decisions from Gemini AI analysis JSONB.

Source: bronze.bronze_events_analysis_ai.structured_analysis -> 'decisions'
Target: bronze.bronze_decisions_from_ai

The decision schema was reworked: decisions now carry a subject/place/legislation
reference graph plus rich narrative blocks (human_element, competing_views,
smart_brevity) and rendered diagrams. Scalar fields land in their own columns;
reference arrays and nested objects are stored as JSONB.

Incremental: Only processes new events since last run.
NOTE: schema changed from the prior version — run once with `--full-refresh`.
*/

WITH source_events AS (
    SELECT
        id as event_id,
        structured_analysis,
        ai_model,
        created_at
    FROM {{ source('bronze', 'bronze_events_analysis_ai') }}
    WHERE structured_analysis IS NOT NULL
      AND {{ is_publishable_governance_analysis('structured_analysis') }}

    {% if is_incremental() %}
        AND created_at > (SELECT MAX(extracted_at) FROM {{ this }})
    {% endif %}
),

-- Unnest the decisions array from JSONB
decisions_unnested AS (
    SELECT
        event_id as source_event_id,
        ai_model as source_ai_model,
        jsonb_array_elements(structured_analysis->'decisions') as decision_data,
        created_at as extracted_at
    FROM source_events
    WHERE structured_analysis ? 'decisions'
),

-- Extract decision fields (mix of scalars, reference arrays, and nested objects)
decisions_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,

        -- Identity & references
        decision_data->>'decision_id' as decision_id,
        decision_data->>'subject_id' as subject_id,
        decision_data->>'primary_place_id' as primary_place_id,
        decision_data->'place_refs' as place_refs,
        decision_data->'legislation_refs' as legislation_refs,
        decision_data->'financial_item_refs' as financial_item_refs,

        -- Headline narrative
        decision_data->>'headline' as headline,
        decision_data->>'decision_statement' as decision_statement,
        decision_data->>'primary_theme' as primary_theme,
        decision_data->>'outcome' as outcome,
        decision_data->'vote_tally' as vote_tally,

        -- Rich narrative blocks (nested objects)
        decision_data->'human_element' as human_element,
        decision_data->'competing_views' as competing_views,
        decision_data->'smart_brevity' as smart_brevity,

        -- Rendered diagrams
        decision_data->>'diagram_timeline' as diagram_timeline,
        decision_data->'diagram_timeline_lines' as diagram_timeline_lines,
        decision_data->>'diagram_mindmap' as diagram_mindmap,
        decision_data->'diagram_mindmap_lines' as diagram_mindmap_lines,

        extracted_at
    FROM decisions_unnested
    WHERE decision_data->>'decision_id' IS NOT NULL
)

SELECT
    -- Composite unique key
    source_event_id || '_' || decision_id as source_event_id_decision_id,

    -- All fields
    source_event_id,
    source_ai_model,
    decision_id,
    subject_id,
    primary_place_id,
    place_refs,
    legislation_refs,
    financial_item_refs,
    headline,
    decision_statement,
    primary_theme,
    outcome,
    vote_tally,
    human_element,
    competing_views,
    smart_brevity,
    diagram_timeline,
    diagram_timeline_lines,
    diagram_mindmap,
    diagram_mindmap_lines,
    extracted_at
FROM decisions_extracted
