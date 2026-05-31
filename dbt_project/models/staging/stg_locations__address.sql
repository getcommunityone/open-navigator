{{ config(materialized='view') }}

/*
    Staging (MDM address conformance): facility addresses from bronze_locations,
    mapped onto the shared address contract.

    Reads bronze_locations directly: the landed table already exposes flat
    address columns (name, address, city, state, zip, lat/long), so the
    raw_record-JSONB staging model (stg_hifld__location) is not needed here — and
    is in fact stale against this table. The street is one combined string
    ("4380 BEACH STREET"), so the house number is split out the same way as the
    parcel source. One row per (source_dataset, source_id).

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, address pipeline).
    Four-CTE template: source → parsed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_locations') }}
),

parsed as (
    select
        'bronze_locations'                                     as source_system,
        concat_ws(':', source_dataset, source_id::text)        as source_pk,
        'address'                                              as entity_type,

        address                                                as raw_address,

        {{ normalize_address('address') }}                     as address_norm,
        {{ address_match_key('address', 'city', 'state', 'zip') }}
                                                               as address_match_key,

        nullif(substring(address from '^[[:space:]]*([0-9]+)'), '')
                                                               as street_number,
        {{ normalize_address("regexp_replace(coalesce(address, ''), '^[[:space:]]*[0-9]+[[:space:]]*', '')") }}
                                                               as street_name,

        lower(trim(unaccent(city)))                            as city_norm,
        upper(left(trim(state), 2))                            as state_code,
        {{ zip5('zip') }}                                      as zip5,

        latitude                                               as lat,
        longitude                                              as lon
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
