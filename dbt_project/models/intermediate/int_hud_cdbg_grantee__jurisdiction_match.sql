{{ config(materialized='table', sql_header='set enable_nestloop = off;') }}

/*
    Intermediate (#1394): match each HUD CDBG grantee to gold.jurisdictions.
      * grantee type 21 (state): the state jurisdiction                         -> 0.99
      * type 61 (urban county) or a name ending COUNTY: normalized name + state
        against counties                                                         -> 0.95 unique, 0.60 several
      * other types (entitlement cities, small cities, others): normalized name
        + state against cities and towns (Census county divisions excluded)      -> 0.95 unique, 0.60 several
    Several candidates: the most populous is taken and flagged by the 0.60 score.
    Unmatched grantees stay NULL, never forced.
*/

with grantees as materialized (
    select
        grantee_id, state_code,
        max(grantee_type_code) as grantee_type_code,
        max(grantee_name) as grantee_name
    from {{ ref('stg_hud_cdbg__activity') }}
    group by 1, 2
),

kinded as materialized (
    select
        *,
        case
            when grantee_type_code = '21' then 'state'
            when grantee_type_code = '61' or upper(grantee_name) ~ ' COUNTY$' then 'county'
            else 'place'
        end as kind,
        trim(regexp_replace(regexp_replace(regexp_replace(upper(grantee_name), '[^A-Z0-9 ]', '', 'g'),
             '\mSAINT\M', 'ST', 'g'),
             ' (COUNTY|PARISH|CITY|TOWN|VILLAGE|BOROUGH|TOWNSHIP)$', '')) as base_name
    from grantees
),

jur as materialized (
    select
        jurisdiction_id, state_code, population,
        case when jurisdiction_type in ('city', 'town') then 'place' else jurisdiction_type end as kind,
        trim(regexp_replace(regexp_replace(regexp_replace(upper(name), '[^A-Z0-9 ]', '', 'g'),
             '\mSAINT\M', 'ST', 'g'),
             ' (COUNTY|PARISH|CITY|TOWN|VILLAGE|BOROUGH|TOWNSHIP|CENSUS AREA|MUNICIPALITY)$', '')) as base_name
    from {{ ref('jurisdictions') }}
    where jurisdiction_type in ('state', 'county', 'city', 'town')
      and upper(name) not like '% CCD'
),

cands as (
    select
        k.grantee_id, k.state_code, j.jurisdiction_id, k.kind,
        count(*) over (partition by k.grantee_id, k.state_code) as n_cands,
        row_number() over (
            partition by k.grantee_id, k.state_code order by coalesce(j.population, 0) desc, j.jurisdiction_id
        ) as rn
    from kinded k
    join jur j
      on j.state_code = k.state_code
     and j.kind = k.kind
     and (k.kind = 'state' or j.base_name = k.base_name)
)

select
    grantee_id, state_code, jurisdiction_id,
    case when kind = 'state' then 0.99 when n_cands = 1 then 0.95 else 0.60 end::numeric(3,2) as match_confidence
from cands
where rn = 1
