{{
  config(
    materialized='table',
    tags=['marts', 'events', 'production'],
    unique_key='id',
    indexes=[
      {'columns': ['event_date'], 'type': 'btree'},
      {'columns': ['state_code', 'state'], 'type': 'btree'},
      {'columns': ['jurisdiction_name', 'state_code'], 'type': 'btree'},
      {'columns': ['channel_id'], 'type': 'btree'},
      {'columns': ['video_url'], 'unique': True},
      {'columns': ['source'], 'type': 'btree'}
    ]
  )
}}

/*
Production events_search table - API-ready meeting events

This model:
- Deduplicates events by video_url (keeps most recent)
- Applies quality filters
- Provides clean, consistent data for API consumption

Used by: api/routes/search_postgres.py, frontend event search

Data Flow:
bronze_events_search → stg_bronze_events_search → events_search (this model)
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
    FROM {{ ref('stg_bronze_events_search') }}
),

quality_filtered AS (
    SELECT
        bronze_event_id,
        title,
        description,
        event_date,
        event_time,
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
        agenda_url,
        minutes_url,
        video_url,
        channel_id,
        channel_url,
        channel_type,
        view_count,
        duration_minutes,
        like_count,
        language,
        source,
        datasource_id,
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
    ROW_NUMBER() OVER (ORDER BY event_date DESC, bronze_event_id) AS id,
    
    -- Event basics
    title,
    description,
    event_date,
    event_time,
    
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
    meeting_type,
    status,
    
    -- Documents/links
    agenda_url,
    minutes_url,
    video_url,
    
    -- YouTube video metrics
    view_count,
    duration_minutes,
    like_count,
    language,
    channel_type,
    channel_url,
    location_description,
    
    -- Metadata
    source,
    CURRENT_TIMESTAMP AS last_updated

FROM quality_filtered
ORDER BY event_date DESC, id
