{{ config(materialized='table') }}

/*
    Intermediate (MDM): the conformed address pool — every source address mapped
    onto one schema and stacked. This is the table Splink reads to build the
    address clusters (see web_docs/docs/dbt/entity-resolution-mdm.md, Layer 2→3).

    Grain: one row per source address occurrence (NOT deduplicated — clustering
    happens downstream in Splink). The shared contract is fixed by the column
    list below; every stg_<source>__address model must emit it identically.

    Address sources (strongest geo signal first):
      - stg_parcels__address    (bronze_addresses, ~598k parcel records)
      - stg_locations__address  (bronze_locations / HIFLD facilities)
      - stg_places__address     (bronze_places_from_ai, AI-extracted, lowest trust)

    TODO: add stg_nccs__address as it conforms.
*/

with unioned as (
    select * from {{ ref('stg_parcels__address') }}
    union all
    select * from {{ ref('stg_locations__address') }}
    union all
    select * from {{ ref('stg_places__address') }}
)

select
    md5(source_system || '|' || source_pk)  as address_uid,
    source_system,
    source_pk,
    entity_type,
    raw_address,
    address_norm,
    address_match_key,
    street_number,
    street_name,
    city_norm,
    state_code,
    zip5,
    lat,
    lon
from unioned
