{{
  config(
    materialized='view',
    tags=['staging', 'opportunity_atlas', 'mobility']
  )
}}

/*
staging.stg_opportunity_atlas_cz — cleaned, typed commuting-zone (CZ)
intergenerational-mobility measures from bronze.bronze_opportunity_atlas_cz
(Opportunity Insights "Opportunity Atlas"; Chetty, Hendren, Jones & Porter 2018,
"Race and Economic Opportunity in the United States").

GRAIN: one row per (cz, race, gender, parent_income_level) — long/tidy.

MEASURE: child_income_rank = the child's mean adult household-income RANK
(a decimal 0..1) given parents at the parent_percentile national income
percentile. child_percentile = round(child_income_rank * 100, 1) is the same on
a 0..100 scale for display. parent_income_level maps to parent_percentile
(low -> 25, middle -> 50, high -> 75).

NULL stays NULL: child_income_rank is NULL where the source cell was blank
(honest "missing", never 0 / never a stand-in). n is the per-(race,gender)
sample-count column from the source, used downstream for honest empty states.
*/

with src as (
    select
        cz,
        czname,
        race,
        gender,
        parent_income_level,
        child_income_rank,
        n
    from {{ source('bronze', 'bronze_opportunity_atlas_cz') }}
)

select
    cz,
    nullif(trim(czname), '')                       as czname,
    race,
    gender,
    parent_income_level,
    case parent_income_level
        when 'low'    then 25
        when 'middle' then 50
        when 'high'   then 75
    end                                            as parent_percentile,
    child_income_rank::numeric                     as child_income_rank,
    case
        when child_income_rank is null then null
        else round((child_income_rank * 100.0)::numeric, 1)
    end                                            as child_percentile,
    n::numeric                                     as n
from src
