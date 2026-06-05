{{
    config(
        materialized='table',
        unique_key='source_event_id_leg_id',
        tags=['marts', 'policy-analysis', 'text', 'ai']
    )
}}

/*
public.event_policy_bill — legislation/bills extracted by the TEXT/policy
transcript-analysis pipeline (Pipeline A), surfaced with resolved geography.

GRAIN: one row per source_event_id_leg_id (the bronze PK, already unique).

SOURCE : stg_policy_bill (bronze.bronze_bills — NOT bronze_bills_from_ai)
BRIDGE : video_id -> public.event_youtube_with_jurisdiction (resolved
         jurisdiction). The bronze `jurisdiction` text column is DIRTY and is
         dropped; geography comes from the resolved view. No clean public event
         PK exists for these videos, so we carry video_id + jurisdiction_id and
         FK the resolved jurisdiction instead.
TARGET : public.event_policy_bill (table). `year` is a nullable integer.
*/

with bills as (
    select * from {{ ref('stg_policy_bill') }}
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
    -- primary key (already unique in bronze)
    b.source_event_id_leg_id,

    -- source / bridge keys
    b.source_event_id,
    b.video_id,

    -- resolved geography (jurisdiction_id is the FK)
    g.jurisdiction_id,
    g.jurisdiction_name,
    g.state_code,
    g.state,
    g.event_date,

    -- bill identity & content
    b.leg_id,
    b.leg_type,
    b.official_number,
    b.title,
    b.year,
    b.status,
    b.relevance,
    b.url,
    b.agenda_labels,

    -- provenance
    b.source_ai_model,
    b.extracted_at

from bills b
left join geo g on g.video_id = b.video_id
