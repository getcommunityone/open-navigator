{{
  config(
    materialized='table',
    tags=['marts', 'opportunity_atlas', 'mobility', 'production'],
    unique_key='opportunity_atlas_mobility_id',
    indexes=[
      {'columns': ['cz'], 'type': 'btree'},
      {'columns': ['czname'], 'type': 'btree'},
      {'columns': ['race', 'gender', 'parent_income_level'], 'type': 'btree'}
    ]
  )
}}

/*
gold.opportunity_atlas_mobility (published to public.opportunity_atlas_mobility) —
commuting-zone (CZ) intergenerational-mobility, long/tidy: one row per
(cz, race, gender, parent_income_level).

SOURCE: Opportunity Insights "Opportunity Atlas" / Chetty, Hendren, Jones & Porter
(2018), "Race and Economic Opportunity in the United States" (cz_outcomes.csv).

MEASURE: child_income_rank = child's mean adult household-income RANK (decimal
0..1) given parents at the parent_percentile national income percentile.
child_percentile = round(rank*100, 1) is the same on a 0..100 display scale.
parent_income_level low->25 / middle->50 / high->75 (parent_percentile).

NO FABRICATED DATA: child_income_rank is NULL where the source cell was blank;
never substituted with 0 or any stand-in. n is the source sample count for the
(race, gender) cell — use it for honest empty states.

GRAIN / KEYS (per CLAUDE.md, enforced as Postgres constraints via contract):
  - PK: (cz, race, gender, parent_income_level). A single-column surrogate
    opportunity_atlas_mobility_id = md5(cz||'|'||race||'|'||gender||'|'||level)
    is also carried so children/serving can reference one stable id; the
    composite is declared as the contract PK below.
*/

with src as (
    select * from {{ ref('stg_opportunity_atlas_cz') }}
)

select
    md5(
        src.cz::text || '|' || src.race || '|' || src.gender
        || '|' || src.parent_income_level
    )                                              as opportunity_atlas_mobility_id,
    src.cz,
    src.czname,
    src.race,
    src.gender,
    src.parent_income_level,
    src.parent_percentile,
    src.child_income_rank,
    src.child_percentile,
    src.n
from src
