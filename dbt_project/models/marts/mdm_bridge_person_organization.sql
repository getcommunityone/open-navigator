{{ config(materialized='table') }}

/*
    Mart (MDM): the public organization-officer bridge — IRS Form 990 Part VII
    people (officers, directors, trustees, key employees) mapped to their resolved
    organization, with full year-by-year history of role and compensation.

    Grain: one row per (officer person, organization, tax_year). PK org_person_year_id,
    FK master_org_id -> mdm_organization.

    The person side is keyed on the deterministic officer_person_uid (name + EIN);
    these people are NOT (yet) resolved into mdm_person, so there is intentionally no
    person FK. Geography is inherited from the organization. See
    int_990_officers__org_linked for the keys and the EIN link.
*/

select
    org_person_year_id,
    officer_person_uid,
    person_name,
    name_norm,
    master_org_id,
    org_name,
    tax_year,
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
    city_norm,
    state_code,
    zip5,
    lat,
    lon,
    source_url
from {{ ref('int_990_officers__org_linked') }}
