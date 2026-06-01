{{ config(materialized='view') }}

/*
    Staging (MDM org conformance): nonprofits from the IRS Business Master File
    (bronze_organizations_nonprofits_irs, ~1.95M orgs), onto the shared org
    contract. EIN is the deterministic key that merges nonprofits across sources,
    so IRS rows for an EIN already present in NCCS collapse into the same cluster;
    IRS-only EINs (~290k absent from NCCS) finally get a golden master_org_id and
    flow through to mdm_organization / mdm_organization_nonprofit.

    NCCS is the richer, geocoded nonprofit source, so where both exist NCCS wins
    survivorship in mdm_organization (see int_organizations__clustered ranking).
    The IRS detail (financials, NTEE, etc.) is still merged per-EIN downstream in
    int_nonprofits_combined.
*/

with source as (
    select * from {{ source('bronze', 'bronze_organizations_nonprofits_irs') }}
    where ein is not null
)

select
    'bronze_organizations_nonprofits_irs'         as source_system,
    ein                                           as source_pk,
    name                                          as org_name,
    {{ normalize_org_name('name') }}              as org_name_norm,
    {{ canonical_org_type('ntee_cd', 'nonprofit') }} as org_type,
    nullif(ntee_cd, '')                           as org_subtype,
    nullif(ein, '')                               as ein,
    nullif(lower(trim(unaccent(city))), '')       as city_norm,
    upper(left(trim(state_code), 2))              as state_code,
    nullif(left(trim(zip_code), 5), '')           as zip5,
    null::double precision                        as lat,
    null::double precision                        as lon,
    null::text                                    as website,
    -- tax_period is YYYYMM; take the calendar year as the as-of year
    case when tax_period ~ '^\d{6}$' then left(tax_period, 4)::int end as as_of_year
from source
where {{ normalize_org_name('name') }} is not null
