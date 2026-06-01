{{ config(materialized='table') }}

/*
    Intermediate (MDM): 990 officers mapped to their resolved organization.

    Joins stg_990_officers -> mdm_organization on the bare-digit EIN (the org
    master keys on EIN, so this is an exact deterministic link). Only EIN-matched
    rows survive — the downstream bridge carries an enforced FK to mdm_organization,
    so an officer with no resolvable org is dropped here.

    Each officer inherits its geography (city/state/zip/lat/lon) from the org, since
    the 990 source carries none.

    Keys:
      - officer_person_uid : md5(name_norm | ein) — the officer identity scoped to
        the org, stable across tax years. A future Splink pass can attach a
        cross-org master_person_id alongside this.
      - org_person_year_id : md5(name_norm | ein | tax_year) — the per-year grain
        and the mart primary key.
*/

with officers as (
    select * from {{ ref('stg_990_officers') }}
    where ein_norm is not null
),

org as (
    select
        master_org_id,
        ein,
        org_name,
        city_norm,
        state_code,
        zip5,
        lat,
        lon
    from {{ ref('mdm_organization') }}
    where ein is not null
)

-- one row per (person, org, year): guard against duplicate reporting lines.
select distinct on (org_person_year_id)
    md5(o.name_norm || '|' || o.ein_norm || '|' || o.tax_year)  as org_person_year_id,
    md5(o.name_norm || '|' || o.ein_norm)                       as officer_person_uid,
    o.person_name,
    o.name_norm,
    o.entity_type,
    org.master_org_id,
    org.org_name,
    o.tax_year,
    o.title,
    o.is_officer,
    o.is_director_trustee,
    o.is_institutional_trustee,
    o.is_key_employee,
    o.is_highest_comp,
    o.is_former,
    o.avg_hours_org,
    o.avg_hours_related,
    o.reportable_comp_org,
    o.reportable_comp_related,
    o.other_comp,
    -- geography inherited from the organization
    org.city_norm,
    org.state_code,
    org.zip5,
    org.lat,
    org.lon,
    o.source_url
from officers o
join org on org.ein = o.ein_norm
order by
    org_person_year_id,
    -- prefer the most-complete reporting line when a (person,org,year) repeats
    (o.title is not null) desc,
    o.reportable_comp_org desc nulls last
