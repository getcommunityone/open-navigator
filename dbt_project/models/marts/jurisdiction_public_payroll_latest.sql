{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction'],
    indexes=[{'columns': ['function_code', 'year'], 'type': 'btree'}]
  )
}}

/*
    jurisdiction_public_payroll_latest (#1395): the served slice of jurisdiction_public_payroll.
    Only the latest survey year, twelve core functions and only the columns the benchmark reads, so the table
    stays under the 5 MB serving limit. Grain: jurisdiction_id x function_code (year is
    the single latest survey year). The full history stays gold-only.
*/

select
    jurisdiction_id::text                  as jurisdiction_id,
    year::integer                          as year,
    function_code::text                    as function_code,
    state_code::text                       as state_code,
    state::text                            as state,
    full_time_employees::integer           as full_time_employees,
    full_time_payroll_dollars::numeric     as full_time_payroll_dollars,
    avg_monthly_pay::numeric               as avg_monthly_pay,
    source_updated_at::timestamp           as source_updated_at
from {{ ref('jurisdiction_public_payroll') }}
where year = (select max(year) from {{ ref('jurisdiction_public_payroll') }})
  and full_time_employees > 0
  -- the municipal functions peers are compared on (keeps the slice under 5 MB)
  and function_code in ('000', '023', '029', '062', '162', '024', '124', '044', '061', '052', '081', '080')
