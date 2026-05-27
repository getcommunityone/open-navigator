{{ config(materialized='view') }}

/*
    Staging: HIFLD infrastructure locations (1 row per (source_dataset, source_id)).

    Reads the RAW table landed by ingestion.hifld.locations, which preserves every
    source column verbatim in `raw_record` JSONB. The two transformations that used
    to live in the Python loader are done here in SQL (moved per
    dbt_project/CONVENTIONS.md):

      - FIELD_MAP column-name normalization: HIFLD datasets use inconsistent column
        names (NAME / FACNAME / SCHOOL_NAME, ADDRESS / STREET / LOCATION, LAT / Y,
        LON / LONG / X, …). They are coalesced into canonical columns below.
      - organization_type classification (was map_organization_type): derived from
        source_dataset, with the raw TYPE field used for law enforcement.

    Four-CTE template: source → renamed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_locations') }}
),

renamed as (
    select
        source_id                                              as source_id,
        source_dataset                                         as source_dataset,

        -- FIELD_MAP: name <- NAME / FACNAME / FACILITY_NAME / SCHOOL_NAME / HOSPITAL_NAME
        left(nullif(trim(coalesce(
            raw_record ->> 'NAME',
            raw_record ->> 'FACNAME',
            raw_record ->> 'FACILITY_NAME',
            raw_record ->> 'SCHOOL_NAME',
            raw_record ->> 'HOSPITAL_NAME'
        )), ''), 500)                                          as name,

        -- FIELD_MAP: address <- ADDRESS / STREET / ADDR / LOCATION
        left(nullif(trim(coalesce(
            raw_record ->> 'ADDRESS',
            raw_record ->> 'STREET',
            raw_record ->> 'ADDR',
            raw_record ->> 'LOCATION'
        )), ''), 500)                                          as address,

        -- FIELD_MAP: city <- CITY / CITYNAME
        left(nullif(trim(coalesce(
            raw_record ->> 'CITY',
            raw_record ->> 'CITYNAME'
        )), ''), 200)                                          as city,

        -- FIELD_MAP: state <- STATE / ST / STATE_ABBR (uppercased, 2 chars)
        left(upper(nullif(trim(coalesce(
            raw_record ->> 'STATE',
            raw_record ->> 'ST',
            raw_record ->> 'STATE_ABBR'
        )), '')), 2)                                           as state,

        -- FIELD_MAP: zip <- ZIP / ZIPCODE / ZIP_CODE
        left(nullif(trim(coalesce(
            raw_record ->> 'ZIP',
            raw_record ->> 'ZIPCODE',
            raw_record ->> 'ZIP_CODE'
        )), ''), 10)                                           as zip,

        -- FIELD_MAP: county <- COUNTY / COUNTYNAME
        left(nullif(trim(coalesce(
            raw_record ->> 'COUNTY',
            raw_record ->> 'COUNTYNAME'
        )), ''), 200)                                          as county,

        -- FIELD_MAP: latitude <- LATITUDE / LAT / Y
        nullif(trim(coalesce(
            raw_record ->> 'LATITUDE',
            raw_record ->> 'LAT',
            raw_record ->> 'Y'
        )), '')::double precision                              as latitude,

        -- FIELD_MAP: longitude <- LONGITUDE / LON / LONG / X
        nullif(trim(coalesce(
            raw_record ->> 'LONGITUDE',
            raw_record ->> 'LON',
            raw_record ->> 'LONG',
            raw_record ->> 'X'
        )), '')::double precision                              as longitude,

        -- FIELD_MAP: telephone <- TELEPHONE / PHONE / TEL
        left(nullif(trim(coalesce(
            raw_record ->> 'TELEPHONE',
            raw_record ->> 'PHONE',
            raw_record ->> 'TEL'
        )), ''), 50)                                           as telephone,

        -- FIELD_MAP: website <- WEBSITE / URL / WEB
        left(nullif(trim(coalesce(
            raw_record ->> 'WEBSITE',
            raw_record ->> 'URL',
            raw_record ->> 'WEB'
        )), ''), 500)                                          as website,

        -- organization_type classification (ported from map_organization_type):
        -- dataset-name substring dispatch; law enforcement uses raw TYPE.
        case
            when lower(source_dataset) like '%law_enforcement%'
              or lower(source_dataset) like '%police%'
                then replace(
                    lower(coalesce(nullif(trim(raw_record ->> 'TYPE'), ''), 'law_enforcement')),
                    ' ', '_'
                )
            when lower(source_dataset) like '%worship%'
              or lower(source_dataset) like '%church%'
              or lower(source_dataset) like '%religious%'
                then 'place_of_worship'
            when lower(source_dataset) like '%school%'
              or lower(source_dataset) like '%education%'
                then 'school'
            when lower(source_dataset) like '%hospital%'
              or lower(source_dataset) like '%healthcare%'
              or lower(source_dataset) like '%medical%'
                then 'hospital'
            when lower(source_dataset) like '%fire%'
                then 'fire_station'
            when lower(source_dataset) like '%government%'
              or lower(source_dataset) like '%courthouse%'
              or lower(source_dataset) like '%city_hall%'
                then 'government_building'
            else 'other'
        end                                                    as organization_type,

        loaded_at                                              as source_ingested_at
    from source
),

filtered as (
    -- Business rule: drop rows with no source_dataset (the natural-key component
    -- and the organization_type driver).
    select *
    from renamed
    where source_dataset is not null
      and length(source_dataset) > 0
),

final as (
    select
        source_id,
        source_dataset,
        organization_type,
        name,
        address,
        city,
        state,
        zip,
        county,
        latitude,
        longitude,
        telephone,
        website,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
