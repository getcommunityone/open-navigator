{{
  config(
    materialized='table',
    post_hook=[
      "CREATE INDEX IF NOT EXISTS grant_opportunity_status_idx ON {{ this }} (opp_status)",
      "CREATE INDEX IF NOT EXISTS grant_opportunity_close_date_idx ON {{ this }} (close_date)",
      "CREATE INDEX IF NOT EXISTS grant_opportunity_agency_idx ON {{ this }} (agency_code)"
    ]
  )
}}

/*
    Mart: public.grant_opportunity — one row per Grants.gov federal funding
    OPPORTUNITY (prospective grants open / forecasted for application). Sourced
    from stg_grants_gov__opportunity.

    DISTINCT ENTITY from public.grant (the 990 Schedule I mart): `grant` is
    historical nonprofit grantmaking ("who got funded"); `grant_opportunity` is
    open federal funding ("what's available now"). They are surfaced as separate
    /search result types ('grant' vs 'opportunity') and must not be conflated.

    Keying: opportunity_id is the natural PK (the Grants.gov opportunity id). No
    foreign keys — an opportunity has no resolved org/jurisdiction relationship
    yet (a future enrichment could bridge agency_code -> a gov org master).

    external_url is the canonical public Grants.gov detail page, so /search can
    link straight out without an internal detail route.
*/

with

opportunities as (
    select * from {{ ref('stg_grants_gov__opportunity') }}
)

select
    cast(opportunity_id as text)        as opportunity_id,
    cast(opportunity_number as text)    as opportunity_number,
    cast(title as text)                 as title,
    cast(agency_code as text)           as agency_code,
    cast(agency_name as text)           as agency_name,
    open_date,
    close_date,
    cast(opp_status as text)            as opp_status,
    cast(doc_type as text)              as doc_type,
    cast(aln as text)                   as aln,
    is_open,
    'https://www.grants.gov/search-results-detail/' || opportunity_id
                                        as external_url,
    current_timestamp                   as dbt_loaded_at
from opportunities
