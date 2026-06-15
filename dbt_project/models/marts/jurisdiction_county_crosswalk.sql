{{
  config(
    materialized='table',
    tags=['gold', 'jurisdictions', 'api'],
    unique_key='geoid',
    indexes=[
      {'columns': ['geoid'], 'unique': True},
      {'columns': ['county_fips'], 'type': 'btree'},
      {'columns': ['state_code'], 'type': 'btree'}
    ]
  )
}}

/*
gold.jurisdiction_county_crosswalk -> published to public.jurisdiction_county_crosswalk

City/town -> containing county crosswalk consumed by the search county-broaden
filter (resolve_county_crosswalk in api/routes/search_postgres.py): given a
5-digit county_fips it returns every city/town NAME in that county plus the
county's own name, so the geo-scoped search legs can widen from one city to the
whole surrounding county.

Grain: one row per city/town geoid (PK = geoid). geoid is unique here because
the join is filtered to jurisdiction_type IN ('city','town') and a place geoid
is unique within that type.

Lineage (reproduces, in dbt, the former hand-created live view introduced by
PR #176):
  - city + county name/type/geoid come from {{ ref('jurisdictions') }}.
  - the city -> county_fips mapping comes from the spatial enrichment source
    bronze.bronze_jurisdictions_county_fips_enriched (point-in-polygon county
    resolution), declared as source('bronze', ...).

county_name is LEFT-joined: a city whose resolved county_fips has no matching
county row in jurisdictions keeps county_fips with county_name NULL rather than
being dropped.
*/

with city_county_fips as (
    select
        geoid,
        county_fips_code
    from {{ source('bronze', 'bronze_jurisdictions_county_fips_enriched') }}
),

cities as (
    select
        geoid,
        name,
        state_code,
        state_name
    from {{ ref('jurisdictions') }}
    where jurisdiction_type in ('city', 'town')
),

counties as (
    select
        geoid,
        name as county_name
    from {{ ref('jurisdictions') }}
    where jurisdiction_type = 'county'
)

select
    j.geoid          as geoid,
    j.name           as name,
    j.state_code     as state_code,
    j.state_name     as state,
    e.county_fips_code as county_fips,
    c.county_name    as county_name
from city_county_fips e
join cities j
    on j.geoid = e.geoid
left join counties c
    on c.geoid = e.county_fips_code
