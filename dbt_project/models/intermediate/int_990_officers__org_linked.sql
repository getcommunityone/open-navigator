{{ config(
    materialized='table',
    pre_hook="set work_mem = '1GB'"
) }}

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

    Dedup is done NARROWLY: `winners` picks one bronze id per (name_norm, ein, year)
    by sorting only the key + id, not the 25 wide columns. The wide `distinct on`
    spilled ~21 GB to temp; this keeps the sort payload tiny.
*/

with officers as (
    select * from {{ ref('stg_990_officers') }}
    where ein_norm is not null
),

org as (
    -- distinct on ein: ein is the master_org_id for nonprofits (1:1), but guard
    -- against any fan-out that would duplicate org_person_year_id and break the PK.
    select distinct on (ein)
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
    order by ein, master_org_id
),

-- one surviving bronze row per (name_norm, ein, tax_year): most-complete line wins.
winners as (
    select distinct on (name_norm, ein_norm, tax_year) id
    from officers
    order by
        name_norm, ein_norm, tax_year,
        (title is not null) desc,
        reportable_comp_org desc nulls last,
        id
)

select
    md5(o.name_norm || '|' || o.ein_norm || '|' || o.tax_year::text)  as org_person_year_id,
    md5(o.name_norm || '|' || o.ein_norm)                             as officer_person_uid,
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
join winners w on w.id = o.id
join org on org.ein = o.ein_norm
