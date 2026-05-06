{{
  config(
    materialized='view',
    tags=['staging', 'events', 'cdp-compatible']
  )
}}

/*
Staging view for bronze_events_search

Applies basic cleaning and type casting to raw event data.
Does NOT deduplicate - that happens in intermediate layer.

CDP Compatibility: Maps to Council Data Project Event and Session models
See: https://councildataproject.org/

Source: bronze_events_search (from open_navigator_bronze via FDW)
Target: Intermediate models for deduplication and enrichment
*/

SELECT
    -- Primary key
    id AS bronze_event_id,
    
    -- Event basics (cleaned, CDP-compatible)
    TRIM(title) AS title,
    NULLIF(TRIM(description), '') AS description,
    event_date,
    event_time,
    event_datetime,  -- CDP: event_datetime
    
    -- CDP Body fields (meeting body like "City Council", "Planning Commission")
    NULLIF(TRIM(body_name), '') AS body_name,
    NULLIF(TRIM(body_description), '') AS body_description,
    
    -- Jurisdiction (normalized)
    NULLIF(TRIM(jurisdiction_id), '') AS jurisdiction_id,
    NULLIF(TRIM(jurisdiction_name), '') AS jurisdiction_name,
    NULLIF(TRIM(jurisdiction_type), '') AS jurisdiction_type,
    UPPER(TRIM(state_code)) AS state_code,
    INITCAP(TRIM(state)) AS state,
    NULLIF(TRIM(city), '') AS city,
    
    -- Meeting details
    NULLIF(TRIM(location), '') AS location,
    NULLIF(TRIM(location_description), '') AS location_description,
    NULLIF(TRIM(meeting_type), '') AS meeting_type,
    NULLIF(TRIM(status), '') AS status,
    
    -- Documents/links (cleaned URLs, CDP uses _uri suffix)
    NULLIF(TRIM(agenda_url), '') AS agenda_url,      -- CDP: agenda_uri
    NULLIF(TRIM(minutes_url), '') AS minutes_url,    -- CDP: minutes_uri
    NULLIF(TRIM(video_url), '') AS video_url,        -- CDP: session.video_uri
    NULLIF(TRIM(session_content_hash), '') AS session_content_hash,  -- CDP: session.session_content_hash
    
    -- YouTube-specific
    NULLIF(TRIM(channel_id), '') AS channel_id,
    NULLIF(TRIM(channel_url), '') AS channel_url,
    NULLIF(TRIM(channel_type), '') AS channel_type,
    view_count,
    duration_minutes,
    like_count,
    LOWER(TRIM(language)) AS language,
    
    -- Data source tracking (CDP-compatible)
    LOWER(TRIM(source)) AS source,
    NULLIF(TRIM(datasource_id), '') AS datasource_id,
    NULLIF(TRIM(external_source_id), '') AS external_source_id,  -- CDP: external_source_id
    
    -- Quality flags
    CASE 
        WHEN title IS NULL OR TRIM(title) = '' THEN TRUE 
        ELSE FALSE 
    END AS missing_title,
    
    CASE 
        WHEN event_date IS NULL THEN TRUE 
        ELSE FALSE 
    END AS missing_date,
    
    CASE 
        WHEN state_code IS NULL OR TRIM(state_code) = '' THEN TRUE 
        ELSE FALSE 
    END AS missing_state,
    
    CASE
        WHEN video_url IS NOT NULL AND channel_id IS NULL THEN TRUE
        ELSE FALSE
    END AS video_missing_channel,
    
    -- Metadata
    loaded_at,
    last_updated

FROM {{ source('bronze', 'bronze_events_search') }}

-- Basic quality filter: must have title and non-null date
WHERE 
    title IS NOT NULL 
    AND TRIM(title) != ''
    AND event_date IS NOT NULL
