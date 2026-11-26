/*
    Public records about data centers from the Public Evidence Project (#958): permits,
    dockets, filings, incentives and moratoriums. Grain: one row per record.

    Every row links the government document it rests on (source_url) and the record's page on
    publicevidence.org (record_url), with the CC BY 4.0 credit (attribution). summary and
    boundary are the project's own words, kept as written. facility_id is the project's own
    facility id; the project shares no id with Epoch or the US Data Center Registry, so records
    are not linked to data_center_site (a name-and-place match would be a guess).
    record_date_text and verified_on_text stay as published ("Opened May 27, 2026").
*/

select
    p.public_record_id::text                          as data_center_public_record_id,
    p.facility_id::text                               as facility_id,
    p.state_code::text                                as state_code,
    (case when p.state_code ~ '^[A-Z]{2}$' then {{ state_code_to_name('p.state_code') }} end)::text as state,
    p.locality::text                                  as locality,
    p.category::text                                  as category,
    p.category_label::text                            as category_label,
    p.title::text                                     as title,
    p.record_status::text                             as record_status,
    p.record_date_text::text                          as record_date_text,
    p.summary::text                                   as summary,
    p.boundary::text                                  as boundary,
    p.source_label::text                              as source_label,
    p.source_publisher::text                          as source_publisher,
    p.source_url::text                                as source_url,
    p.verified_on_text::text                          as verified_on_text,
    p.latitude::double precision                      as latitude,
    p.longitude::double precision                     as longitude,
    p.record_url::text                                as record_url,
    'Public Evidence Project'::text                   as source_name,
    'CC BY 4.0'::text                                 as license,
    p.attribution::text                               as attribution,
    p.last_seen_on::date                              as last_seen_on
from {{ ref('stg_data_center_public_record') }} as p
