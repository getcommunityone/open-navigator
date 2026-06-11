{{
  config(
    materialized='table',
    tags=['marts', 'opportunity_atlas', 'mobility', 'production'],
    unique_key='opportunity_atlas_mobility_national_id',
    indexes=[
      {'columns': ['race', 'gender', 'parent_income_level'], 'type': 'btree'}
    ]
  )
}}

/*
gold.opportunity_atlas_mobility_national (published to
public.opportunity_atlas_mobility_national) — a national rollup of the CZ
Opportunity Atlas mobility measures: one row per (race, gender,
parent_income_level).

DERIVED AGGREGATE — POPULATION-WEIGHTED ACROSS COMMUTING ZONES. child_income_rank
here is the sample-count-weighted mean of the per-CZ child_income_rank, using each
CZ's (race, gender) sample count `n` as the weight. CZs with a NULL rank or NULL/
zero n are excluded from the average (honest — never zero-filled). This is NOT a
figure published by Opportunity Insights; it is our transparent weighted mean of
their CZ values, labeled as such. total_n is the summed weight (sample size)
behind each row, for honest empty states.

KEYS (per CLAUDE.md, enforced as Postgres constraints via contract):
  - PK: (race, gender, parent_income_level). Surrogate id
    opportunity_atlas_mobility_national_id = md5(race||'|'||gender||'|'||level)
    also carried.
*/

with src as (
    select
        race,
        gender,
        parent_income_level,
        parent_percentile,
        child_income_rank,
        n
    from {{ ref('stg_opportunity_atlas_cz') }}
),

weighted as (
    select
        race,
        gender,
        parent_income_level,
        max(parent_percentile)                     as parent_percentile,
        -- count-weighted mean of child_income_rank across CZs (weight = n),
        -- ignoring rows with NULL rank or NULL/<=0 weight. NULL when no usable
        -- (rank, n) pairs exist (honest empty state).
        sum(child_income_rank * n)
            filter (where child_income_rank is not null and n > 0)
          / nullif(
              sum(n) filter (where child_income_rank is not null and n > 0),
              0
            )                                       as child_income_rank,
        sum(n) filter (where child_income_rank is not null and n > 0)
                                                    as total_n
    from src
    group by race, gender, parent_income_level
)

select
    md5(race || '|' || gender || '|' || parent_income_level)
                                                   as opportunity_atlas_mobility_national_id,
    race,
    gender,
    parent_income_level,
    parent_percentile,
    child_income_rank::numeric                     as child_income_rank,
    case
        when child_income_rank is null then null
        else round((child_income_rank * 100.0)::numeric, 1)
    end                                            as child_percentile,
    total_n::numeric                               as total_n
from weighted
