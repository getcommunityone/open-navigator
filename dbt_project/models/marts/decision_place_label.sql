{{ config(materialized='table', tags=['marts', 'event-extraction', 'data_centers', 'serving']) }}

/*
    Where a decision is, when we can say so safely (#508). Grain: one row per
    event_decision_id that gets a place label. A decision with no row shows no place.

    Places come from the decision's own reference graph: its primary_place_id, resolved in
    event_place_geocoded within the same analysis_id (the latest extraction of that place).
    When the decision has no primary place, a non-primary ref is used only if it is the
    decision's single street-level ref, so an address read out in public comment isn't
    shown as the subject.

    A place is labelled only when ALL of these hold:
      1. It is street-level: a street_address that starts with a house number and names a
         road, or an intersection / corridor that names a road (named_road_regex).
         Jurisdiction-wide, county, facility and vague places ("industrial corridor") never
         are, which keeps speech-to-text county names such as "Dicab County", "Brooks
         County" or "Sum County" off the page.
      2. Its state agrees: place_state_code is null or equals the state of the decision's
         own government (int_event_decision__jurisdiction).
      3. Its city does not contradict: place_city is null, or is that government, or (for a
         county) is a place inside that county in jurisdiction_county_crosswalk.
      4. Its address agrees positively (agreement_basis):
           place_city               place_city is the government (a city or town);
           city_in_county           place_city is a place inside the county;
           address_names_jurisdiction  a comma-separated part of the address is the
                                    government's name ("Tomachici Road, Spalding County, GA").
    No geocode-inside-boundary test: the warehouse holds no jurisdiction polygons, so the
    check is on the address text alone.
*/

{%- set road = named_road_regex() %}

with decisions as (
    select distinct on (event_decision_id)
        event_decision_id,
        analysis_id,
        nullif(btrim(primary_place_id), '') as primary_place_id,
        place_refs
    from {{ ref('event_decision') }}
    order by event_decision_id, extracted_at desc
),

places as (
    select distinct on (analysis_id, place_id)
        analysis_id,
        place_id,
        place_type,
        raw_text,
        normalized_address,
        street_address,
        place_city,
        place_state_code,
        latitude,
        longitude
    from {{ ref('event_place_geocoded') }}
    order by analysis_id, place_id, extracted_at desc
),

refs as (
    select d.event_decision_id, d.analysis_id, r.place_id, (r.place_id = d.primary_place_id) as is_primary,
           d.primary_place_id is null as has_no_primary
    from decisions as d
    cross join lateral (
        select jsonb_array_elements_text(coalesce(d.place_refs, '[]'::jsonb)) as place_id
        union
        select d.primary_place_id where d.primary_place_id is not null
    ) as r
    where nullif(btrim(r.place_id), '') is not null
),

street_level as (
    select
        r.event_decision_id,
        r.is_primary,
        r.has_no_primary,
        p.*,
        coalesce(nullif(btrim(p.normalized_address), ''), nullif(btrim(p.raw_text), '')) as label_text
    from refs as r
    inner join places as p on p.analysis_id = r.analysis_id and p.place_id = r.place_id
    where (
            p.place_type = 'street_address'
        and coalesce(p.street_address, p.normalized_address, p.raw_text) ~ '^\s*\d+'
        and coalesce(p.street_address, p.normalized_address, p.raw_text) ~* '{{ road }}'
    ) or (
            p.place_type in ('intersection', 'corridor')
        and coalesce(p.raw_text, p.normalized_address) ~* '{{ road }}'
    )
),

candidates as (
    select s.*
    from street_level as s
    where s.is_primary
    union all
    -- no primary place: only a decision's single street-level ref
    select s.*
    from street_level as s
    where s.has_no_primary
      and 1 = (select count(*) from street_level as x where x.event_decision_id = s.event_decision_id)
),

judged as (
    select
        c.*,
        j.jurisdiction_id,
        j.jurisdiction_name,
        j.jurisdiction_type,
        j.state_code,
        lower(btrim(c.place_city)) = lower(j.jurisdiction_name)                as city_is_jurisdiction,
        (j.jurisdiction_type = 'county' and exists (
            select 1 from {{ ref('jurisdiction_county_crosswalk') }} as x
            where x.state_code = j.state_code
              and x.county_fips = j.jurisdiction_geoid
              and lower(x.name) = lower(btrim(c.place_city))
        ))                                                                      as city_in_county,
        c.label_text ~* ('(^|,)\s*' || {{ regex_escape('j.jurisdiction_name') }} || '\s*(,|$)') as address_names_jurisdiction
    from candidates as c
    inner join {{ ref('int_event_decision__jurisdiction') }} as j on j.event_decision_id = c.event_decision_id
),

agreeing as (
    select
        *,
        case
            when city_is_jurisdiction and jurisdiction_type <> 'county' then 'place_city'
            when city_in_county then 'city_in_county'
            when address_names_jurisdiction then 'address_names_jurisdiction'
        end as agreement_basis
    from judged
    where (place_state_code is null or upper(btrim(place_state_code)) = state_code)
      and (nullif(btrim(place_city), '') is null
           or city_is_jurisdiction
           or city_in_county)
)

select distinct on (event_decision_id)
    event_decision_id::text              as event_decision_id,
    state_code::text                     as state_code,
    jurisdiction_id::text                as jurisdiction_id,
    place_id::text                       as place_id,
    place_type::text                     as place_type,
    label_text::text                     as place_label,
    agreement_basis::text                as agreement_basis,
    latitude::double precision           as latitude,
    longitude::double precision          as longitude
from agreeing
where agreement_basis is not null
order by event_decision_id, is_primary desc, place_id
