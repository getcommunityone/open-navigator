{{ config(materialized='view') }}

/*
    Staging: Census ASPEP governments (#1395). One row per government x survey year.
    Types are pinned here: survey_year and population integer, codes text.
*/

select
    survey_year::integer                                         as survey_year,
    unit_id::text                                                as unit_id,
    state_code::text                                             as state_fips,  -- ASPEP's state code is the numeric FIPS
    fips_state::text                                             as fips_state,
    case unit_type_code
        when '0' then 'state' when '1' then 'county' when '2' then 'municipality'
        when '3' then 'township' when '4' then 'special_district'
        when '5' then 'school_district' end                      as unit_type,
    government_name::text                                        as government_name,
    county_name::text                                            as county_name,
    (fips_state || fips_county)::text                            as county_fips,
    nullif(trim(population_or_enrollment), '')::bigint           as population_or_enrollment,
    ingestion_date::timestamp                                    as source_updated_at
from {{ source('bronze', 'bronze_aspep_unit') }}
