{{ config(materialized='view') }}

/*
    Staging: municipality (city/town) *_wikidata SEED rows.

    Replaces the Python SEED step in load_jurisdictions_wikidata.py
    (_seed_wikidata_table('city'): copy bronze_jurisdictions_municipalities ->
    bronze_jurisdictions_municipalities_wikidata, keyed on geoid). Pure
    TRANSFORMATION -> dbt.

    1 row per place GEOID (7-digit state_fips + place_fips). The Wikidata
    enrichment JOIN happens in int_wikidata__jurisdictions_enriched.
    Four-CTE template per dbt_project/CONVENTIONS.md.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_jurisdictions_municipalities') }}
),

renamed as (
    select
        replace(trim(geoid::text), '-', '')          as geoid,
        upper(nullif(trim(usps), ''))                as state_code,
        nullif(trim(ansicode::text), '')             as ansicode,
        nullif(trim(name), '')                       as place_name,
        nullif(trim(lsad), '')                       as lsad,
        nullif(trim(funcstat), '')                   as funcstat,
        aland_sqmi                                   as aland_sqmi,
        awater_sqmi                                  as awater_sqmi,
        intptlat::double precision                   as latitude,
        intptlong::double precision                  as longitude,
        ingestion_date                               as source_ingested_at
    from source
),

filtered as (
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
        'city'                                       as jurisdiction_type,
        ansicode,
        place_name                                   as jurisdiction_name,
        lsad,
        funcstat,
        aland_sqmi,
        awater_sqmi,
        latitude,
        longitude,
        source_ingested_at,
        current_timestamp                            as dbt_loaded_at
    from filtered
)

select * from final
