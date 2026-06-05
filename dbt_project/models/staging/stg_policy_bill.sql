{{
    config(
        materialized='view'
    )
}}

/*
Staging for bronze.bronze_bills — the TEXT/policy transcript-analysis pipeline
(Pipeline A) legislation/bill output. NOT bronze_bills_from_ai.

GRAIN: one row per source_event_id_leg_id (the bronze PK, already unique). Thin
clean: rename, surface video_id as the geography bridge, cast the raw VARCHAR(4)
`year` to a nullable integer per the project's calendar-year rule (integer storage
in staging+; bronze keeps source-native varchar for raw fidelity). The bronze
`jurisdiction` text column is DIRTY and intentionally dropped — geography is
resolved downstream in the mart via video_id -> event_youtube_with_jurisdiction.
*/

with source as (
    select * from {{ source('bronze', 'bronze_bills') }}
)

select
    -- primary key (already unique in bronze)
    source_event_id_leg_id,

    source_event_id,
    video_id,

    -- bill identity
    leg_id,
    leg_type,
    official_number,
    title,

    -- calendar year: raw varchar(4) -> nullable integer (storage rule).
    -- nullif guards blank strings; trailing cast is null-safe.
    nullif(trim(year), '')::integer         as year,

    status,
    relevance,
    url,
    agenda_labels,

    -- provenance
    source_ai_model,
    extracted_at

from source
