{{
    config(
        materialized='view',
        schema='bronze',
        tags=['bronze', 'ballot_measures', 'ai_extraction'],
    )
}}

/*
Placeholder for AI-extracted ballot measures from meeting minutes / policy JSON.

Empty until a loader exists; ``bronze_ballot_measures_nist`` still compiles and unions zero rows.
*/

SELECT
    NULL::text                              AS source_event_id,
    NULL::text                              AS measure_id,
    NULL::text                              AS ocd_division_id,
    NULL::jsonb                             AS measure_data,
    NULL::timestamptz                       AS extracted_at
WHERE false
