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
- stg_givingtuesday__990_officers     (Part VII-A, the base grain)
- stg_givingtuesday__990_schedule_j   (Schedule J detail)
- int_nonprofits_combined             (org metadata, 1 row per EIN)

Target: API routes (nonprofit detail / "top earners" views).
*/

with

officers as (
    select * from {{ ref('stg_givingtuesday__990_officers') }}
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
)

select
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
