{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction'],
    indexes=[{'columns': ['jurisdiction_id', 'fiscal_year'], 'type': 'btree'}]
  )
}}

/*
    opioid_settlement_spending (#1396): one row per reported spend-plan line of a state's
    opioid settlement funds. Grain: opioid_line_id (state-code + source row, the PK).
    Pilot: Michigan (MDHHS). These are state-agency lines, so jurisdiction_id is the state
    jurisdiction; payments to individual cities and counties are not in this source.
    expenditure_dollars is NULL where the state has not reported spending yet.
*/

select
    o.opioid_line_id::text            as opioid_line_id,
    j.jurisdiction_id::text           as jurisdiction_id,
    o.state_code::text                as state_code,
    j.state_name::text                as state,
    o.fiscal_year::integer            as fiscal_year,
    o.status::text                    as status,
    o.pillar::text                    as pillar,
    o.strategy::text                  as strategy,
    o.program::text                   as program,
    o.recipient::text                 as recipient,
    o.appropriation::text             as appropriation,
    o.spend_plan_dollars::numeric     as spend_plan_dollars,
    o.expenditure_dollars::numeric    as expenditure_dollars,
    o.remaining_plan_dollars::numeric as remaining_plan_dollars,
    o.reported_as_of::date            as reported_as_of,
    o.source_url::text                as source_url,
    o.source_updated_at::timestamp    as source_updated_at
from {{ ref('stg_opioid_settlement__spending') }} o
left join {{ ref('jurisdictions') }} j
  on j.jurisdiction_type = 'state' and j.state_code = o.state_code
