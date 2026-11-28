{{ config(materialized='view') }}

/*
    Staging: Census ASPEP employees and March payroll by government x function (#1395).
    Dollars are the 31-day monthly equivalent for March. Blank source values stay NULL.
    There is no per-person pay in this source.
*/

select
    survey_year::integer                                  as survey_year,
    unit_id::text                                         as unit_id,
    item_code::text                                       as function_code,
    nullif(trim(full_time_employees), '')::integer        as full_time_employees,
    nullif(trim(full_time_payroll), '')::numeric(16,0)    as full_time_payroll_dollars,
    nullif(trim(part_time_employees), '')::integer        as part_time_employees,
    nullif(trim(part_time_payroll), '')::numeric(16,0)    as part_time_payroll_dollars,
    full_time_payroll_flag::text                          as full_time_payroll_flag
from {{ source('bronze', 'bronze_aspep_employment') }}
