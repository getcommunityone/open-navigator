{{ config(materialized='view', tags=['staging', 'data_centers']) }}

/*
    Public Evidence Project records about data centers (#958), from
    bronze_data_center_facility_public_evidence
    (python -m ingestion.data_centers.facility_inventories --source public_evidence).
    Grain: one row per record (its own `id`): a permit, a docket, a filing, an incentive.

    Each record links the government document it rests on (source_url, source_label) and its
    page on publicevidence.org. CC BY 4.0: credit the Public Evidence Project, with Compute
    Atlas upstream (`attribution`). facility_id, when present, is the Public Evidence Project's
    own facility id ("va-fairfax-word-of-grace", "us-epa-frs-…"); it is not a US Data Center
    Registry id, so it doesn't link a record to a data_center_site. summary and boundary are
    the project's own words.
*/

select
    record_id::text                                                 as public_record_id,
    nullif(record->>'facility_id', '')::text                        as facility_id,
    upper(nullif(record->>'state_code', ''))::text                  as state_code,
    nullif(record->>'locality', '')::text                           as locality,
    nullif(record->>'category', '')::text                           as category,
    nullif(record->>'category_label', '')::text                     as category_label,
    nullif(record->>'title', '')::text                              as title,
    nullif(record->>'status', '')::text                             as record_status,
    nullif(record->>'record_date', '')::text                        as record_date_text,
    nullif(record->>'summary', '')::text                            as summary,
    nullif(record->>'boundary', '')::text                           as boundary,
    nullif(record->>'source_label', '')::text                       as source_label,
    nullif(record->>'source_publisher', '')::text                   as source_publisher,
    nullif(record->>'source_url', '')::text                         as source_url,
    nullif(record->>'verified_on', '')::text                        as verified_on_text,
    (case when record->>'latitude' ~ '^-?\d+(\.\d+)?$' then (record->>'latitude')::double precision end)   as latitude,
    (case when record->>'longitude' ~ '^-?\d+(\.\d+)?$' then (record->>'longitude')::double precision end) as longitude,
    nullif(record->>'public_evidence_record_url', '')::text         as record_url,
    attribution::text                                               as attribution,
    first_seen_at::date                                             as first_seen_on,
    last_seen_at::date                                              as last_seen_on
from {{ source('bronze', 'bronze_data_center_facility_public_evidence') }}
