{{ config(materialized='view') }}

/*
    Staging: county *_wikidata SEED rows.

    Replaces the Python SEED step in
    packages/scrapers/src/scrapers/wikidata/load_jurisdictions_wikidata.py
    (_seed_wikidata_table('county'): copy bronze_jurisdictions_counties ->
    bronze_jurisdictions_counties_wikidata, keyed on geoid). That copy is a pure
    TRANSFORMATION, so it lives here, not in Python.

    1 row per county GEOID. Light cleaning + type stabilization only — the
    Wikidata enrichment is JOINed on downstream in
    int_wikidata__jurisdictions_enriched. Four-CTE template per
    dbt_project/CONVENTIONS.md.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_jurisdictions_counties') }}
),

renamed as (
    select
        replace(trim(geoid::text), '-', '')          as geoid,
        upper(nullif(trim(usps), ''))                as state_code,
        nullif(trim(ansicode::text), '')             as ansicode,
        nullif(trim(name), '')                       as county_name,
        aland_sqmi                                   as aland_sqmi,
        awater_sqmi                                  as awater_sqmi,
        intptlat::double precision                   as latitude,
        intptlong::double precision                  as longitude,
        ingestion_date                               as source_ingested_at
    from source
),

filtered as (
    -- Business rule: a seed row must have its join key (geoid) and a state.
    select *
    from renamed
    where geoid is not null
      and length(geoid) > 0
      and state_code is not null
),

final as (
    select
        geoid,
        state_code,
        'county'                                     as jurisdiction_type,
        ansicode,
        county_name                                  as jurisdiction_name,
        aland_sqmi,
        awater_sqmi,
        latitude,
        longitude,
        source_ingested_at,
        current_timestamp                            as dbt_loaded_at
    from filtered
)

select * from final
