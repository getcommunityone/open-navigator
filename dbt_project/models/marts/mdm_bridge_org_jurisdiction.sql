{{ config(materialized='table') }}

/*
    Mart (MDM): organization <-> jurisdiction, as a many-to-many bridge across
    three geographic tiers (state, city, county). This is the join that makes
    location-scoped search ("organizations in Tuscaloosa") possible.

    Grain: one row per (master_org_id, jurisdiction_id).

    Three tiers, UNION ALL'd:
      - STATE  : org.state_code -> jurisdictions where jurisdiction_type='state'
                 (the state jurisdiction_id IS the 2-letter state_code).
                 match_method='state_code'. Always is_dominant.
      - CITY   : normalize(org.city_norm)+state_code -> jurisdictions
                 (jurisdiction_type in ('city','town')). match_method=
                 'city_name_state'. One best row per org (prefer 'city' over
                 'town', then larger population), marked is_dominant.
      - COUNTY : org.zip5 -> HUD bronze_jurisdictions_zip_county -> the county
                 jurisdiction (zc.county = j.geoid, zc.usps_zip_pref_state =
                 j.state_code). A ZIP can straddle counties, so every candidate
                 county is kept; allocation_ratio = HUD tot_ratio and is_dominant
                 marks the largest-share county per org. match_method='zip5_hud'.
                 Only orgs with a zip5 get a county tier (partial by design).

    allocation_ratio is populated only for the county tier (NULL elsewhere).
*/

with org as (
    select
        master_org_id,
        city_norm,
        state_code,
        {{ zip5('zip5') }} as zip5
    from {{ ref('mdm_organization') }}
),

-- ---- jurisdiction slices ------------------------------------------------
state_juris as (
    select jurisdiction_id, state_code
    from {{ ref('jurisdictions') }}
    where jurisdiction_type = 'state'
),

city_juris as (
    select
        jurisdiction_id,
        {{ normalize_jurisdiction_label_for_match('name') }} as name_norm,
        state_code,
        jurisdiction_type,
        coalesce(population, 0) as population
    from {{ ref('jurisdictions') }}
    where jurisdiction_type in ('city', 'town')
),

county_juris as (
    select jurisdiction_id, geoid, state_code
    from {{ ref('jurisdictions') }}
    where jurisdiction_type = 'county'
),

zip_county as (
    select
        zip,
        county,
        usps_zip_pref_state,
        tot_ratio
    from {{ source('bronze', 'bronze_jurisdictions_zip_county') }}
),

-- ---- STATE tier ---------------------------------------------------------
state_tier as (
    select
        o.master_org_id,
        s.jurisdiction_id,
        'state'         as jurisdiction_level,
        'state_code'    as match_method,
        null::numeric   as allocation_ratio,
        true            as is_dominant
    from org o
    join state_juris s on s.state_code = o.state_code
    where o.state_code is not null
),

-- ---- CITY tier ----------------------------------------------------------
city_candidates as (
    select
        o.master_org_id,
        c.jurisdiction_id,
        c.jurisdiction_type,
        c.population,
        row_number() over (
            partition by o.master_org_id
            order by
                case c.jurisdiction_type when 'city' then 1 else 2 end,
                c.population desc,
                c.jurisdiction_id
        ) as rn
    from org o
    join city_juris c
      on c.name_norm = {{ normalize_jurisdiction_label_for_match('o.city_norm') }}
     and c.state_code = o.state_code
    where o.city_norm is not null
      and o.state_code is not null
),

city_tier as (
    select
        master_org_id,
        jurisdiction_id,
        'city'              as jurisdiction_level,
        'city_name_state'   as match_method,
        null::numeric       as allocation_ratio,
        true                as is_dominant
    from city_candidates
    where rn = 1
),

-- ---- COUNTY tier --------------------------------------------------------
county_candidates as (
    select
        o.master_org_id,
        cj.jurisdiction_id,
        zc.tot_ratio,
        zc.tot_ratio = max(zc.tot_ratio) over (partition by o.master_org_id) as is_dominant
    from org o
    join zip_county zc on zc.zip = o.zip5
    join county_juris cj
      on cj.geoid = zc.county
     and cj.state_code = zc.usps_zip_pref_state
    where o.zip5 is not null
),

county_tier as (
    -- A ZIP row can repeat a (org, county) pair only once given the HUD grain,
    -- but distinct on guards the bridge PK against any source fan-out.
    select distinct on (master_org_id, jurisdiction_id)
        master_org_id,
        jurisdiction_id,
        'county'        as jurisdiction_level,
        'zip5_hud'      as match_method,
        tot_ratio       as allocation_ratio,
        is_dominant
    from county_candidates
    order by master_org_id, jurisdiction_id, tot_ratio desc nulls last
),

combined as (
    select * from state_tier
    union all
    select * from city_tier
    union all
    select * from county_tier
)

select
    md5(master_org_id || '|' || jurisdiction_id)    as org_jurisdiction_id,
    master_org_id,
    jurisdiction_id,
    jurisdiction_level,
    match_method,
    allocation_ratio,
    is_dominant
from combined
