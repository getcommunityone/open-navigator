{{ config(materialized='table', tags=['intermediate', 'event-extraction', 'data_centers']) }}

/*
    Each AI-extracted decision's own government (#508). Grain: one row per event_decision_id
    (the latest extraction of it).

    The decision's meeting is the canonical event it was analysed from:
    event_decision.legacy_event_id -> civic_event.legacy_id, which carries jurisdiction_id.
    No name matching: a decision whose event has no jurisdiction_id gets no row, so the
    marts that need a government (decision_place_label, decision_nearby_data_center_site)
    show nothing for it rather than guess.
*/

with decisions as (
    select distinct on (event_decision_id)
        event_decision_id,
        legacy_event_id,
        state_code
    from {{ ref('event_decision') }}
    order by event_decision_id, extracted_at desc
)

select
    d.event_decision_id::text      as event_decision_id,
    j.jurisdiction_id::text        as jurisdiction_id,
    j.geoid::text                  as jurisdiction_geoid,
    j.name::text                   as jurisdiction_name,
    j.jurisdiction_type::text      as jurisdiction_type,
    j.state_code::text             as state_code
from decisions as d
inner join {{ source('civic_core', 'civic_event') }} as e on e.legacy_id = d.legacy_event_id
inner join {{ ref('jurisdictions') }} as j on j.jurisdiction_id = e.jurisdiction_id
