{{ config(materialized='view') }}

/*
    Staging (MDM org conformance): AI-extracted organizations from
    bronze_organizations_from_ai, onto the shared org contract. Carries the AI
    org_type (canonicalized) and EIN where the model resolved one.
*/

with source as (
    select * from {{ ref('bronze_organizations_from_ai') }}
)

select
    'bronze_organizations_from_ai'                 as source_system,
    org_name_normalized_state_code                 as source_pk,
    org_name                                       as org_name,
    {{ normalize_org_name('org_name') }}           as org_name_norm,
    {{ canonical_org_type('org_type') }}           as org_type,
    nullif(coalesce(org_subtype, org_type), '')    as org_subtype,
    nullif(ein, '')                                as ein,
    null::text                                     as city_norm,
    upper(left(trim(state_code), 2))               as state_code,
    null::text                                     as zip5,
    null::double precision                         as lat,
    null::double precision                         as lon,
    null::text                                     as website,
    extract(year from extracted_at)::int           as as_of_year
from source
where {{ normalize_org_name('org_name') }} is not null
