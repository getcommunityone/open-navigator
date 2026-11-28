{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction'],
    indexes=[{'columns': ['fiscal_year'], 'type': 'btree'}]
  )
}}

/*
    cdbg_allocation (#1394): HUD CDBG grant dollars per matched jurisdiction x federal fiscal
    year, taken from USAspending awards under assistance listings 14.218 (Entitlement) and
    14.228 (State / Non-entitlement) already in jurisdiction_federal_funding. These are the
    awards' current total obligations, which is what USAspending reports; HUD's own
    allocation notices are not published in a form we can fetch. Grain: jurisdiction_id x
    fiscal_year (composite PK).
*/

select
    jurisdiction_id::text                  as jurisdiction_id,
    fiscal_year::integer                   as fiscal_year,
    max(state_code)::text                  as state_code,
    max(state)::text                       as state,
    sum(award_count)::integer              as award_count,
    sum(total_obligation)::numeric         as total_obligation,
    max(source_updated_at)::timestamp      as source_updated_at
from {{ ref('jurisdiction_federal_funding') }}
where assistance_listing_number in ('14.218', '14.228')
group by 1, 2
