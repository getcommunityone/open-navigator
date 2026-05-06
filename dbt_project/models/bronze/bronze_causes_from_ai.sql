{{
  config(
    materialized='incremental',
    unique_key='cause_headline',
    schema='bronze',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract underlying causes from Gemini AI analysis JSONB.

Causes are extracted from decisions.underlying_causes array.
Deduplicated by cause_headline to track trending issues across meetings.

Source: bronze.bronze_events_analysis_ai.structured_analysis JSONB
Target: bronze.bronze_causes

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

-- Unnest decisions array
decisions_unnested AS (
    SELECT 
        event_id as source_event_id,
        ai_model as source_ai_model,
        jsonb_array_elements(structured_analysis->'decisions') as decision_data,
        created_at as extracted_at
    FROM source_events
    WHERE structured_analysis ? 'decisions'
),

-- Unnest underlying_causes array within each decision
causes_unnested AS (
    SELECT
        source_event_id,
        source_ai_model,
        decision_data->>'decision_id' as decision_id,
        jsonb_array_elements(decision_data->'underlying_causes') as cause_data,
        extracted_at
    FROM decisions_unnested
    WHERE decision_data ? 'underlying_causes'
      AND decision_data->'underlying_causes' != 'null'::jsonb
      AND jsonb_array_length(decision_data->'underlying_causes') > 0
),

-- Extract cause fields
causes_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,
        decision_id,
        cause_data->>'headline' as cause_headline,
        cause_data->>'detail' as cause_detail,
        extracted_at
    FROM causes_unnested
    WHERE cause_data->>'headline' IS NOT NULL
      AND TRIM(cause_data->>'headline') != ''
),

-- Aggregate by cause_headline to track first/last seen
causes_aggregated AS (
    SELECT
        cause_headline,
        -- Take values from most recent occurrence
        (array_agg(source_event_id ORDER BY extracted_at DESC))[1] as source_event_id,
        (array_agg(source_ai_model ORDER BY extracted_at DESC))[1] as source_ai_model,
        (array_agg(decision_id ORDER BY extracted_at DESC))[1] as decision_id,
        (array_agg(cause_detail ORDER BY extracted_at DESC))[1] as cause_detail,
        MAX(source_event_id) as last_seen_event_id,
        MIN(source_event_id) as first_seen_event_id,
        MAX(extracted_at) as extracted_at
    FROM causes_extracted
    GROUP BY cause_headline
)

SELECT
    -- Unique key (cause headline)
    cause_headline,
    
    -- All fields
    source_event_id,
    source_ai_model,
    decision_id,
    cause_detail,
    extracted_at,
    last_seen_event_id,
    first_seen_event_id
FROM causes_aggregated
