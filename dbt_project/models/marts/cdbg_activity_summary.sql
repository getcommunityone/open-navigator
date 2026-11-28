{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction'],
    indexes=[{'columns': ['activity_group', 'fiscal_year'], 'type': 'btree'}]
  )
}}

/*
    cdbg_activity_summary (#1394): the served slice of cdbg_activity. Completed activities
    of federal fiscal year 2019 onward, matched to a jurisdiction, summed per jurisdiction x
    fiscal year x HUD activity group. Grain: jurisdiction_id x fiscal_year x activity_group
    (composite PK). Feeds the cdbg_public_services_share benchmark.
*/

select
    jurisdiction_id::text                  as jurisdiction_id,
    fiscal_year::integer                   as fiscal_year,
    activity_group::text                   as activity_group,
    max(state_code)::text                  as state_code,
    max(state)::text                       as state,
    count(*)::integer                      as activity_count,
    sum(funding_amount)::numeric           as funding_amount,
    max(source_updated_at)::timestamp      as source_updated_at
from {{ ref('cdbg_activity') }}
where jurisdiction_id is not null
  and fiscal_year >= 2019
  and activity_group is not null
  and funding_amount is not null
group by 1, 2, 3
