{{
    config(
        materialized='view'
    )
}}

/*
    Staging model for bronze_bills
    
    - Normalizes bill numbers
    - Standardizes jurisdiction names
    - Prepares for matching with OpenStates data
*/

WITH source AS (
    SELECT * FROM {{ source('bronze', 'bronze_bills') }}
),

cleaned AS (
    SELECT
        id as bronze_bill_id,
        source_event_id,
        source_ai_model,
        
        -- Bill identifiers
        leg_id,  -- OpenStates ID if matched (ocd-bill/...)
        official_number,
        {{ normalize_bill_number('official_number') }} as bill_number_normalized,
        
        -- Bill details
        title,
        LOWER(TRIM(title)) as title_normalized,
        leg_type,
        
        -- Jurisdiction
        jurisdiction,
        LOWER(TRIM(jurisdiction)) as jurisdiction_normalized,
        year,
        CAST(year AS TEXT) || 'rs' as session_guess,  -- Guess session format
        
        -- Status
        status,
        relevance,
        url,
        
        -- Metadata
        extracted_at
        
    FROM source
    
    WHERE 1=1
        AND title IS NOT NULL
        AND LENGTH(TRIM(title)) > 5
        AND (
            leg_id IS NOT NULL
            OR official_number IS NOT NULL
            OR (jurisdiction IS NOT NULL AND year IS NOT NULL)
        )
)

SELECT * FROM cleaned
