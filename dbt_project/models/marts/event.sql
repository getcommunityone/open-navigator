{{
  config(
    materialized='table',
    tags=['marts', 'events', 'production', 'cdp-compatible'],
    unique_key='event_id',
    indexes=[
      {'columns': ['event_date'], 'type': 'btree'},
      {'columns': ['event_datetime'], 'type': 'btree'},
      {'columns': ['state_code', 'state'], 'type': 'btree'},
      {'columns': ['jurisdiction_name', 'state_code'], 'type': 'btree'},
      {'columns': ['body_name'], 'type': 'btree'},
      {'columns': ['channel_id'], 'type': 'btree'},
      {'columns': ['video_url'], 'unique': True},
      {'columns': ['source'], 'type': 'btree'}
    ]
  )
}}

/*
Production event table - API-ready meeting events

CDP-Compatible: Follows Council Data Project (CDP) backend schema
See: https://councildataproject.org/cdp-backend/database_models.html

This model:
- Deduplicates events by video_url (keeps most recent)
- Applies quality filters
- Provides clean, consistent data for API consumption
- Maps to CDP Event and Session models

Used by: api/routes/search_postgres.py, frontend event search

Data Flow:
bronze_events_cdp → stg_bronze_events_cdp → event (this model)
*/

WITH deduplicated_events AS (
    SELECT
        *,
        -- Rank by loaded_at to keep most recent version
        ROW_NUMBER() OVER (
            PARTITION BY 
                CASE 
                    WHEN video_url IS NOT NULL THEN video_url
                    ELSE CONCAT(datasource_id, '_', source)
                END
            ORDER BY loaded_at DESC, bronze_event_id DESC
        ) AS row_num
    FROM {{ ref('stg_bronze_events_cdp') }}
),

quality_filtered AS (
    SELECT
        bronze_event_id,
        title,
        description,
        event_date,
        event_time,
        event_datetime,          -- CDP: event_datetime
        body_name,               -- CDP: body.name
        body_description,        -- CDP: body.description
        event_date,
        event_time,
        event_datetime,          -- CDP: event_datetime
        body_name,               -- CDP: body.name
        body_description,        -- CDP: body.description
        jurisdiction_id,
        jurisdiction_name,
        jurisdiction_type,
        state_code,
        state,
        city,
        location,
        location_description,
        meeting_type,
        status,
        agenda_url,              -- CDP: agenda_uri
        minutes_url,             -- CDP: minutes_uri
        video_url,               -- CDP: session.video_uri
        session_content_hash,    -- CDP: session.session_content_hash
        channel_id,
        channel_url,
        channel_type,
        view_count,
        duration_minutes,
        like_count,
        language,
        source,
        datasource_id,
        external_source_id,      -- CDP: external_source_id
        loaded_at,
        last_updated
    FROM deduplicated_events
    WHERE 
        row_num = 1  -- Keep only one record per unique event
        AND NOT missing_title
        AND NOT missing_date
        -- Optional: Add state filter if needed
        -- AND NOT missing_state
)

SELECT
    -- Use bronze_event_id as primary key for now
    -- In production, this will be id SERIAL
    ROW_NUMBER() OVER (ORDER BY event_date DESC, bronze_event_id) AS event_id,
    
    -- Event basics (CDP-compatible)
    title AS event_title,
    description AS event_description,
    event_date,
    event_time,
    event_datetime,              -- CDP: event_datetime
    
    -- Meeting Body (CDP concept)
    body_name,                   -- CDP: body.name
    body_description,            -- CDP: body.description
    
    -- Organization/Jurisdiction
    jurisdiction_id,
    channel_id,
    jurisdiction_name,
    jurisdiction_type,
    state_code,
    state,
    city,
    
    -- Meeting details
    location,
    location_description,
    meeting_type,
    status,
    
    -- Documents/links (CDP-compatible)
    agenda_url,                  -- CDP: agenda_uri
    minutes_url,                 -- CDP: minutes_uri
    video_url,                   -- CDP: session.video_uri
    session_content_hash,        -- CDP: session.session_content_hash
    
    -- YouTube video metrics
    view_count,
    duration_minutes,
    like_count,
    language,
    channel_type,
    channel_url,
    
    -- Data source tracking (CDP-compatible)
    source,
    datasource_id,
    external_source_id,          -- CDP: external_source_id
    CURRENT_TIMESTAMP AS last_updated

FROM quality_filtered
ORDER BY event_date DESC, event_id
