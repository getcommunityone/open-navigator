{{
  config(
    materialized='incremental',
    unique_key='source_event_id_speaker_id',
    schema='bronze',
    on_schema_change='sync_all_columns',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

/*
Extract public-comment speakers from the Gemini AI analysis JSONB.

Source: bronze.bronze_events_analysis_ai.structured_analysis -> 'public_participation'
Target: bronze.bronze_public_participation_from_ai

Each element is one speaker turn during public comment:
  speaker_id, topic, stance, summary, primary_theme, place_refs,
  timestamp_start_seconds, timestamp_end_seconds.

Powers the `engagement` interestingness component (speaker count + duration).

COVERAGE CAVEAT: as of 2026-06 only ~1 of ~1,569 analyses carries a
public_participation array (the analyzer rarely emits it yet), so engagement is
near-empty in practice today. This model mirrors the bronze_*_from_ai family so
the signal lights up automatically as the analyzer backfills the array — no
downstream change needed. Until then, engagement degrades to ~0 (handled, not
faked, in int_civic__item_signals).

Incremental: only processes new events since last run.
*/

WITH source_events AS (
    SELECT
        id as event_id,
        structured_analysis,
        ai_model,
        created_at
    FROM {{ source('bronze', 'bronze_events_analysis_ai') }}
    WHERE structured_analysis IS NOT NULL
      AND {{ is_publishable_governance_analysis('structured_analysis') }}
      AND jsonb_typeof(structured_analysis->'public_participation') = 'array'

    {% if is_incremental() %}
        AND created_at > (SELECT MAX(extracted_at) FROM {{ this }})
    {% endif %}
),

participation_unnested AS (
    SELECT
        event_id as source_event_id,
        ai_model as source_ai_model,
        jsonb_array_elements(structured_analysis->'public_participation') as pp,
        created_at as extracted_at
    FROM source_events
),

participation_extracted AS (
    SELECT
        source_event_id,
        source_ai_model,
        pp->>'speaker_id'    as speaker_id,
        pp->>'topic'         as topic,
        pp->>'stance'        as stance,
        pp->>'summary'       as summary,
        pp->>'primary_theme' as primary_theme,
        pp->'place_refs'     as place_refs,
        -- numeric timestamps, guarded against free-text
        CASE WHEN (pp->>'timestamp_start_seconds') ~ '^-?[0-9]+(\.[0-9]+)?$'
             THEN (pp->>'timestamp_start_seconds')::numeric END as timestamp_start_seconds,
        CASE WHEN (pp->>'timestamp_end_seconds') ~ '^-?[0-9]+(\.[0-9]+)?$'
             THEN (pp->>'timestamp_end_seconds')::numeric END   as timestamp_end_seconds,
        extracted_at
    FROM participation_unnested
    WHERE pp->>'speaker_id' IS NOT NULL
)

SELECT
    source_event_id || '_' || speaker_id as source_event_id_speaker_id,
    source_event_id,
    source_ai_model,
    speaker_id,
    topic,
    stance,
    summary,
    primary_theme,
    place_refs,
    timestamp_start_seconds,
    timestamp_end_seconds,
    extracted_at
FROM participation_extracted
