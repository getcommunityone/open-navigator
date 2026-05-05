{{
    config(
        materialized='view'
    )
}}

/*
    Staging model for bronze_decisions
    
    - Cleans and normalizes decision data
    - Filters recent decisions (last 90 days)
    - Prepares for cause aggregation
*/

WITH source AS (
    SELECT * FROM {{ source('bronze', 'bronze_decisions') }}
),

cleaned AS (
    SELECT
        id as bronze_decision_id,
        source_event_id,
        source_ai_model,
        decision_id,
        subject_id,
        
        -- Topic and headline
        topic,
        headline,
        decision_statement,
        
        -- Themes and causes
        primary_theme,
        primary_theme_cofog,
        secondary_theme,
        secondary_theme_cofog,
        
        -- NTEE codes for cause categorization
        primary_org_ids,
        secondary_ntee_code,
        secondary_ntee_major_group,
        secondary_ntee_category_label,
        
        -- Decision metadata
        decision_date,
        outcome,
        decision_method,
        
        -- Timestamps for recency filtering
        extracted_at,
        
        -- Flag recent decisions (last 90 days)
        CASE 
            WHEN decision_date >= CURRENT_DATE - INTERVAL '90 days' 
            THEN true 
            ELSE false 
        END as is_recent,
        
        -- Days since decision (for trending calculations)
        CURRENT_DATE - decision_date as days_since_decision
        
    FROM source
    WHERE decision_date IS NOT NULL  -- Only include decisions with valid dates
)

SELECT * FROM cleaned
