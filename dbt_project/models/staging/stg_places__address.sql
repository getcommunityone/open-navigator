{{ config(materialized='view') }}

/*
    Staging (MDM address conformance): AI-extracted places from
    bronze_places_from_ai (the RAW source behind the event_place mart — read here
    at bronze, NOT from the mart, to keep the medallion DAG one-directional).

    These are the lowest-trust address source (LLM-extracted, no strong keys);
    rank them last in survivorship downstream. They DO carry geocoded lat/long,
    which is a strong corroborating signal. No postal code in this source.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, address pipeline).
    Four-CTE template: source → parsed → filtered → final.
*/

with

source as (
    select * from {{ ref('bronze_places_from_ai') }}
),

parsed as (
    select
        'bronze_places_from_ai'                                as source_system,
        source_event_id_place_id                               as source_pk,
        'address'                                              as entity_type,

        coalesce(normalized_address, street_address, raw_text) as raw_address,

        {{ normalize_address('street_address') }}              as address_norm,
        {{ address_match_key('street_address', 'city', 'state_code', 'null') }}
                                                               as address_match_key,

        nullif(substring(street_address from '^[[:space:]]*([0-9]+)'), '')
                                                               as street_number,
        {{ normalize_address("regexp_replace(coalesce(street_address, ''), '^[[:space:]]*[0-9]+[[:space:]]*', '')") }}
                                                               as street_name,

        lower(trim(unaccent(city)))                            as city_norm,
        upper(left(trim(state_code), 2))                       as state_code,
        null::text                                             as zip5,  -- no postal code in source

        latitude                                               as lat,
        longitude                                              as lon
    from source
),

filtered as (
    -- AI places may be just a name + geocode; keep anything locatable
    select *
    from parsed
    where street_name is not null
       or (city_norm is not null and state_code is not null)
       or (lat is not null and lon is not null)
),

final as (
    select * from filtered
)

select * from final
