{{
  config(
    materialized='incremental',
    unique_key='source_event_id_decision_id',
    schema='bronze',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract topics from Gemini AI analysis JSONB.

Topics are derived from decisions - each decision has thematic classification.

Source: bronze.bronze_events_analysis_ai.structured_analysis JSONB
Target: bronze.bronze_topics

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

-- Unnest decisions array (topics are decision attributes)
decisions_unnested AS (
    SELECT 
        event_id as source_event_id,
        ai_model as source_ai_model,
        jsonb_array_elements(structured_analysis->'decisions') as decision_data,
        created_at as extracted_at
    FROM source_events
    WHERE structured_analysis ? 'decisions'
),

-- Extract topic fields from each decision
topics_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,
        decision_data->>'decision_id' as decision_id,
        decision_data->>'primary_theme' as primary_theme,
        decision_data->>'primary_theme_cofog' as primary_theme_cofog,
        decision_data->>'secondary_theme' as secondary_theme,
        decision_data->>'secondary_theme_cofog' as secondary_theme_cofog,
        decision_data->>'ntee_code' as ntee_code,
        decision_data->>'ntee_major_group' as ntee_major_group,
        decision_data->>'ntee_category_label' as ntee_category_label,
        decision_data->>'secondary_ntee_code' as secondary_ntee_code,
        decision_data->>'secondary_ntee_major_group' as secondary_ntee_major_group,
        decision_data->>'secondary_ntee_category_label' as secondary_ntee_category_label,
        decision_data->'primary_org_ids' as primary_org_ids,
        decision_data->>'topic' as topic,
        decision_data->>'headline' as headline,
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
    primary_theme,
    primary_theme_cofog,
    secondary_theme,
    secondary_theme_cofog,
    ntee_code,
    ntee_major_group,
    ntee_category_label,
    secondary_ntee_code,
    secondary_ntee_major_group,
    secondary_ntee_category_label,
    primary_org_ids,
    topic,
    headline,
    extracted_at
FROM topics_extracted
