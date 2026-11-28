{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction'],
    indexes=[
      {'columns': ['jurisdiction_id', 'year'], 'type': 'btree'},
      {'columns': ['function_code', 'year'], 'type': 'btree'}
    ]
  )
}}

/*
    jurisdiction_public_payroll (#1395): Census ASPEP public employees and March payroll
    per matched jurisdiction x survey year x function. Aggregate only: it holds no
    per-person pay and no department-head salary. Grain: jurisdiction_id x year x
    function_code (composite PK). Payroll is the 31-day monthly equivalent for March.
    Non-census years (not ending in 2 or 7) cover only sampled governments.
*/

select
    m.jurisdiction_id::text                       as jurisdiction_id,
    e.survey_year::integer                        as year,
    e.function_code::text                         as function_code,
    f.function_name::text                         as function_name,
    j.state_code::text                            as state_code,
    j.state_name::text                            as state,
    e.full_time_employees::integer                as full_time_employees,
    e.full_time_payroll_dollars::numeric          as full_time_payroll_dollars,
    case when e.full_time_employees > 0
         then round(e.full_time_payroll_dollars / e.full_time_employees, 0) end::numeric as avg_monthly_pay,
    e.part_time_employees::integer                as part_time_employees,
    m.match_confidence::numeric                   as match_confidence,
    u.source_updated_at::timestamp                as source_updated_at
from {{ ref('stg_aspep__employment') }} e
join {{ ref('int_aspep_unit__jurisdiction_match') }} m
  on m.survey_year = e.survey_year and m.unit_id = e.unit_id
join {{ ref('stg_aspep__unit') }} u
  on u.survey_year = e.survey_year and u.unit_id = e.unit_id
join {{ ref('jurisdictions') }} j on j.jurisdiction_id = m.jurisdiction_id
left join {{ ref('aspep_function_code') }} f on f.function_code = e.function_code
