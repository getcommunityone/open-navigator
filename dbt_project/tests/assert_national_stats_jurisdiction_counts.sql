-- #291: the national row of jurisdiction_state_aggregate reported 0 jurisdictions
-- and 0 school districts although int_jurisdictions holds both. The national
-- figures must equal a direct count from int_jurisdictions, and the state rows
-- must not report 0 for a state that has jurisdictions. governments_count
-- (#351) must equal its direct count and never exceed jurisdictions_count.
-- Returns offending rows; the test passes when zero rows are returned.

with expected as (
    select
        count(*) filter (where jurisdiction_type <> 'state') as jurisdictions_count,
        count(*) filter (where jurisdiction_type = 'school_district') as school_districts_count,
        count(*) filter (
            where jurisdiction_type in ('county', 'school_district')
               or (jurisdiction_type in ('municipality', 'township') and funcstat in ('A', 'B', 'C'))
        ) as governments_count
    from {{ ref('int_jurisdictions') }}
    where state_code is not null
),

national as (
    select jurisdictions_count, school_districts_count, governments_count
    from {{ ref('jurisdiction_state_aggregate') }}
    where level = 'national'
)

select
    'national' as row_level,
    n.jurisdictions_count,
    e.jurisdictions_count as expected_jurisdictions_count,
    n.school_districts_count,
    e.school_districts_count as expected_school_districts_count
from national as n
cross join expected as e
where n.jurisdictions_count <> e.jurisdictions_count
   or n.school_districts_count <> e.school_districts_count
   or n.governments_count <> e.governments_count
   or n.governments_count > n.jurisdictions_count

union all

select
    'state:' || a.state_code,
    a.jurisdictions_count,
    j.cnt,
    null,
    null
from {{ ref('jurisdiction_state_aggregate') }} as a
join (
    select state_code, count(*) filter (where jurisdiction_type <> 'state') as cnt
    from {{ ref('int_jurisdictions') }}
    group by state_code
) as j on j.state_code = a.state_code
where a.level = 'state'
  and j.cnt > 0
  and a.jurisdictions_count = 0
