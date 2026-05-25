{{ config(
    materialized='view',
    tags=['intermediate', 'youtube', 'channels']
) }}

/*
Intermediate model: Enriched channels with event stats and quality scoring

Adds:
- Event statistics (count, date ranges)
- Jurisdiction counts
- Calculated quality scores
- Government likelihood assessment

Downstream: events_channels_search (mart)
*/

WITH channel_event_stats AS (
    -- Calculate event statistics per channel
    SELECT
        channel_id,
        COUNT(DISTINCT event_id) as event_count,
        COUNT(DISTINCT jurisdiction_name) as jurisdiction_count,
        MIN(event_date) as first_video_date,
        MAX(event_date) as latest_video_date
    FROM {{ ref('int_events_localview') }}
    WHERE channel_id IS NOT NULL
    GROUP BY channel_id
),

channels_with_quality AS (
    SELECT
        c.*,
        
        -- Calculate quality score based on validation sources
        CASE
            WHEN c.in_wikidata THEN 1.0                                    -- WikiData verified = highest quality
            WHEN c.in_localview AND c.in_jurisdictions_details THEN 0.9   -- Both LocalView + jurisdiction data
            WHEN c.in_localview THEN 0.85                                  -- LocalView validated
            WHEN c.in_jurisdictions_details THEN 0.7                       -- Only jurisdiction data
            ELSE 0.5                                                       -- Unknown source
        END as quality_score,
        
        -- Determine if likely government channel
        -- Use is_government if set, otherwise infer from validation sources
        COALESCE(
            c.is_government,
            CASE
                WHEN c.in_wikidata THEN TRUE                               -- WikiData = verified government
                WHEN c.in_localview AND NOT c.flagged_as_junk THEN TRUE   -- LocalView = likely government
                WHEN c.in_jurisdictions_details AND NOT c.flagged_as_junk THEN NULL  -- Unknown but not flagged
                ELSE FALSE                                                 -- Probably not government
            END
        ) as is_likely_government,
        
        -- Extract jurisdiction count from JSONB array
        CASE 
            WHEN c.jurisdictions IS NOT NULL 
            THEN jsonb_array_length(c.jurisdictions)
            ELSE 0
        END as jurisdiction_association_count
        
    FROM {{ ref('int_events_channels_registry') }} c
)

-- Join with event statistics
SELECT
    v.*,
    COALESCE(s.event_count, 0) as event_count,
    COALESCE(s.jurisdiction_count, 0) as event_jurisdiction_count,
    s.first_video_date,
    s.latest_video_date,
    
    -- Days since last video (for staleness detection)
    CASE 
        WHEN s.latest_video_date IS NOT NULL 
        THEN CURRENT_DATE - s.latest_video_date::date
        ELSE NULL
    END as days_since_last_video,
    
    -- Channel activity status
    CASE
        WHEN s.latest_video_date IS NULL THEN 'no_videos'
        WHEN CURRENT_DATE - s.latest_video_date::date <= 30 THEN 'active'
        WHEN CURRENT_DATE - s.latest_video_date::date <= 90 THEN 'recent'
        WHEN CURRENT_DATE - s.latest_video_date::date <= 365 THEN 'stale'
        ELSE 'inactive'
    END as activity_status
    
FROM channels_with_quality v
LEFT JOIN channel_event_stats s ON v.channel_id = s.channel_id
