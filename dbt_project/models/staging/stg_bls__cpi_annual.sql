{{ config(materialized='view') }}

/*
Annual-average BLS CPI index — one row per (series_id, year).

BLS returns the annual average as ``period='M13'`` when the API request sets
``annualaverage=true`` (the loader always does). When that row is missing
(e.g. partial current-year coverage), this falls back to the mean of the
available monthly observations — but only when at least 6 months are present,
so a sparse current year isn't silently blessed as a final annual figure.
``from_official_annual`` flags which lens applied.

Downstream: the frontend real-dollar toggle reads this as a
``{year: index_value}`` map keyed on CUUR0000SA0 (the default loaded series)
and applies it uniformly to every geography — see ``frontend/src/utils/inflation.ts``
(forthcoming PR).
*/

with

source as (
    select * from {{ ref('bronze_bls_cpi') }}
),

annual_explicit as (
    select
        series_id,
        year,
        value as index_value,
        true  as from_official_annual
    from source
    where period = 'M13'
),

annual_fallback as (
    select
        series_id,
        year,
        round(avg(value)::numeric, 3) as index_value,
        false                         as from_official_annual
    from source
    where period like 'M%' and period <> 'M13'
    group by series_id, year
    having count(*) >= 6
),

merged as (
    select * from annual_explicit
    union all
    select f.*
    from annual_fallback f
    where not exists (
        select 1
        from annual_explicit e
        where e.series_id = f.series_id and e.year = f.year
    )
)

select
    series_id,
    year,
    index_value,
    from_official_annual,
    current_timestamp as dbt_loaded_at
from merged
order by series_id, year
