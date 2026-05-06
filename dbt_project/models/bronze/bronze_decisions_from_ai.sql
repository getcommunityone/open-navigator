{{
  config(
    materialized='incremental',
    unique_key='source_event_id_decision_id',
    schema='bronze',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract decisions from Gemini AI analysis JSONB.

This model replaces the Python script load_meeting_transcripts_bronze.py
for the bronze_decisions table.

Source: bronze.bronze_events_analysis_ai.structured_analysis JSONB
Target: bronze.bronze_decisions

Incremental: Only processes new events since last run
*/

WITH source_events AS (
    SELECT 
        id as event_id,
        structured_analysis,
        ai_model,
        created_at
    FROM {{ source('bronze', 'bronze_events_analysis_ai') }}
    WHERE structured_analysis IS NOT NULL
    
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

-- Extract decision fields (complex nested JSONB)
decisions_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,
        decision_data->>'decision_id' as decision_id,
        decision_data->>'subject_id' as subject_id,
        decision_data->>'agenda_item' as agenda_item,
        decision_data->>'timestamp_start' as timestamp_start,
        decision_data->>'timestamp_end' as timestamp_end,
        (decision_data->>'decision_date')::date as decision_date,
        decision_data->>'topic' as topic,
        decision_data->>'headline' as headline,
        decision_data->>'decision_statement' as decision_statement,
        decision_data->>'decision_method' as decision_method,
        decision_data->>'lineage_type' as lineage_type,
        decision_data->>'lineage_note' as lineage_note,
        
        -- Theme classification
        decision_data->>'primary_theme' as primary_theme,
        decision_data->>'primary_theme_cofog' as primary_theme_cofog,
        decision_data->>'secondary_theme' as secondary_theme,
        decision_data->>'secondary_theme_cofog' as secondary_theme_cofog,
        
        -- NTEE codes
        decision_data->'primary_org_ids' as primary_org_ids,
        decision_data->>'ntee_code' as ntee_code,
        decision_data->>'ntee_major_group' as ntee_major_group,
        decision_data->>'ntee_category_label' as ntee_category_label,
        decision_data->>'secondary_ntee_code' as secondary_ntee_code,
        decision_data->>'secondary_ntee_major_group' as secondary_ntee_major_group,
        decision_data->>'secondary_ntee_category_label' as secondary_ntee_category_label,
        
        -- Outcome and analysis
        decision_data->>'outcome' as outcome,
        decision_data->'vote_tally' as vote_tally,
        decision_data->'timeline' as timeline,
        decision_data->'arguments_for' as arguments_for,
        decision_data->'arguments_against' as arguments_against,
        decision_data->'tradeoffs' as tradeoffs,
        decision_data->'underlying_causes' as underlying_causes,
        decision_data->'power_map' as power_map,
        decision_data->'frame_analysis' as frame_analysis,
        decision_data->'legislation_refs' as legislation_refs,
        decision_data->'financial_item_refs' as financial_item_refs,
        
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
    agenda_item,
    timestamp_start,
    timestamp_end,
    decision_date,
    topic,
    headline,
    decision_statement,
    decision_method,
    lineage_type,
    lineage_note,
    primary_theme,
    primary_theme_cofog,
    secondary_theme,
    secondary_theme_cofog,
    primary_org_ids,
    ntee_code,
    ntee_major_group,
    ntee_category_label,
    secondary_ntee_code,
    secondary_ntee_major_group,
    secondary_ntee_category_label,
    outcome,
    vote_tally,
    timeline,
    arguments_for,
    arguments_against,
    tradeoffs,
    underlying_causes,
    power_map,
    frame_analysis,
    legislation_refs,
    financial_item_refs,
    extracted_at
FROM decisions_extracted
