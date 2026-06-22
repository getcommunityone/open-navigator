{{
  config(
    materialized='incremental',
    unique_key='org_name_normalized_state_code',
    schema='bronze',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract organizations from Gemini AI analysis JSONB.

Organizations are deduplicated by (org_name_normalized, state_code) for Master Data Management.
Tracks first_seen and last_seen event IDs.

Source: bronze.bronze_events_analysis_ai.structured_analysis JSONB
Target: bronze.bronze_organizations_meetings

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

-- Unnest organizations array
organizations_unnested AS (
    SELECT 
        event_id as source_event_id,
        ai_model as source_ai_model,
        jsonb_array_elements(structured_analysis->'organizations') as org_data,
        created_at as extracted_at
    FROM source_events
    WHERE structured_analysis ? 'organizations'
),

-- Extract organization fields
organizations_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,
        org_data->>'org_id' as org_id,
        org_data->>'org_name' as org_name,
        -- Normalize org name for MDM
        LOWER(TRIM(
            regexp_replace(
                regexp_replace(org_data->>'org_name', 
                    '\s+(commission|council|board|department|authority|agency)$', '', 'i'),
                '[^\w\s]', ' ', 'g'
            )
        )) as org_name_normalized,
        org_data->>'org_type' as org_type,
        org_data->>'org_subtype' as org_subtype,
        COALESCE((org_data->>'is_lobbyist_entity')::boolean, FALSE) as is_lobbyist_entity,
        org_data->'lobbying_clients' as lobbying_clients,
        org_data->>'party_affiliation' as party_affiliation,
        org_data->>'ein' as ein,
        org_data->>'wikidata_qid' as wikidata_qid,
        org_data->>'ntee_major_group' as ntee_major_group,
        org_data->>'ntee_category_label' as ntee_category_label,
        org_data->>'ntee_code' as ntee_code,
        org_data->>'role_in_meeting' as role_in_meeting,
        org_data->>'financial_interest' as financial_interest,
        -- Extract state code from org_id (pattern: org_name_XX where XX is state)
        UPPER(substring(org_data->>'org_id' from '_([a-z]{2})$')) as state_code,
        extracted_at
    FROM organizations_unnested
    WHERE org_data->>'org_name' IS NOT NULL
),

-- Aggregate to track first/last seen (for incremental updates)
organizations_aggregated AS (
    SELECT
        org_name_normalized,
        COALESCE(state_code, '') as state_code,
        -- Take values from most recent occurrence
        (array_agg(source_event_id ORDER BY extracted_at DESC))[1] as source_event_id,
        (array_agg(source_ai_model ORDER BY extracted_at DESC))[1] as source_ai_model,
        (array_agg(org_id ORDER BY extracted_at DESC))[1] as org_id,
        (array_agg(org_name ORDER BY extracted_at DESC))[1] as org_name,
        (array_agg(org_type ORDER BY extracted_at DESC))[1] as org_type,
        (array_agg(org_subtype ORDER BY extracted_at DESC))[1] as org_subtype,
        (array_agg(is_lobbyist_entity ORDER BY extracted_at DESC))[1] as is_lobbyist_entity,
        (array_agg(lobbying_clients ORDER BY extracted_at DESC))[1] as lobbying_clients,
        (array_agg(party_affiliation ORDER BY extracted_at DESC))[1] as party_affiliation,
        (array_agg(ein ORDER BY extracted_at DESC))[1] as ein,
        (array_agg(wikidata_qid ORDER BY extracted_at DESC))[1] as wikidata_qid,
        (array_agg(ntee_major_group ORDER BY extracted_at DESC))[1] as ntee_major_group,
        (array_agg(ntee_category_label ORDER BY extracted_at DESC))[1] as ntee_category_label,
        (array_agg(ntee_code ORDER BY extracted_at DESC))[1] as ntee_code,
        (array_agg(role_in_meeting ORDER BY extracted_at DESC))[1] as role_in_meeting,
        (array_agg(financial_interest ORDER BY extracted_at DESC))[1] as financial_interest,
        MAX(source_event_id) as last_seen_event_id,
        MIN(source_event_id) as first_seen_event_id,
        MAX(extracted_at) as extracted_at
    FROM organizations_extracted
    GROUP BY org_name_normalized, COALESCE(state_code, '')
)

SELECT
    -- Composite unique key for deduplication
    org_name_normalized || '_' || state_code as org_name_normalized_state_code,
    
    -- All fields
    source_event_id,
    source_ai_model,
    org_id,
    org_name,
    org_name_normalized,
    NULLIF(state_code, '') as state_code,  -- Convert empty string back to NULL
    org_type,
    org_subtype,
    is_lobbyist_entity,
    lobbying_clients,
    party_affiliation,
    ein,
    wikidata_qid,
    ntee_major_group,
    ntee_category_label,
    ntee_code,
    role_in_meeting,
    financial_interest,
    extracted_at,
    last_seen_event_id,
    first_seen_event_id
FROM organizations_aggregated
