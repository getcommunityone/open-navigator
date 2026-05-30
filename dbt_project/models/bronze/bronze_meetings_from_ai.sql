{{
  config(
    materialized='incremental',
    unique_key='source_event_id',
    schema='bronze',
    on_schema_change='sync_all_columns',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract the meeting-level block from Gemini AI analysis JSONB.

Source: bronze.bronze_events_analysis_ai.structured_analysis -> 'meeting'
Target: bronze.bronze_meetings_from_ai

Unlike the other bronze_*_from_ai extractors, `meeting` is a single object per
analysis (not an array), so the grain here is one row per analysis
(bronze_events_analysis_ai.id). This is the parent record the child extractions
(persons/decisions/places/...) all hang off of via source_event_id.

Incremental: only processes new analyses since the last run.
*/

WITH source_events AS (
    SELECT
        id as event_id,
        structured_analysis,
        ai_model,
        video_id,
        created_at
    FROM {{ source('bronze', 'bronze_events_analysis_ai') }}
    WHERE structured_analysis IS NOT NULL
      AND structured_analysis ? 'meeting'

    {% if is_incremental() %}
        AND created_at > (SELECT MAX(extracted_at) FROM {{ this }})
    {% endif %}
),

meeting_extracted AS (
    SELECT
        event_id                                  as source_event_id,
        ai_model                                  as source_ai_model,
        video_id,

        structured_analysis->'meeting'            as meeting_data,
        -- top-level event_date is the canonical calendar date for the analysis
        structured_analysis->>'event_date'        as event_date,

        created_at                                as extracted_at
    FROM source_events
)

SELECT
    source_event_id,
    source_ai_model,
    video_id,

    meeting_data->>'meeting_id'        as meeting_id,
    meeting_data->>'body_name'         as body_name,
    meeting_data->>'meeting_date'      as meeting_date,
    meeting_data->>'jurisdiction'      as jurisdiction,
    meeting_data->>'meeting_summary'   as meeting_summary,
    meeting_data->>'agenda_summary'    as agenda_summary,
    meeting_data->'session_info'       as session_info,

    event_date,
    extracted_at
FROM meeting_extracted
