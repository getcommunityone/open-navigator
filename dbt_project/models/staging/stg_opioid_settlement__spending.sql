{{ config(materialized='view') }}

/*
    Staging: state opioid settlement spending lines (#1396). Today only Michigan
    (MDHHS dashboard workbook). Types pinned here: dollars numeric, fiscal_year
    integer (the 'FY24' label -> 2024), reported_as_of a real DATE. Blank stays NULL.
*/

select
    (state_code || '-' || source_row)::text                 as opioid_line_id,
    state_code::text                                        as state_code,
    (2000 + substring(fiscal_year_label from 3 for 2)::int)::integer as fiscal_year,
    status::text                                            as status,
    pillar::text                                            as pillar,
    strategy::text                                          as strategy,
    program::text                                           as program,
    recipient::text                                         as recipient,
    appropriation::text                                     as appropriation,
    nullif(spend_plan, '')::numeric(16,2)                   as spend_plan_dollars,
    nullif(expenditures, '')::numeric(16,2)                 as expenditure_dollars,
    nullif(remaining_plan, '')::numeric(16,2)               as remaining_plan_dollars,
    reported_as_of::date                                    as reported_as_of,
    source_url::text                                        as source_url,
    ingestion_date::timestamp                               as source_updated_at
from {{ source('bronze', 'bronze_opioid_settlement_spending') }}
