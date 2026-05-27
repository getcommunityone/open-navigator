{{ config(materialized='view') }}

/*
    Staging: jurisdiction (MDM input).

    1:1 with public.jurisdiction (census-derived serving table). Aliases `type`
    to `jurisdiction_type` (the column the original Python crosswalk SQL
    referenced as `jd.jurisdiction_type` / `js.type`), and extracts a normalized
    `domain` from website_url.

    FLAG: the original Python script's phone-matching strategy joined on
    `jd.phone`, but public.jurisdiction has NO phone column (phone lives on the
    `contact` table). That strategy is therefore NOT reproducible against the
    current schema and is documented as deferred in the MDM int models.
*/

with

source as (
    select * from {{ source('mdm_inputs', 'jurisdiction') }}
),

renamed as (
    select
        id                                          as jurisdiction_id,
        nullif(trim(name), '')                      as jurisdiction_name,
        nullif(trim(type), '')                      as jurisdiction_type,
        upper(nullif(trim(state_code), ''))         as state_code,
        nullif(trim(state), '')                     as state_name,
        nullif(trim(county), '')                    as county,
        nullif(trim(geoid), '')                     as geoid,
        nullif(trim(fips_code), '')                 as fips_code,
        nullif(trim(website_url), '')               as website_url,
        gov_domains                                 as gov_domains
    from source
),

final as (
    select
        jurisdiction_id,
        jurisdiction_name,
        jurisdiction_type,
        state_code,
        state_name,
        county,
        geoid,
        fips_code,
        website_url,
        gov_domains,
        case
            when website_url is null then null
            else nullif(
                lower(trim(
                    regexp_replace(
                        regexp_replace(website_url, '^https?://(www\.)?', '', 'i'),
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
