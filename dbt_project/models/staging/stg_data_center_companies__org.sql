{{ config(materialized='view') }}

/*
    Staging (MDM org conformance, #531): curated data center companies from the
    data_center_companies seed onto the shared org contract, org_type 'company'.

    No city or state: a company is national, so its deterministic cluster key in
    int_organizations__clustered is md5(org_name_norm || '||'). A same-name national
    row from another source (e.g. the AI-extracted "Google" or "Microsoft") lands in
    the same cluster, so the existing master_org_id is reused, not duplicated.
    Data center detail (roles, aliases, feed, source) lives in the
    mdm_organization_data_center satellite.
*/

select
    'seed_data_center_companies'::text              as source_system,
    company_key::text                               as source_pk,
    company_name::text                              as org_name,
    {{ normalize_org_name('company_name') }}        as org_name_norm,
    'company'::text                                 as org_type,
    'data_center'::text                             as org_subtype,
    null::text                                      as ein,
    null::text                                      as city_norm,
    null::text                                      as state_code,
    null::text                                      as zip5,
    null::double precision                          as lat,
    null::double precision                          as lon,
    nullif(btrim(website_url), '')::text            as website,
    null::int                                       as as_of_year
from {{ ref('data_center_companies') }}
where {{ normalize_org_name('company_name') }} is not null
