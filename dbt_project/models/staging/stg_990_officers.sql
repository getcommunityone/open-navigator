{{ config(materialized='table') }}
-- Materialized as a TABLE (not the usual staging view): the name-normalization regex
-- (normalize_person_name + classify_name_entity_type) is expensive, and downstream
-- int_990_officers__org_linked reads this twice (dedup + final join). A view would
-- re-run the regex over all 40M rows on every reference; a table runs it once.

/*
    Staging: IRS Form 990 Part VII people (officers, directors, trustees, key
    employees) from bronze_organizations_990_officers, conformed for the
    organization-officer bridge.

    Grain: one row per bronze row = one (ein, tax_year, person) reporting line.
    NOT a person-pool conformance model — these people are mapped to orgs on EIN
    (mdm_bridge_person_organization), not routed through Splink, because the source
    carries no geography of its own (it's inherited from the org downstream).

    Name handling reuses the shared MDM macros so officer names normalize the same
    way as the rest of the person pool, leaving the door open to a future Splink
    pass once geography is attached from the org.
*/

with source as (
    select * from {{ source('bronze', 'bronze_organizations_990_officers') }}
)

select
    id,  -- bronze surrogate key; stable tiebreaker for the per-(person,org,year) dedup
    -- bare-digit EIN: the org master stores EINs without dashes/spaces.
    nullif(regexp_replace(ein, '\D', '', 'g'), '')  as ein_norm,
    tax_year,
    org_name                                        as filer_org_name,
    person_name,
    {{ normalize_person_name('person_name') }}      as name_norm,
    -- person vs org-shaped name (institutional trustees are frequently orgs).
    {{ classify_name_entity_type('person_name') }}  as entity_type,
    title,
    is_officer,
    is_director_trustee,
    is_institutional_trustee,
    is_key_employee,
    is_highest_comp,
    is_former,
    avg_hours_org,
    avg_hours_related,
    reportable_comp_org,
    reportable_comp_related,
    other_comp,
    source_url
from source
where {{ normalize_person_name('person_name') }} is not null
