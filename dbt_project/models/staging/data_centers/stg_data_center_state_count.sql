{{ config(materialized='view', tags=['staging', 'data_centers']) }}

/*
    State data center figures from github.com/greencalculus/us-data-centers-by-state (#958),
    from bronze_data_center_state_count_greencalculus
    (python -m ingestion.data_centers.facility_inventories --source greencalculus).
    Grain: one row per figure (its own `id`): one metric for one state from one publisher.

    The repo is CC BY 4.0, but each figure belongs to its original publisher (source,
    source_title, source_url), several of whom (Pew Research Center, Data Center Map) limit
    republishing. So this stays in staging and is not served: see
    web_docs/docs/development/data-center-source-review.md.
*/

select
    record_id::text                                                             as state_count_id,
    upper(nullif(record->>'state', ''))::text                                   as state_code,
    nullif(record->>'geography', '')::text                                      as geography,
    nullif(record->>'metric', '')::text                                         as metric,
    (case when record->>'value' ~ '^-?\d+(\.\d+)?$' then (record->>'value')::numeric end) as value,
    nullif(record->>'unit', '')::text                                           as unit,
    nullif(record->>'status', '')::text                                         as figure_status,
    (case when record->>'as_of' ~ '^\d{4}-\d{2}-\d{2}$' then (record->>'as_of')::date end) as as_of_on,
    nullif(record->>'source', '')::text                                         as publisher,
    nullif(record->>'source_title', '')::text                                   as source_title,
    nullif(record->>'source_url', '')::text                                     as source_url,
    nullif(record->>'notes', '')::text                                          as notes,
    attribution::text                                                           as attribution,
    last_seen_at::date                                                          as last_seen_on
from {{ source('bronze', 'bronze_data_center_state_count_greencalculus') }}
