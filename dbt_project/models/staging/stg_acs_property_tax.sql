{{
  config(
    materialized='view',
    tags=['staging', 'census', 'property_tax']
  )
}}

/*
staging.stg_acs_property_tax — cleaned ACS property-tax inputs per geography,
from bronze.bronze_acs_property_tax (Census ACS 5-year B25103 + B25077, landed
by ingestion.census.property_tax).

GRAIN: one row per (geography_type, geoid, acs_vintage_year). geography_type is
'place' (city/town) or 'county'.

WHAT THIS DOES
  - Casts the bare calendar year to INTEGER (CLAUDE.md: years are integers in
    storage from the staging layer on; string only at the JSON/wire boundary).
  - Keeps the two dollar amounts as integers; the bronze loader already
    coerced ACS jumbo-negative suppression sentinels to NULL (honest missing).
  - The effective RATE itself is computed downstream in the mart, not here.
*/

select
    geography_type,
    geoid,
    lpad(trim(state_fips), 2, '0')                  as state_fips,
    name,
    acs_vintage_year::integer                       as acs_vintage_year,
    median_real_estate_taxes_paid::integer          as median_real_estate_taxes_paid,
    median_home_value::integer                      as median_home_value,
    loaded_at
from {{ source('bronze', 'bronze_acs_property_tax') }}
