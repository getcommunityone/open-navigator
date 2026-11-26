{{ config(materialized='view') }}

/*
    Staging (MDM org conformance, #1015): curated short-term rental platform companies (Airbnb, Expedia Group /
    Vrbo, Booking Holdings) from the short_term_rental_companies seed onto the shared org contract, org_type
    'company'. Same shape and reasoning as stg_data_center_companies__org: a company is national, so its
    deterministic cluster key in int_organizations__clustered is md5(org_name_norm || '||'); a same-name national
    row from another source lands in the same cluster. "Airbnb" normalizes to 'airbnb', not 'airbnb org', so the
    Airbnb.org charity stays its own organization. Platform detail lives in mdm_organization_short_term_rental.
*/

select
    'seed_short_term_rental_companies'::text        as source_system,
    company_key::text                               as source_pk,
    company_name::text                              as org_name,
    {{ normalize_org_name('company_name') }}        as org_name_norm,
    'company'::text                                 as org_type,
    'short_term_rental'::text                       as org_subtype,
    null::text                                      as ein,
    null::text                                      as city_norm,
    null::text                                      as state_code,
    null::text                                      as zip5,
    null::double precision                          as lat,
    null::double precision                          as lon,
    nullif(btrim(website_url), '')::text            as website,
    null::int                                       as as_of_year
from {{ ref('short_term_rental_companies') }}
