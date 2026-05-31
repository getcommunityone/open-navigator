{{ config(materialized='view') }}

/*
    Staging (MDM address conformance): parcel/property addresses from
    bronze.bronze_addresses, mapped onto the shared address contract that
    int_addresses__unioned unions. One row per source row (parcel record).

    NOTE: despite the column name, bronze_addresses.street_number is empty — the
    house number is embedded in street_line1 ("417 LIVINGSTON LN"), so it is
    split out here with a leading-digits regex. situs_full carries a noisy source
    prefix (e.g. "HWY 69 N, ..."), so the street is built from street_line1 (+ the
    unit in street_line2, which normalize_address strips anyway).

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, address pipeline).
    Four-CTE template: source → parsed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_addresses') }}
),

parsed as (
    select
        'bronze_addresses'                                     as source_system,
        id::text                                               as source_pk,
        'address'                                              as entity_type,

        situs_full                                             as raw_address,

        {{ normalize_address("concat_ws(' ', street_line1, street_line2)") }}
                                                               as address_norm,
        {{ address_match_key('street_line1', 'city', 'coalesce(state_abbr, state_code)', 'postal_code') }}
                                                               as address_match_key,

        nullif(substring(street_line1 from '^[[:space:]]*([0-9]+)'), '')
                                                               as street_number,
        {{ normalize_address("regexp_replace(coalesce(street_line1, ''), '^[[:space:]]*[0-9]+[[:space:]]*', '')") }}
                                                               as street_name,

        lower(trim(unaccent(city)))                            as city_norm,
        upper(left(trim(coalesce(state_abbr, state_code)), 2)) as state_code,
        {{ zip5('postal_code') }}                              as zip5,

        null::double precision                                 as lat,  -- not present in bronze_addresses
        null::double precision                                 as lon
    from source
),

filtered as (
    select *
    from parsed
    where street_name is not null
       or (city_norm is not null and state_code is not null)
),

final as (
    select * from filtered
)

select * from final
