{{ config(materialized='view') }}

/*
    Staging: school-district *_wikidata SEED rows.

    Replaces the Python SEED step in load_jurisdictions_wikidata.py
    (_seed_wikidata_table('school_district'): copy
    bronze_jurisdictions_school_districts ->
    bronze_jurisdictions_school_districts_wikidata, keyed on geoid). Pure
    TRANSFORMATION -> dbt.

    1 row per district GEOID (7-digit). The Wikidata enrichment JOIN happens in
    int_wikidata__jurisdictions_enriched. Four-CTE template per
    dbt_project/CONVENTIONS.md.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_jurisdictions_school_districts') }}
),

renamed as (
    select
        replace(trim(geoid::text), '-', '')          as geoid,
        upper(nullif(trim(usps), ''))                as state_code,
        nullif(trim(name), '')                       as district_name,
        nullif(trim(lograde), '')                    as lograde,
        nullif(trim(higrade), '')                    as higrade,
        aland_sqmi::double precision                 as aland_sqmi,
        awater_sqmi::double precision                as awater_sqmi,
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
        'school_district'                            as jurisdiction_type,
        district_name                                as jurisdiction_name,
        lograde,
        higrade,
        aland_sqmi,
        awater_sqmi,
        latitude,
        longitude,
        source_ingested_at,
        current_timestamp                            as dbt_loaded_at
    from filtered
)

select * from final
