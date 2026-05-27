{{ config(materialized='view') }}

/*
    Staging: NACo County Explorer counties (1 row per (state_code, county_name)).

    Reads the RAW landing table bronze.bronze_jurisdictions_counties_naco, where
    ingestion.naco.counties now lands only the natural-key columns plus the full
    NACo county JSON object (raw_json). This model reproduces the derivation that
    used to live in the Python loader's parse_county():
      - multi-alias coalescing for name / county_name / countyName, etc.
      - the nested naco_get_county.county "inner" block (gated on .found)
      - digit-stripping of Population_Level (the _population_from_naco_display helper)
      - numeric extraction of Land_Area
      - website / county_seat fallbacks to the inner block
    All done in SQL against raw_json JSONB. Four-CTE template:
    source -> renamed -> filtered -> final. See dbt_project/CONVENTIONS.md.

    Note on coalescing semantics: the Python loader used `a or b or c`, which
    treats empty strings as falsy. nullif(<expr>, '') reproduces that so an empty
    string at an earlier alias falls through to the next, matching parse_county.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_jurisdictions_counties_naco') }}
),

renamed as (
    select
        -- The "inner" NACo profile block: raw_json.naco_get_county.county, but
        -- only when naco_get_county.found is truthy (mirrors _naco_profile_county_block).
        case
            when (raw_json -> 'naco_get_county' ->> 'found') in ('true', 't', '1')
                then raw_json -> 'naco_get_county' -> 'county'
            else null
        end                                                          as inner_block,
        raw_json
    from source
),

derived as (
    select
        -- naco_id: id OR naco_id (max 50)
        left(
            coalesce(
                nullif(raw_json ->> 'id', ''),
                nullif(raw_json ->> 'naco_id', '')
            ),
            50
        )                                                            as naco_id,

        -- county_name: name OR county_name OR countyName (max 255)
        left(
            coalesce(
                nullif(raw_json ->> 'name', ''),
                nullif(raw_json ->> 'county_name', ''),
                nullif(raw_json ->> 'countyName', '')
            ),
            255
        )                                                            as county_name,

        -- state_code: state OR state_code OR stateCode, uppercased (max 2)
        upper(
            left(
                coalesce(
                    nullif(raw_json ->> 'state', ''),
                    nullif(raw_json ->> 'state_code', ''),
                    nullif(raw_json ->> 'stateCode', '')
                ),
                2
            )
        )                                                            as state_code,

        -- fips_code: fips OR fips_code OR geoid (max 5)
        left(
            coalesce(
                nullif(raw_json ->> 'fips', ''),
                nullif(raw_json ->> 'fips_code', ''),
                nullif(raw_json ->> 'geoid', '')
            ),
            5
        )                                                            as fips_code,

        -- website: website OR url OR countyWebsite, fallback inner.County_Website (max 500)
        left(
            coalesce(
                nullif(raw_json ->> 'website', ''),
                nullif(raw_json ->> 'url', ''),
                nullif(raw_json ->> 'countyWebsite', ''),
                nullif(inner_block ->> 'County_Website', '')
            ),
            500
        )                                                            as website,

        -- phone: phone OR phoneNumber (max 50)
        left(
            coalesce(
                nullif(raw_json ->> 'phone', ''),
                nullif(raw_json ->> 'phoneNumber', '')
            ),
            50
        )                                                            as phone,

        -- email: email OR contactEmail (max 255)
        left(
            coalesce(
                nullif(raw_json ->> 'email', ''),
                nullif(raw_json ->> 'contactEmail', '')
            ),
            255
        )                                                            as email,

        -- population: population, else digit-stripped inner.Population_Level, else pop
        coalesce(
            (nullif(raw_json ->> 'population', ''))::numeric::int,
            nullif(regexp_replace(coalesce(inner_block ->> 'Population_Level', ''), '[^0-9]', '', 'g'), '')::int,
            (nullif(raw_json ->> 'pop', ''))::numeric::int
        )                                                            as population,

        -- area_sq_miles: area_sq_miles OR area OR areaSqMiles, else numeric of inner.Land_Area
        coalesce(
            (nullif(raw_json ->> 'area_sq_miles', ''))::numeric,
            (nullif(raw_json ->> 'area', ''))::numeric,
            (nullif(raw_json ->> 'areaSqMiles', ''))::numeric,
            nullif(regexp_replace(coalesce(inner_block ->> 'Land_Area', ''), '[^0-9.]', '', 'g'), '')::numeric
        )::numeric(12, 2)                                            as area_sq_miles,

        -- county_seat: county_seat OR countySeat OR seat, fallback inner.County_Seat (max 255)
        left(
            coalesce(
                nullif(raw_json ->> 'county_seat', ''),
                nullif(raw_json ->> 'countySeat', ''),
                nullif(raw_json ->> 'seat', ''),
                nullif(inner_block ->> 'County_Seat', '')
            ),
            255
        )                                                            as county_seat,

        ingestion_date                                               as source_ingested_at
    from renamed
),

filtered as (
    -- Business rule: parse_county dropped rows with no county_name or no state_code.
    select *
    from derived
    where county_name is not null
      and state_code is not null
),

final as (
    select
        state_code,
        county_name,
        naco_id,
        fips_code,
        website,
        phone,
        email,
        population,
        area_sq_miles,
        county_seat,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
