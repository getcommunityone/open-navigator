{{
  config(
    materialized='incremental',
    unique_key='source_event_id_leg_id',
    schema='bronze',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract bills/legislation from Gemini AI analysis JSONB.

Source: bronze.bronze_events_analysis_ai.structured_analysis JSONB
Target: bronze.bronze_bills

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
      AND {{ is_publishable_governance_analysis('structured_analysis') }}
    
    {% if is_incremental() %}
        AND created_at > (SELECT MAX(extracted_at) FROM {{ this }})
    {% endif %}
),

-- Unnest legislation array
bills_unnested AS (
    SELECT 
        event_id as source_event_id,
        ai_model as source_ai_model,
        jsonb_array_elements(structured_analysis->'legislation') as bill_data,
        created_at as extracted_at
    FROM source_events
    WHERE structured_analysis ? 'legislation'
),

-- Extract bill fields
bills_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,
        bill_data->>'leg_id' as leg_id,
        bill_data->>'leg_type' as leg_type,
        bill_data->>'official_number' as official_number,
        bill_data->>'title' as title,
        bill_data->>'jurisdiction' as jurisdiction,
        CASE
            WHEN nullif(trim(bill_data->>'year'), '') ~ '^[0-9]{4}$'
            THEN trim(bill_data->>'year')
            ELSE NULL
        END as year,
        bill_data->>'status' as status,
        bill_data->>'relevance' as relevance,
        bill_data->>'url' as url,
        extracted_at
    FROM bills_unnested
    WHERE bill_data->>'leg_id' IS NOT NULL
)

SELECT
    -- Composite unique key
    source_event_id || '_' || leg_id as source_event_id_leg_id,
    
    -- All fields
    source_event_id,
    source_ai_model,
    leg_id,
    leg_type,
    official_number,
    title,
    jurisdiction,
    year,
    status,
    relevance,
    url,
    extracted_at
FROM bills_extracted
