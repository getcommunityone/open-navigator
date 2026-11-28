{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction'],
    unique_key='award_id',
    indexes=[
      {'columns': ['jurisdiction_id', 'fiscal_year'], 'type': 'btree'},
      {'columns': ['assistance_listing_number'], 'type': 'btree'},
      {'columns': ['state_code', 'fiscal_year'], 'type': 'btree'}
    ]
  )
}}

/*
    public.federal_award (#1393): one row per USAspending assistance award (grants and
    cooperative agreements, types 02-05) to a local-government recipient, FY2019 onward.
    jurisdiction_id links to jurisdictions by normalized name + state + kind with a
    match_confidence (0.95 unique / 0.60 ambiguous); unmatched recipients keep NULL.
    total_obligation is the award's current total, not a single transaction.
    Source: USAspending.gov (public domain).
*/

with a as (
    select * from {{ ref('stg_usaspending__award') }}
    where fiscal_year >= 2019
),

m as (
    select * from {{ ref('int_usaspending_recipient__jurisdiction_match') }}
),

st as (
    select state_code, name as state from {{ ref('jurisdictions') }} where jurisdiction_type = 'state'
)

select
    a.award_id::text                                   as award_id,
    a.award_number::text                               as award_number,
    a.recipient_name::text                             as recipient_name,
    a.recipient_uei::text                              as recipient_uei,
    a.recipient_type::text                             as recipient_type,
    a.assistance_listing_number::text                  as assistance_listing_number,
    a.assistance_listing_title::text                   as assistance_listing_title,
    a.awarding_agency::text                            as awarding_agency,
    a.funding_agency::text                             as funding_agency,
    a.total_obligation::numeric                        as total_obligation,
    a.total_outlays::numeric                           as total_outlays,
    a.period_start::date                               as period_start,
    a.period_end::date                                 as period_end,
    coalesce(a.recipient_state_code, a.pop_state_code)::text as state_code,
    st.state::text                                     as state,
    a.pop_state_code::text                             as pop_state_code,
    a.pop_state::text                                  as pop_state,
    a.pop_county::text                                 as pop_county,
    a.pop_city::text                                   as pop_city,
    a.description::text                                as description,
    m.jurisdiction_id::text                            as jurisdiction_id,
    m.match_confidence::numeric                        as match_confidence,
    a.fiscal_year::integer                             as fiscal_year,
    a.source_updated_at::timestamp                     as source_updated_at,
    a.ingested_at::timestamp                           as ingested_at
from a
left join m
  on m.recipient_name_u = upper(a.recipient_name)
 and m.state_code is not distinct from coalesce(a.recipient_state_code, a.pop_state_code)
left join st on st.state_code = coalesce(a.recipient_state_code, a.pop_state_code)
