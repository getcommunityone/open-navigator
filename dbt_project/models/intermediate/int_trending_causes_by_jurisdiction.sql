{{
    config(
        materialized='table'
    )
}}

/*
    Intermediate model: Trending Causes by Jurisdiction
    
    Aggregates decision counts by cause (NTEE major group) and jurisdiction
    for the last 90 days. Used to populate trending_causes JSON in stats_aggregates.
*/

WITH recent_decisions AS (
    SELECT *
    FROM {{ ref('stg_bronze_decisions') }}
    WHERE is_recent = true
),

-- For now, we don't have junction info in bronze_decisions
-- We'll need to add jurisdiction data later or derive it from another source
-- Using topic/theme grouping instead
decisions_aggregated AS (
    SELECT 
        d.*,
        -- TODO: Add jurisdiction lookup when bronze_events or equivalent is available
        'Unknown' as jurisdiction_name,
        NULL::VARCHAR(2) as state_code,
        NULL::VARCHAR(50) as state,
        'jurisdiction' as jurisdiction_type
    FROM recent_decisions d
),

-- Aggregate by cause and jurisdiction
cause_aggregates AS (
    SELECT
        -- Jurisdiction identifiers (placeholder for now)
        state_code,
        state,
        jurisdiction_name,
        jurisdiction_type,
        
        -- Cause identifier (use secondary_ntee_major_group or primary_theme)
        COALESCE(secondary_ntee_major_group, primary_theme) as cause_category,
        COALESCE(secondary_ntee_code, primary_theme_cofog) as cause_code,
        
        -- Decision counts
        COUNT(*) as decision_count,
        COUNT(DISTINCT topic) as unique_topics,
        
        -- Most recent decision date
        MAX(decision_date) as most_recent_decision,
        
        -- Average age of decisions
        AVG(days_since_decision) as avg_days_old,
        
        -- Sample headlines (for context)
        ARRAY_AGG(headline ORDER BY decision_date DESC LIMIT 3) as sample_headlines
        
    FROM decisions_aggregated
    WHERE secondary_ntee_major_group IS NOT NULL  -- Only decisions with cause mapping
       OR primary_theme IS NOT NULL
    GROUP BY 
        state_code,
        state,
        jurisdiction_name,
        jurisdiction_type,
        COALESCE(secondary_ntee_major_group, primary_theme),
        COALESCE(secondary_ntee_code, primary_theme_cofog)
),

-- Rank causes within each jurisdiction
ranked_causes AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY state_code, jurisdiction_name 
            ORDER BY decision_count DESC, most_recent_decision DESC
        ) as cause_rank
    FROM cause_aggregates
)

-- Only keep top 10 causes per jurisdiction
SELECT
    state_code,
    state,
    jurisdiction_name,
    jurisdiction_type,
    cause_category,
    cause_code,
    decision_count,
    unique_topics,
    most_recent_decision,
    avg_days_old,
    sample_headlines,
    cause_rank
FROM ranked_causes
WHERE cause_rank <= 10  -- Top 10 trending causes per jurisdiction
ORDER BY 
    state_code,
    jurisdiction_name,
    cause_rank
