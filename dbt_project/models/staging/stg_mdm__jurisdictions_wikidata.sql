{{ config(materialized='view') }}

/*
    Staging: jurisdictions_wikidata (MDM input).

    1:1 with public.jurisdictions_wikidata. Light cleaning + a normalized
    `domain` extracted from `official_website` (same extract_domain logic as
    stg_mdm__organization_location).
*/

with

source as (
    select * from {{ source('mdm_inputs', 'jurisdictions_wikidata') }}
),

renamed as (
    select
        id                                          as wikidata_id,
        nullif(trim(jurisdiction_name), '')         as jurisdiction_name,
        nullif(trim(jurisdiction_type), '')         as jurisdiction_type,
        upper(nullif(trim(state_code), ''))         as state_code,
        nullif(trim(official_website), '')          as official_website,
        nullif(trim(nces_id), '')                   as nces_id,
        nullif(trim(geoid), '')                     as geoid,
        nullif(trim(fips_code), '')                 as fips_code,
        latitude::double precision                  as latitude,
        longitude::double precision                 as longitude
    from source
),

final as (
    select
        wikidata_id,
        jurisdiction_name,
        jurisdiction_type,
        state_code,
        official_website,
        nces_id,
        geoid,
        fips_code,
        latitude,
        longitude,
        case
            when official_website is null then null
            else nullif(
                lower(trim(
                    regexp_replace(
                        regexp_replace(official_website, '^https?://(www\.)?', '', 'i'),
                        '/.*$', ''
                    )
                )),
                ''
            )
        end                                         as domain,
        current_timestamp                           as dbt_loaded_at
    from renamed
)

select * from final
