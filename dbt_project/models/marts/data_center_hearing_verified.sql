{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    The served slice of data_center_hearing (#955): verified leads only, so an unverified research
    lead is never published to public / Neon. Grain: one row per verified hearing.
    Design: web_docs/docs/development/data-center-hearings.md
*/

select
    data_center_hearing_id::text    as data_center_hearing_id,
    jurisdiction_id::text           as jurisdiction_id,
    meeting_date::date              as meeting_date,
    jurisdiction_name::text         as jurisdiction_name,
    state_code::text                as state_code,
    state::text                     as state,
    body_name::text                 as body_name,
    topic::text                     as topic,
    source_url::text                as source_url,
    source_name::text               as source_name,
    evidence::text                  as evidence,
    tentative::boolean              as tentative,
    checked_at::timestamptz         as checked_at
from {{ ref('data_center_hearing') }}
where status = 'verified'
