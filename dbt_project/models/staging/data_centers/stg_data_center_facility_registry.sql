{{ config(materialized='view', tags=['staging', 'data_centers']) }}

/*
    US Data Center Registry facilities (#958), from bronze_data_center_facility_registry
    (python -m ingestion.data_centers.facility_inventories --source registry).
    Grain: one row per registry record (its own `id`).

    Publisher: SueDataCenters.org (Theory Road LLC), base data from Compute Atlas. CC BY 4.0:
    credit Compute Atlas for the base and SueDataCenters.org for joins, corrections and
    additions (`attribution`). The registry gives no primary source URL per record (only a
    source_count), so these are registry records, credited as such, not verified facts.
    `profile_url` is the record's own page on the registry.

    Values are typed with guarded casts: a value that isn't a clean number or date is null,
    never guessed. is_listed: the newest load still lists the record (a record the registry
    drops keeps its last_seen_on and reads no_longer_listed downstream).
*/

with raw as (
    select * from {{ source('bronze', 'bronze_data_center_facility_registry') }}
),

newest as (
    select max(last_seen_at) as last_load_at from raw
)

select
    r.record_id::text                                                                       as registry_id,
    nullif(r.record->>'name', '')::text                                                     as facility_name,
    nullif(r.record->>'operator', '')::text                                                 as operator,
    nullif(r.record->>'company', '')::text                                                  as company,
    nullif(r.record->>'facility_type', '')::text                                            as facility_type,
    nullif(lower(r.record->>'status'), '')::text                                            as registry_status,
    nullif(r.record->>'community_reception', '')::text                                      as community_reception,
    nullif(r.record->>'source_confidence', '')::text                                        as source_confidence,
    nullif(r.record->>'city', '')::text                                                     as city,
    nullif(r.record->>'county', '')::text                                                   as county,
    upper(nullif(r.record->>'state', ''))::text                                             as state_code,
    (case when r.record->>'latitude' ~ '^-?\d+(\.\d+)?$' then (r.record->>'latitude')::double precision end) as latitude,
    (case when r.record->>'longitude' ~ '^-?\d+(\.\d+)?$' then (r.record->>'longitude')::double precision end) as longitude,
    nullif(r.record->>'coordinate_precision', '')::text                                     as coordinate_precision,
    (case when r.record->>'capacity_mw_planned' ~ '^\d+(\.\d+)?$' then (r.record->>'capacity_mw_planned')::double precision end) as capacity_mw_planned,
    (case when r.record->>'capacity_mw_operational' ~ '^\d+(\.\d+)?$' then (r.record->>'capacity_mw_operational')::double precision end) as capacity_mw_operational,
    (case when r.record->>'announced_date' ~ '^\d{4}-\d{2}-\d{2}$' then (r.record->>'announced_date')::date end) as announced_on,
    (case when r.record->>'record_updated' ~ '^\d{4}-\d{2}-\d{2}$' then (r.record->>'record_updated')::date end) as record_updated_on,
    (case when r.record->>'source_count' ~ '^\d+$' then (r.record->>'source_count')::int end) as source_count,
    nullif(r.record->>'record_origin', '')::text                                            as record_origin,
    nullif(r.record->>'profile_url', '')::text                                              as profile_url,
    r.feed_url::text                                                                        as feed_url,
    r.attribution::text                                                                     as attribution,
    r.first_seen_at::date                                                                   as first_seen_on,
    r.last_seen_at::date                                                                    as last_seen_on,
    (r.last_seen_at = n.last_load_at)::boolean                                              as is_listed
from raw as r
cross join newest as n
