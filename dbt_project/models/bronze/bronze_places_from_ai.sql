{{
  config(
    materialized='incremental',
    unique_key='source_event_id_place_id',
    schema='bronze',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract places from Gemini AI analysis JSONB.

Source: bronze.bronze_events_analysis_ai.structured_analysis -> 'places'
Target: bronze.bronze_places_from_ai

Places are geocodable locations mentioned in a meeting. They carry a raw mention,
a normalized address / geocode query, lat/long (often pending), and reference
arrays linking them back to decisions and agenda items.

Incremental: Only processes new events since last run.
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

-- Unnest the places array from JSONB
places_unnested AS (
    SELECT
        event_id as source_event_id,
        ai_model as source_ai_model,
        jsonb_array_elements(structured_analysis->'places') as place_data,
        created_at as extracted_at
    FROM source_events
    WHERE structured_analysis ? 'places'
),

-- Extract place fields
places_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,
        place_data->>'place_id' as place_id,
        place_data->>'raw_text' as raw_text,
        place_data->>'normalized_address' as normalized_address,
        place_data->>'place_type' as place_type,
        place_data->>'street_address' as street_address,
        place_data->>'city' as city,
        place_data->>'state' as state_code,
        place_data->>'geocode_query' as geocode_query,
        (place_data->>'latitude')::double precision as latitude,
        (place_data->>'longitude')::double precision as longitude,
        place_data->>'geocode_status' as geocode_status,
        place_data->'linked_decision_ids' as linked_decision_ids,
        place_data->'linked_item_ids' as linked_item_ids,
        (place_data->>'mention_count')::int as mention_count,
        extracted_at
    FROM places_unnested
    WHERE place_data->>'place_id' IS NOT NULL
)

SELECT
    -- Composite unique key
    source_event_id || '_' || place_id as source_event_id_place_id,

    -- All fields
    source_event_id,
    source_ai_model,
    place_id,
    raw_text,
    normalized_address,
    place_type,
    street_address,
    city,
    state_code,
    geocode_query,
    latitude,
    longitude,
    geocode_status,
    linked_decision_ids,
    linked_item_ids,
    mention_count,
    extracted_at
FROM places_extracted
