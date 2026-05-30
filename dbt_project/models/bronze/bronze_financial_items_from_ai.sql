{{
  config(
    materialized='incremental',
    unique_key='source_event_id_financial_item_id',
    schema='bronze',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract financial items from Gemini AI analysis JSONB.

Financial items track budget allocations, expenditures, and funding mentioned in meetings.

Source: bronze.bronze_events_analysis_ai.structured_analysis JSONB
Target: bronze.bronze_financial_items

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

-- Unnest financial_items array
financial_items_unnested AS (
    SELECT 
        event_id as source_event_id,
        ai_model as source_ai_model,
        jsonb_array_elements(structured_analysis->'financial_items') as financial_data,
        created_at as extracted_at
    FROM source_events
    WHERE structured_analysis ? 'financial_items'
),

-- Extract financial item fields
financial_items_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,
        financial_data->>'financial_item_id' as financial_item_id,
        financial_data->>'decision_id' as decision_id,
        financial_data->>'subject_id' as subject_id,
        financial_data->>'event_description' as event_description,
        financial_data->>'item_description' as item_description,
        -- Gemini sometimes emits free-text amounts ("1.2 to 1.3 million", "TBD").
        -- Strip $ , and whitespace, then cast only if a clean number remains;
        -- otherwise NULL (the raw text is preserved in amount_qualifier / notes).
        CASE
            WHEN regexp_replace(financial_data->>'amount', '[\s$,]', '', 'g') ~ '^-?[0-9]+(\.[0-9]+)?$'
            THEN regexp_replace(financial_data->>'amount', '[\s$,]', '', 'g')::numeric
        END as amount,
        financial_data->>'amount_type' as amount_type,
        financial_data->>'amount_qualifier' as amount_qualifier,
        COALESCE(financial_data->>'currency', 'USD') as currency,
        -- Guard against free-text dates; only parse strict ISO YYYY-MM-DD.
        CASE
            WHEN financial_data->>'item_date' ~ '^\d{4}-\d{2}-\d{2}$'
            THEN (financial_data->>'item_date')::date
        END as item_date,
        financial_data->>'item_date_type' as item_date_type,
        financial_data->>'org_id' as org_id,
        financial_data->>'org_role' as org_role,
        financial_data->>'authorized_by_person_id' as authorized_by_person_id,
        financial_data->>'funding_source' as funding_source,
        financial_data->>'notes' as notes,
        extracted_at
    FROM financial_items_unnested
    WHERE financial_data->>'financial_item_id' IS NOT NULL
)

SELECT
    -- Composite unique key
    source_event_id || '_' || financial_item_id as source_event_id_financial_item_id,
    
    -- All fields
    source_event_id,
    source_ai_model,
    financial_item_id,
    decision_id,
    subject_id,
    event_description,
    item_description,
    amount,
    amount_type,
    amount_qualifier,
    currency,
    item_date,
    item_date_type,
    org_id,
    org_role,
    authorized_by_person_id,
    funding_source,
    notes,
    extracted_at
FROM financial_items_extracted
