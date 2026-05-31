{{ config(materialized='view') }}

/*
    Staging (MDM org conformance): nonprofits from int_nccs__current_orgs (current
    record per EIN), onto the shared org contract. EIN is the deterministic key
    that merges nonprofits across sources; nccs_level_1 refines the type beyond
    the nonprofit default (e.g. healthcare, education).
*/

with source as (
    select * from {{ ref('int_nccs__current_orgs') }}
)

select
    'bronze_organizations_nonprofits_nccs'                 as source_system,
    ein                                                    as source_pk,
    org_name_current                                       as org_name,
    {{ normalize_org_name('org_name_current') }}           as org_name_norm,
    {{ canonical_org_type('nccs_level_1', 'nonprofit') }}  as org_type,
    nullif(coalesce(ntee_nccs, ntee_irs, nccs_level_1), '') as org_subtype,
    nullif(ein, '')                                        as ein,
    nullif(lower(trim(unaccent(city))), '')                as city_norm,
    upper(left(trim(state_code), 2))                       as state_code,
    null::text                                             as zip5,
    latitude                                               as lat,
    longitude                                              as lon,
    null::text                                             as website,
    org_year_last::int                                     as as_of_year
from source
where {{ normalize_org_name('org_name_current') }} is not null
