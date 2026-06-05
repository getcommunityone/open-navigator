{{
    config(
        materialized='view'
    )
}}

/*
Staging for bronze.bronze_policy_decisions — the TEXT/policy transcript-analysis
pipeline (Pipeline A) decision output.

GRAIN: one row per (source_event_id, decision_id, source_ai_model) — the bronze
UNIQUE constraint. Thin clean: rename, surface video_id as the geography bridge,
build the stable extraction key. Geography is resolved downstream in the mart via
video_id -> event_youtube_with_jurisdiction.
*/

with source as (
    select * from {{ source('bronze', 'bronze_policy_decisions') }}
)

select
    -- stable dedup / surrogate basis
    source_event_id || '|' || decision_id || '|' || source_ai_model
                                            as extraction_key,

    source_event_id,
    video_id,
    decision_id,
    subject_id,

    -- narrative
    headline,
    outcome,

    -- reference graph / vote detail (JSONB pass-through)
    legislation_refs,
    vote_tally,

    -- provenance
    source_ai_model,
    extracted_at

from source
