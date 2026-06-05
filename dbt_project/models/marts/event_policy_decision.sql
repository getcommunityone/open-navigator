{{
    config(
        materialized='table',
        unique_key='event_policy_decision_id',
        tags=['marts', 'policy-analysis', 'text', 'ai']
    )
}}

/*
public.event_policy_decision — policy decisions extracted by the TEXT/policy
transcript-analysis pipeline (Pipeline A), surfaced with resolved geography.

GRAIN: one row per (source_event_id, decision_id, source_ai_model).

SOURCE : stg_policy_decisions (bronze.bronze_policy_decisions)
BRIDGE : video_id -> public.event_youtube_with_jurisdiction (resolved jurisdiction
         + event_date). No clean public event PK exists for these videos
         (civic_event 'youtube|<id>' bridge has zero coverage), so we carry
         video_id + jurisdiction_id and FK the resolved jurisdiction instead.
TARGET : public.event_policy_decision (table).
*/

with decisions as (
    select * from {{ ref('stg_policy_decisions') }}
),

geo as (
    select
        video_id,
        jurisdiction_id,
        jurisdiction_name,
        state_code,
        state,
        event_date
    from {{ ref('event_youtube_with_jurisdiction') }}
)

select
    -- primary key
    md5(d.source_event_id || '|' || d.decision_id || '|' || d.source_ai_model)
                                            as event_policy_decision_id,
    d.extraction_key,

    -- source / bridge keys
    d.source_event_id,
    d.video_id,
    d.decision_id,
    d.subject_id,

    -- resolved geography (jurisdiction_id is the FK)
    g.jurisdiction_id,
    g.jurisdiction_name,
    g.state_code,
    g.state,
    g.event_date,

    -- decision content
    d.headline,
    d.outcome,
    d.legislation_refs,
    d.vote_tally,

    -- provenance
    d.source_ai_model,
    d.extracted_at

from decisions d
left join geo g on g.video_id = d.video_id
