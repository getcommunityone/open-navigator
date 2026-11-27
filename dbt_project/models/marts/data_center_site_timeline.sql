/*
    Data center sites over time (#1348). Grain: one row per data center site (PK data_center_site_id,
    FK -> data_center_site). It places each site in the year of its earliest real date on record and
    gives it the coordinates the sources publish, for the Data Center Story's "Over time" screen.

    Only real dates, never a guessed year:
      appear_year     the year of the site's earliest date on record:
                        announced     the US Data Center Registry's announced_date, at the precision it gives
                                      (day, month or year; appear_precision says which);
                        first_report  Epoch AI's first dated timeline row (satellite or permit evidence of work
                                      on the site), always a full date.
                      For an Epoch site that the registry also lists (data_center_site_source,
                      match_basis = 'epoch_same_name'), the earlier of the two. Null when the site has
                      neither: the page counts it as "no date on record", it is never placed at a guess.
      operating_year  Epoch only: the year of the first timeline row with a building operational (or, when
                      that count is blank, IT power above zero), the rule data_center_site uses for
                      'operating'. A year after today is Epoch's projection (operating_is_expected).
      first_report_year  Epoch only: the year of the first dated timeline row (work on the site is on record).
    The registry publishes no opening or completion date, so a registry site has no operating_year.

    The API reads a site's phase in a year from these: an Epoch site is planned before first_report_year,
    under construction from it, operating from operating_year; a registry site keeps its status today.

    Coordinates: the registry's own latitude/longitude; an Epoch site (street address only) takes its
    same-name registry record's, else null (listed, not mapped).
*/

with sites as (
    select data_center_site_id, source, site_name, state_code, state, latitude, longitude
    from {{ ref('data_center_site') }}
),

epoch_timeline as (
    select
        md5('epoch|' || name)::text as data_center_site_id,
        min(as_of_on)               as first_report_on,
        min(as_of_on) filter (
            where coalesce(buildings_operational, 0) > 0
               or (buildings_operational is null and coalesce(it_power_mw, 0) > 0)
        )                           as first_operating_on
    from {{ ref('stg_epoch_data_center_timeline') }}
    group by 1
),

-- Every registry record behind a site: its own site, or the Epoch site it is the same as.
registry as (
    select
        m.data_center_site_id,
        r.announced_year,
        r.announced_precision,
        r.latitude,
        r.longitude
    from {{ ref('int_data_center_facility_registry__site') }} as m
    inner join {{ ref('stg_data_center_facility_registry') }} as r on r.registry_id = m.registry_id
),

dated as (
    select
        s.data_center_site_id,
        s.state_code,
        s.state,
        coalesce(s.latitude, r.latitude)                  as latitude,
        coalesce(s.longitude, r.longitude)                as longitude,
        r.announced_year,
        r.announced_precision,
        extract(year from e.first_report_on)::int         as first_report_year,
        extract(year from e.first_operating_on)::int      as operating_year,
        (e.first_operating_on > current_date)             as operating_is_expected
    from sites as s
    left join registry as r on r.data_center_site_id = s.data_center_site_id
    left join epoch_timeline as e on e.data_center_site_id = s.data_center_site_id
)

select
    data_center_site_id::text                                                   as data_center_site_id,
    state_code::text                                                            as state_code,
    state::text                                                                 as state,
    latitude::double precision                                                  as latitude,
    longitude::double precision                                                 as longitude,
    (case
        when announced_year is not null and first_report_year is not null then least(announced_year, first_report_year)
        else coalesce(announced_year, first_report_year)
    end)::int                                                                   as appear_year,
    (case
        when announced_year is not null and (first_report_year is null or announced_year <= first_report_year) then 'announced'
        when first_report_year is not null then 'first_report'
    end)::text                                                                  as appear_basis,
    (case
        when announced_year is not null and (first_report_year is null or announced_year <= first_report_year) then announced_precision
        when first_report_year is not null then 'day'
    end)::text                                                                  as appear_precision,
    first_report_year::int                                                      as first_report_year,
    operating_year::int                                                         as operating_year,
    coalesce(operating_is_expected, false)::boolean                             as operating_is_expected
from dated
