{{ config(materialized='view') }}

/*
    Staging: organization_location (MDM input).

    1:1 with public.organization_location. Light cleaning + type stabilization
    and a normalized `domain` column extracted from `website`, reproducing the
    Python extract_domain() helper:
        http://www.yupiit.org -> yupiit.org
    (lowercase, strip scheme + leading www., drop path/query, trim trailing /).
    The original loader wrote rows verbatim; domain extraction was done in Python
    per-row — moved here so all downstream crosswalk steps share one definition.
*/

with

source as (
    select * from {{ source('mdm_inputs', 'organization_location') }}
),

renamed as (
    select
        id                                          as org_location_id,
        nullif(trim(source_id), '')                 as source_id,
        nullif(trim(name), '')                      as org_name,
        nullif(trim(organization_type), '')         as organization_type,
        nullif(trim(city), '')                      as city,
        upper(nullif(trim(state), ''))              as state_code,
        nullif(trim(county), '')                    as county,
        nullif(trim(telephone), '')                 as telephone,
        nullif(trim(website), '')                   as website,
        latitude::double precision                  as latitude,
        longitude::double precision                 as longitude
    from source
),

final as (
    select
        org_location_id,
        source_id,
        org_name,
        organization_type,
        city,
        state_code,
        county,
        telephone,
        website,
        latitude,
        longitude,
        -- Normalized domain (extract_domain equivalent): strip scheme + www.,
        -- drop everything from the first '/', lowercase + trim. NULL when the
        -- website is missing or a placeholder ("...not available...").
        case
            when website is null then null
            when website ilike '%not available%' then null
            else nullif(
                lower(trim(
                    regexp_replace(
                        regexp_replace(website, '^https?://(www\.)?', '', 'i'),
                        '/.*$', ''
                    )
                )),
                ''
            )
        end                                         as domain,
        -- Phone normalized to digits only (>= 10 digits qualifies for matching).
        nullif(regexp_replace(coalesce(telephone, ''), '[^0-9]', '', 'g'), '')
                                                    as phone_digits,
        current_timestamp                           as dbt_loaded_at
    from renamed
)

select * from final
