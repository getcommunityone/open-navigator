{{ config(
    materialized='view',
    tags=['staging', 'youtube', 'channels']
) }}

/*
Staging model for bronze_events_channels

Cleans and standardizes bronze channel data with basic quality filters.
Preserves all source fields for downstream processing.

Source: bronze.bronze_events_channels (Foreign Data Wrapper from open_navigator_bronze)
*/

SELECT
    id,
    channel_id,
    channel_url,
    channel_title,
    channel_type,
    subscriber_count,
    video_count,
    
    -- Source flags (which datasets validate this channel)
    in_localview,
    in_jurisdictions_details,
    on_public_website,
    in_wikidata,
    
    -- Discovery information
    discovery_method,
    discovery_date,
    confidence_score,
    
    -- Jurisdiction associations (JSONB)
    jurisdictions,
    
    -- Quality indicators
    is_verified,
    is_government,
    flagged_as_junk,
    flag_reason,
    
    -- Timestamps
    loaded_at,
    last_updated
    
FROM {{ source('bronze', 'bronze_events_channels') }}

-- Basic data quality filters
WHERE channel_id IS NOT NULL
  AND channel_id != ''
  AND channel_url IS NOT NULL
