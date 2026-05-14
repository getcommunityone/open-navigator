{{ config(
    materialized='table',
    tags=['mart', 'youtube', 'channels', 'production'],
    indexes=[
        {'columns': ['channel_id'], 'unique': True},
        {'columns': ['in_localview']},
        {'columns': ['in_wikidata']},
        {'columns': ['is_government']},
        {'columns': ['flagged_as_junk']},
        {'columns': ['activity_status']},
        {'columns': ['quality_score']}
    ]
) }}

/*
Mart: events_channels_search

Production-ready channels table with all enrichments and quality filters.
This replaces the direct-loaded events_channels_search table.

Quality rules:
- Excludes flagged junk channels UNLESS they're in LocalView (might be false positive)
- Includes quality scoring based on validation sources
- Adds event statistics and activity status
- Provides government likelihood assessment

Usage:
- API queries for channel search
- Frontend channel dropdowns
- Event association lookups
*/

SELECT
    -- Primary identifiers
    id,
    channel_id,
    channel_url,
    channel_title,
    channel_type,
    channel_description,
    channel_external_links,
    
    -- Channel metrics
    subscriber_count,
    video_count,
    view_count,
    
    -- Source validation flags
    in_localview,
    in_jurisdictions_details,
    on_public_website,
    in_wikidata,
    
    -- Discovery metadata
    discovery_method,
    discovery_date,
    confidence_score,
    quality_score,
    
    -- Jurisdiction associations
    jurisdictions,
    jurisdiction_ids,
    jurisdiction_id,
    jurisdiction_association_count,
    event_jurisdiction_count,
    
    -- Quality and classification
    is_verified,
    is_likely_government as is_government,
    flagged_as_junk,
    flag_reason,
    
    -- Event statistics
    event_count,
    first_video_date,
    latest_video_date,
    days_since_last_video,
    activity_status,
    
    -- Metadata
    loaded_at,
    CURRENT_TIMESTAMP as last_updated
    
FROM {{ ref('int_events_channels_enriched') }}

-- Exclude junk channels from production UNLESS validated by LocalView
WHERE NOT flagged_as_junk
   OR in_localview  -- Keep if in LocalView (might be false positive flag)

-- Only include channels with some validation
AND (
    in_localview 
    OR in_wikidata 
    OR in_jurisdictions_details
    OR quality_score >= 0.7
)
