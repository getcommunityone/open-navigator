{{ config(materialized='table', tags=['marts', 'event-extraction', 'data_centers', 'serving']) }}

/*
    Tracked data center sites near a data center decision's government (#508). Grain: one
    row per (event_decision_id, data_center_site_id).

    Scope: decisions whose headline or decision_statement says "data center"
    (data_center_regex). The decision's own government (int_event_decision__jurisdiction)
    is matched to the governments around each Epoch AI site
    (int_data_center_site__jurisdiction, #445). This says only that the site is near the
    government that made the decision; it does NOT say the decision is about that site, and
    the page labels it "Nearby tracked site".
*/

{%- set dc_regex = data_center_regex() %}

with decisions as (
    select event_decision_id
    from (
        select distinct on (event_decision_id) event_decision_id, headline, decision_statement
        from {{ ref('event_decision') }}
        order by event_decision_id, extracted_at desc
    ) as d
    where coalesce(headline, '') || ' ' || coalesce(decision_statement, '') ~* '{{ dc_regex }}'
)

select
    md5(d.event_decision_id || '|' || l.data_center_site_id)::text as decision_nearby_data_center_site_id,
    d.event_decision_id::text                                      as event_decision_id,
    l.data_center_site_id::text                                    as data_center_site_id,
    j.jurisdiction_id::text                                        as jurisdiction_id,
    j.state_code::text                                             as state_code,
    l.link_basis::text                                             as link_basis
from decisions as d
inner join {{ ref('int_event_decision__jurisdiction') }} as j on j.event_decision_id = d.event_decision_id
inner join {{ ref('int_data_center_site__jurisdiction') }} as l on l.jurisdiction_id = j.jurisdiction_id
