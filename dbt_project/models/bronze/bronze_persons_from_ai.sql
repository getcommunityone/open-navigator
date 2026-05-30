{{
  config(
    materialized='incremental',
    unique_key='source_event_id_person_id',
    schema='bronze',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract contacts (people) from Gemini AI analysis JSONB.

This model replaces the Python script load_meeting_transcripts_bronze.py
for the bronze_contacts table.

Source: bronze.bronze_events_analysis_ai.structured_analysis JSONB
Target: bronze.bronze_contacts

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
        -- Only process records newer than what we already have
        AND created_at > (SELECT MAX(extracted_at) FROM {{ this }})
    {% endif %}
),

-- Unnest the people array from JSONB
people_unnested AS (
    SELECT 
        event_id as source_event_id,
        ai_model as source_ai_model,
        jsonb_array_elements(structured_analysis->'people') as person_data,
        created_at as extracted_at
    FROM source_events
    WHERE structured_analysis ? 'people'  -- Only if people key exists
),

-- Extract person fields
contacts_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,
        person_data->>'person_id' as person_id,
        person_data->>'full_name' as full_name,
        person_data->>'role' as role,
        person_data->>'org_id' as org_id,
        person_data->>'party_affiliation' as party_affiliation,
        COALESCE((person_data->>'is_lobbyist')::boolean, FALSE) as is_lobbyist,
        person_data->>'lobbyist_registration_number' as lobbyist_registration_number,
        person_data->'lobbyist_clients' as lobbyist_clients,  -- Keep as JSONB
        person_data->>'wikidata_qid' as wikidata_qid,
        person_data->>'appeared_as' as appeared_as,
        extracted_at
    FROM people_unnested
    WHERE person_data->>'person_id' IS NOT NULL  -- Must have person_id
)

SELECT
    -- Create composite unique key for incremental deduplication
    source_event_id || '_' || person_id as source_event_id_person_id,
    
    -- All fields
    source_event_id,
    source_ai_model,
    person_id,
    full_name,
    role,
    org_id,
    party_affiliation,
    is_lobbyist,
    lobbyist_registration_number,
    lobbyist_clients,
    wikidata_qid,
    appeared_as,
    extracted_at
FROM contacts_extracted
