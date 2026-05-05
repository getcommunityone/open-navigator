{{
    config(
        materialized='table',
        unique_key=['level', 'state_code', 'county', 'city']
    )
}}

/*
    Stats Aggregates - Jurisdiction-level statistics with trending causes
    
    Builds stats_aggregates table with:
    - Jurisdiction counts, nonprofit counts, event counts, contact counts
    - Trending causes (JSON) based on decisions in last 90 days
    
    Levels: national, state, county, city, jurisdiction
*/

WITH trending_causes AS (
    SELECT
        state_code,
        state,
        jurisdiction_name,
        -- Build JSON array of trending causes
        JSONB_AGG(
            JSONB_BUILD_OBJECT(
                'cause', cause_category,
                'code', cause_code,
                'decision_count', decision_count,
                'topics', unique_topics,
                'most_recent', most_recent_decision,
                'rank', cause_rank,
                'sample_headlines', sample_headlines
            )
            ORDER BY cause_rank
        ) as trending_causes_json
    FROM {{ ref('int_trending_causes_by_jurisdiction') }}
    GROUP BY state_code, state, jurisdiction_name
),

-- National level stats
national_stats AS (
    SELECT
        'national' as level,
        NULL::VARCHAR(2) as state_code,
        NULL::VARCHAR(50) as state,
        NULL::VARCHAR(100) as county,
        NULL::VARCHAR(100) as city,
        
        -- Counts (placeholder - would aggregate from state level)
        0 as jurisdictions_count,
        0 as school_districts_count,
        0 as nonprofits_count,
        0 as events_count,
        0 as bills_count,
        0 as contacts_count,
        0::BIGINT as total_revenue,
        0::BIGINT as total_assets,
        
        -- National trending causes (aggregate across all states)
        NULL::JSONB as trending_causes,
        
        CURRENT_TIMESTAMP as last_updated
),

-- State level stats
state_stats AS (
    SELECT
        'state' as level,
        tc.state_code,
        tc.state,
        NULL::VARCHAR(100) as county,
        NULL::VARCHAR(100) as city,
        
        -- Counts (placeholder - would aggregate from jurisdiction level)
        0 as jurisdictions_count,
        0 as school_districts_count,
        0 as nonprofits_count,
        0 as events_count,
        0 as bills_count,
        0 as contacts_count,
        0::BIGINT as total_revenue,
        0::BIGINT as total_assets,
        
        -- Aggregate trending causes across all jurisdictions in state
        JSONB_AGG(
            JSONB_BUILD_OBJECT(
                'jurisdiction', tc.jurisdiction_name,
                'causes', tc.trending_causes_json
            )
        ) as trending_causes,
        
        CURRENT_TIMESTAMP as last_updated
    FROM trending_causes tc
    GROUP BY tc.state_code, tc.state
),

-- Jurisdiction level stats (city/county/township)
jurisdiction_stats AS (
    SELECT
        'jurisdiction' as level,
        tc.state_code,
        tc.state,
        NULL::VARCHAR(100) as county,
        tc.jurisdiction_name as city,
        
        -- Counts (placeholder - would load from gold parquet files)
        0 as jurisdictions_count,
        0 as school_districts_count,
        0 as nonprofits_count,
        0 as events_count,
        0 as bills_count,
        0 as contacts_count,
        0::BIGINT as total_revenue,
        0::BIGINT as total_assets,
        
        -- Trending causes for this jurisdiction
        tc.trending_causes_json as trending_causes,
        
        CURRENT_TIMESTAMP as last_updated
    FROM trending_causes tc
)

-- Combine all levels
SELECT * FROM national_stats
UNION ALL
SELECT * FROM state_stats
UNION ALL
SELECT * FROM jurisdiction_stats
