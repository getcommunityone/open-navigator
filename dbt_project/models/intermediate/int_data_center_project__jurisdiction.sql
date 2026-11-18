{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    Governments a data center project sits in (#531). Grain: one row per
    (project_id, jurisdiction_id). basis, strongest first:
      stated_city            a curated project's city or town, matched by name and state
                             in jurisdiction_county_crosswalk;
      meeting_source_survey  } an Epoch site's link from int_data_center_site__jurisdiction
      address_city           } (#445), carried to the project that holds the site;
      address_county         }
      stated_county          a curated project's county (by name and state), or the county
                             that contains its stated city.
*/

with projects as (
    select project_id, data_center_site_id, city, county, state_code
    from {{ ref('int_data_center_project__base') }}
),

jurisdictions as (
    select jurisdiction_id, geoid, name, state_code, jurisdiction_type
    from {{ ref('jurisdictions') }}
),

city_places as (
    select p.project_id, x.geoid, x.county_fips, x.state_code
    from projects as p
    inner join {{ ref('jurisdiction_county_crosswalk') }} as x
        on x.state_code = p.state_code and lower(x.name) = lower(p.city)
    where p.city is not null
),

links as (
    select c.project_id, j.jurisdiction_id, 1 as basis_rank, 'stated_city' as basis
    from city_places as c
    inner join jurisdictions as j
        on j.geoid = c.geoid and j.state_code = c.state_code and j.jurisdiction_type in ('city', 'town')
    union all
    select p.project_id, l.jurisdiction_id,
           case l.link_basis when 'meeting_source_survey' then 2 when 'address_city' then 3 else 5 end,
           l.link_basis
    from projects as p
    inner join {{ ref('int_data_center_site__jurisdiction') }} as l on l.data_center_site_id = p.data_center_site_id
    union all
    select c.project_id, j.jurisdiction_id, 4, 'stated_county'
    from city_places as c
    inner join jurisdictions as j on j.geoid = c.county_fips and j.jurisdiction_type = 'county'
    union all
    select p.project_id, j.jurisdiction_id, 4, 'stated_county'
    from projects as p
    inner join jurisdictions as j
        on j.state_code = p.state_code and j.jurisdiction_type = 'county'
       and lower(j.name) = lower(p.county)
    where p.county is not null
)

select distinct on (project_id, jurisdiction_id)
    md5(project_id || '|' || jurisdiction_id)::text as project_jurisdiction_id,
    project_id::text                                as project_id,
    jurisdiction_id::text                           as jurisdiction_id,
    basis::text                                     as basis
from links
order by project_id, jurisdiction_id, basis_rank
