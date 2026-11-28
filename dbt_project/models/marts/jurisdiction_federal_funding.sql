{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction'],
    indexes=[
      {'columns': ['jurisdiction_id', 'fiscal_year'], 'type': 'btree'},
      {'columns': ['assistance_listing_number', 'fiscal_year'], 'type': 'btree'}
    ]
  )
}}

/*
    public.jurisdiction_federal_funding (#1393): federal assistance dollars per matched
    jurisdiction x fiscal year x Assistance Listing Number, summed from federal_award.
    Only awards matched to a jurisdiction are included. Grain: jurisdiction_id x
    fiscal_year x assistance_listing_number (composite PK).
*/

select
    f.jurisdiction_id::text                  as jurisdiction_id,
    f.fiscal_year::integer                   as fiscal_year,
    f.assistance_listing_number::text        as assistance_listing_number,
    max(f.assistance_listing_title)::text    as assistance_listing_title,
    max(f.state_code)::text                  as state_code,
    max(f.state)::text                       as state,
    count(*)::integer                        as award_count,
    sum(f.total_obligation)::numeric         as total_obligation,
    sum(f.total_outlays)::numeric            as total_outlays,
    min(f.match_confidence)::numeric         as min_match_confidence,
    max(f.source_updated_at)::timestamp      as source_updated_at
from {{ ref('federal_award') }} f
where f.jurisdiction_id is not null
  and f.assistance_listing_number is not null
group by 1, 2, 3
