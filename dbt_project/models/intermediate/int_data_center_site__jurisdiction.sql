{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    Governments near each data center site (#445). Grain: one row per
    (data_center_site_id, jurisdiction_id).

    Three ways a government is linked, strongest first (link_basis):
      meeting_source_survey  bronze.bronze_jurisdiction_meeting_source names the site for the
                             government (the #460/#464 survey of who governs around each site).
                             Skipped when that table doesn't exist yet.
      address_city           the city or town in the site's Epoch address, matched by name and
                             state in jurisdiction_county_crosswalk.
      address_county         the county that contains that city or town.
    Epoch gives a street address only, so a site whose address names no city we know links
    through the survey alone, or not at all.
*/

{%- set src = source('bronze', 'bronze_jurisdiction_meeting_source') -%}
{%- set survey_exists = execute and adapter.get_relation(
        database=src.database, schema=src.schema, identifier=src.identifier) is not none %}

with sites as (
    select
        data_center_site_id,
        state_code,
        btrim((regexp_match(address, '([^,]+),\s*(' || state_code || '|' || state || ')\M'))[1]) as address_city
    from (select * from {{ ref('data_center_site') }} where source = 'epoch')
    where state_code is not null and address is not null
),

jurisdictions as (
    select jurisdiction_id, geoid, state_code, jurisdiction_type
    from {{ ref('jurisdictions') }}
),

address_places as (
    select s.data_center_site_id, x.geoid, x.county_fips, x.state_code
    from sites as s
    inner join {{ ref('jurisdiction_county_crosswalk') }} as x
        on x.state_code = s.state_code
       and lower(x.name) = lower(s.address_city)
),

links as (
{%- if survey_exists %}
    select distinct
        b.data_center_site_id,
        b.jurisdiction_id,
        1 as basis_rank,
        'meeting_source_survey' as link_basis
    from {{ src }} as b
    where b.data_center_site_id is not null
    union all
{%- endif %}
    select p.data_center_site_id, j.jurisdiction_id, 2, 'address_city'
    from address_places as p
    inner join jurisdictions as j
        on j.geoid = p.geoid and j.state_code = p.state_code
       and j.jurisdiction_type in ('city', 'town')
    union all
    select p.data_center_site_id, j.jurisdiction_id, 3, 'address_county'
    from address_places as p
    inner join jurisdictions as j
        on j.geoid = p.county_fips and j.jurisdiction_type = 'county'
)

select distinct on (l.data_center_site_id, l.jurisdiction_id)
    l.data_center_site_id::text                as data_center_site_id,
    l.jurisdiction_id::text                    as jurisdiction_id,
    l.link_basis::text                         as link_basis
from links as l
inner join jurisdictions as j on j.jurisdiction_id = l.jurisdiction_id
inner join (select * from {{ ref('data_center_site') }} where source = 'epoch') as s on s.data_center_site_id = l.data_center_site_id
order by l.data_center_site_id, l.jurisdiction_id, l.basis_rank
