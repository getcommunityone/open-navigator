{{ config(materialized='table', sql_header='set enable_nestloop = off;') }}

/*
    Intermediate (#1395): match each ASPEP government x year to gold.jurisdictions.
      * counties: exact 5-digit FIPS = jurisdictions.geoid          -> 0.99
      * states: state_code on the 'state' jurisdiction              -> 0.99
      * municipalities and townships: normalized name + state, kind city or town (Census
        county divisions, "CCD", are excluded); one candidate -> 0.95, several -> the one
        whose population is closest to ASPEP's -> 0.60.
      * special districts and school districts are not matched (their names are not
        comparable); they stay out of the mart rather than being forced.
    If two units map to one jurisdiction in a year, only the best match is kept.
*/

with units as materialized (
    select
        u0.survey_year, u0.unit_id, st.state_code, u0.unit_type, u0.county_fips, u0.population_or_enrollment,
        trim(regexp_replace(regexp_replace(regexp_replace(upper(u0.government_name), '[^A-Z0-9 ]', '', 'g'),
             '\mSAINT\M', 'ST', 'g'),
             ' (CITY|TOWN|VILLAGE|BOROUGH|TOWNSHIP|CHARTER TOWNSHIP|PLANTATION)$', '')) as base_name
    from {{ ref('stg_aspep__unit') }} u0
    join (select geoid as fips, state_code from {{ ref('jurisdictions') }} where jurisdiction_type = 'state') st
      on st.fips = u0.fips_state
    where u0.unit_type in ('state', 'county', 'municipality', 'township')
),

jur as materialized (
    select
        jurisdiction_id, geoid, state_code, jurisdiction_type, population,
        trim(regexp_replace(regexp_replace(regexp_replace(upper(name), '[^A-Z0-9 ]', '', 'g'),
             '\mSAINT\M', 'ST', 'g'),
             ' (CITY|TOWN|VILLAGE|BOROUGH|TOWNSHIP|CHARTER TOWNSHIP|PLANTATION)$', '')) as base_name
    from {{ ref('jurisdictions') }}
    where jurisdiction_type in ('state', 'county', 'city', 'town')
      and upper(name) not like '% CCD'
),

by_geo as (
    select u.survey_year, u.unit_id, j.jurisdiction_id, 0.99::numeric(3,2) as match_confidence, 1 as rn
    from units u
    join jur j on u.unit_type = 'county' and j.jurisdiction_type = 'county' and j.geoid = u.county_fips
    union all
    select u.survey_year, u.unit_id, j.jurisdiction_id, 0.99::numeric(3,2), 1
    from units u
    join jur j on u.unit_type = 'state' and j.jurisdiction_type = 'state' and j.state_code = u.state_code
),

named as (
    select
        u.survey_year, u.unit_id, j.jurisdiction_id,
        count(*) over (partition by u.survey_year, u.unit_id) as n_cands,
        row_number() over (
            partition by u.survey_year, u.unit_id
            order by abs(coalesce(j.population, 0) - coalesce(u.population_or_enrollment, 0)), j.jurisdiction_id
        ) as rn
    from units u
    join jur j
      on u.unit_type in ('municipality', 'township')
     and j.jurisdiction_type in ('city', 'town')
     and j.state_code = u.state_code
     and j.base_name = u.base_name
),

by_name as (
    select survey_year, unit_id, jurisdiction_id,
           case when n_cands = 1 then 0.95 else 0.60 end::numeric(3,2) as match_confidence, rn
    from named
    where rn = 1
),

all_matches as (
    select * from by_geo
    union all
    select * from by_name
),

dedup as (
    select
        survey_year, unit_id, jurisdiction_id, match_confidence,
        row_number() over (partition by survey_year, jurisdiction_id order by match_confidence desc, unit_id) as jr
    from all_matches
)

select survey_year, unit_id, jurisdiction_id, match_confidence
from dedup
where jr = 1
