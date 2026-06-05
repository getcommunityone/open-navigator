{{
  config(
    materialized='table',
    post_hook=[
      "CREATE INDEX IF NOT EXISTS mdm_bridge_person_jurisdiction_jurisdiction_id_idx ON {{ this }} (jurisdiction_id)",
      "CREATE INDEX IF NOT EXISTS mdm_bridge_person_jurisdiction_person_uid_idx ON {{ this }} (person_uid)",
      "ALTER TABLE {{ this }} ADD CONSTRAINT mdm_bridge_person_jurisdiction_person_uid_fkey FOREIGN KEY (person_uid) REFERENCES {{ ref('mdm_person') }} (person_uid) NOT VALID",
      "ALTER TABLE {{ this }} ADD CONSTRAINT mdm_bridge_person_jurisdiction_jurisdiction_id_fkey FOREIGN KEY (jurisdiction_id) REFERENCES {{ ref('jurisdictions') }} (jurisdiction_id) NOT VALID"
    ]
  )
}}

-- FKs are added NOT VALID in the post_hook above (not via the contract `constraints`
-- block) on purpose: inline contract FKs validate every row against the parent during
-- the bulk INSERT (measured ~5 min for person_uid alone over 6.6M rows vs 13.8M-row
-- mdm_person). The bridge is built FROM these parents via ref(), so referential
-- integrity holds by construction; NOT VALID still enforces all FUTURE writes. The
-- ref()s in the SELECT keep dbt build order.

/*
    Mart (MDM): person <-> jurisdiction, as a many-to-many bridge across three
    geographic tiers (state, city, county). Person analogue of
    mdm_bridge_org_jurisdiction; makes location-scoped people search possible.

    Grain: one row per (person_uid, jurisdiction_id). person_uid is the
    mdm_person occurrence key (the same key mdm_bridge_person_address bridges on).

    Three tiers, UNION ALL'd:
      - STATE  : person.state_code -> jurisdictions where jurisdiction_type=
                 'state' (state jurisdiction_id IS the 2-letter state_code).
                 match_method='state_code'. Always is_dominant.
      - CITY   : normalize(person.city_norm)+state_code -> jurisdictions
                 (jurisdiction_type in ('city','town')). match_method=
                 'city_name_state'. One best row per person (prefer 'city' over
                 'town', then larger population), marked is_dominant.
      - COUNTY : person.zip5 -> HUD bronze_jurisdictions_zip_county -> county
                 jurisdiction (zc.county = j.geoid, zc.usps_zip_pref_state =
                 j.state_code). allocation_ratio = HUD tot_ratio; is_dominant
                 marks the largest-share county per person. match_method=
                 'zip5_hud'. mdm_person has no lat/lon, so county is zip5-only.

    allocation_ratio is populated only for the county tier (NULL elsewhere).
*/

with person as (
    select
        person_uid,
        city_norm,
        state_code,
        {{ zip5('zip5') }} as zip5
    from {{ ref('mdm_person') }}
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
        p.person_uid,
        s.jurisdiction_id,
        'state'         as jurisdiction_level,
        'state_code'    as match_method,
        null::numeric   as allocation_ratio,
        true            as is_dominant
    from person p
    join state_juris s on s.state_code = p.state_code
    where p.state_code is not null
),

-- ---- CITY tier ----------------------------------------------------------
city_candidates as (
    select
        p.person_uid,
        c.jurisdiction_id,
        c.jurisdiction_type,
        c.population,
        row_number() over (
            partition by p.person_uid
            order by
                case c.jurisdiction_type when 'city' then 1 else 2 end,
                c.population desc,
                c.jurisdiction_id
        ) as rn
    from person p
    join city_juris c
      on c.name_norm = {{ normalize_jurisdiction_label_for_match('p.city_norm') }}
     and c.state_code = p.state_code
    where p.city_norm is not null
      and p.state_code is not null
),

city_tier as (
    select
        person_uid,
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
        p.person_uid,
        cj.jurisdiction_id,
        zc.tot_ratio,
        zc.tot_ratio = max(zc.tot_ratio) over (partition by p.person_uid) as is_dominant
    from person p
    join zip_county zc on zc.zip = p.zip5
    join county_juris cj
      on cj.geoid = zc.county
     and cj.state_code = zc.usps_zip_pref_state
    where p.zip5 is not null
),

county_tier as (
    select distinct on (person_uid, jurisdiction_id)
        person_uid,
        jurisdiction_id,
        'county'        as jurisdiction_level,
        'zip5_hud'      as match_method,
        tot_ratio       as allocation_ratio,
        is_dominant
    from county_candidates
    order by person_uid, jurisdiction_id, tot_ratio desc nulls last
),

combined as (
    select * from state_tier
    union all
    select * from city_tier
    union all
    select * from county_tier
)

select
    md5(person_uid || '|' || jurisdiction_id)   as person_jurisdiction_id,
    person_uid,
    jurisdiction_id,
    jurisdiction_level,
    match_method,
    allocation_ratio,
    is_dominant
from combined
