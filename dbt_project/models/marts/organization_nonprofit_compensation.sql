{{
  config(
    materialized='table',
    tags=['gold', 'nonprofits', 'compensation', 'api'],
    database='open_navigator'
  )
}}

/*
Gold Nonprofit Compensation - person-level executive/board compensation.

One row per (ein, tax_year, person, title) from Form 990 Part VII, Section A,
enriched with:
  - Schedule J Part 2 detailed compensation (base/bonus/deferred/benefits), for
    the subset of people detailed there (LEFT JOIN; NULL when not on Schedule J),
  - organization context (name, city, state, NTEE) from int_nonprofits_combined.

Source models:
- stg_990_officers                    (Part VII-A, the base grain — reused from
                                       the MDM officer pipeline; same bronze source)
- stg_givingtuesday__990_schedule_j   (Schedule J detail)
- int_nonprofits_combined             (org metadata, 1 row per EIN)
- mdm_organization_nonprofit          (EIN -> master_org_id, for the enforced FK)

Grain: one row per (ein, tax_year, person_name, title). compensation_id is a
deterministic hash over that grain (the enforced PK). master_org_id is the
enforced FK to mdm_organization (NULL when the EIN is not in the org master).

Target: API routes (nonprofit detail / "top earners" views).
*/

with

-- Part VII-A grain. Reuses stg_990_officers (the MDM officer staging model) rather
-- than a duplicate stg_givingtuesday__990_officers: both read
-- bronze_organizations_990_officers at the same (ein, tax_year, person) grain and
-- carry the role flags + reportable-comp columns we need. Column-name adaptations:
--   ein_norm -> ein, filer_org_name -> org_name. total_comp is not exposed there,
-- so it is computed here (reportable_org + reportable_related + other_comp).
officers as (
    select
        ein_norm                                  as ein,
        tax_year,
        filer_org_name                             as org_name,
        person_name,
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
        coalesce(reportable_comp_org, 0)
            + coalesce(reportable_comp_related, 0)
            + coalesce(other_comp, 0)              as total_comp,
        source_url
    from {{ ref('stg_990_officers') }}
    where ein_norm is not null
      and length(ein_norm) >= 9
),

-- Collapse Schedule J to one row per (ein, tax_year, person) to avoid fan-out
-- when joining onto the Part VII-A grain (pick the highest total comp).
schedule_j as (
    select * from (
        select
            *,
            row_number() over (
                partition by ein, tax_year, upper(person_name)
                order by coalesce(total_comp_org, 0) desc
            ) as rn
        from {{ ref('stg_givingtuesday__990_schedule_j') }}
    ) ranked
    where rn = 1
),

-- Organization context: 1 row per EIN.
orgs as (
    select
        ein,
        name             as org_name,
        city,
        state_code_clean as state_code,
        ntee_code
    from {{ ref('int_nonprofits_combined') }}
),

-- EIN -> golden org id, for the enforced FK to mdm_organization. The satellite is
-- 1:1 on EIN, so this join does not fan out the officer grain.
org_master as (
    select
        ein,
        master_org_id
    from {{ ref('mdm_organization_nonprofit') }}
),

joined as (
select
    -- Deterministic surrogate PK over the natural grain (ein, tax_year, person,
    -- title). title can be null; coalesce so the hash stays stable and non-null.
    md5(
        o.ein
        || '|' || coalesce(o.tax_year::text, '')
        || '|' || upper(o.person_name)
        || '|' || coalesce(upper(o.title), '')
    )                                  as compensation_id,

    m.master_org_id,
    o.ein,
    o.tax_year,
    o.person_name,
    o.title,

    -- organization context
    coalesce(org.org_name, o.org_name) as org_name,
    org.city,
    org.state_code,
    org.ntee_code,

    -- Part VII-A role flags
    o.is_officer,
    o.is_director_trustee,
    o.is_institutional_trustee,
    o.is_key_employee,
    o.is_highest_comp,
    o.is_former,
    o.avg_hours_org,
    o.avg_hours_related,

    -- Part VII-A reportable compensation
    o.reportable_comp_org,
    o.reportable_comp_related,
    o.other_comp,
    o.total_comp,

    -- Schedule J Part 2 detail (NULL when the person is not detailed on Sch J)
    (j.ein is not null)              as has_schedule_j,
    j.base_comp_org,
    j.bonus_org,
    j.other_comp_org                 as sch_j_other_comp_org,
    j.deferred_comp_org,
    j.nontaxable_benefits_org,
    j.total_comp_org                 as sch_j_total_comp_org,
    j.total_comp_related             as sch_j_total_comp_related,
    j.prior_reported_org,

    o.source_url,
    current_timestamp                as published_at
from officers o
left join schedule_j j
    on  o.ein = j.ein
    and o.tax_year is not distinct from j.tax_year
    and upper(o.person_name) = upper(j.person_name)
left join orgs org
    on o.ein = org.ein
left join org_master m
    on o.ein = m.ein
),

-- Enforce one row per compensation_id so the PK constraint holds: the source can
-- repeat a (ein, tax_year, person, title) line; keep the highest-comp occurrence.
deduped as (
    select * from (
        select
            *,
            row_number() over (
                partition by compensation_id
                order by coalesce(total_comp, 0) desc
            ) as _rn
        from joined
    ) ranked
    where _rn = 1
)

select
    compensation_id,
    master_org_id,
    ein,
    tax_year,
    person_name,
    title,
    org_name,
    city,
    state_code,
    ntee_code,
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
    total_comp,
    has_schedule_j,
    base_comp_org,
    bonus_org,
    sch_j_other_comp_org,
    deferred_comp_org,
    nontaxable_benefits_org,
    sch_j_total_comp_org,
    sch_j_total_comp_related,
    prior_reported_org,
    source_url,
    published_at
from deduped
