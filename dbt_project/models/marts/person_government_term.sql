{{ config(materialized='table', tags=['marts', 'person', 'officials', 'serving']) }}

/*
    Office terms (#1068): who held which seat, when, and why they left. Grain: one row per (official, role, district,
    source, term). Three sources, kept side by side and labelled by term_source:

      seed             official_term: terms stated on the government's own page (Tuscaloosa first). Dates are given
                       to the day when the page states a day, else only the year. end_reason is what the page says
                       ('died' only when an official source says so).
      openstates       stg_openstates__official membership start/end dates (legislators). An ended membership's reason
                       isn't in the source, so end_reason is 'unknown'.
      roster_snapshot  officials_roster_snapshot: each version of a local official's roster row while marked current.
                       first_seen_on / last_seen_on are when we saw it, NOT term dates; start_date/end_date stay null.

    Only officials present in person_government are kept, so person_id is always a valid FK. Nothing is estimated.
*/

with people as (
    select person_id, full_name, state_code, jurisdiction from {{ ref('person_government') }}
),

seed_terms as (
    select
        p.person_id,
        s.role::text                                                    as role,
        nullif(btrim(s.district), '')::text                             as district,
        s.jurisdiction::text                                            as jurisdiction,
        s.state_code::text                                              as state_code,
        s.start_date::date                                              as start_date,
        coalesce(s.start_year::int, extract(year from s.start_date::date)::int) as start_year,
        s.end_date::date                                                as end_date,
        coalesce(s.end_year::int, extract(year from s.end_date::date)::int)     as end_year,
        nullif(btrim(s.end_reason), '')::text                           as end_reason,
        'seed'::text                                                    as term_source,
        s.source_url::text                                              as source_url,
        s.verified_on::date                                             as verified_on,
        null::date                                                      as first_seen_on,
        null::date                                                      as last_seen_on
    from {{ ref('official_term') }} as s
    inner join people as p
        on lower(btrim(p.full_name)) = lower(btrim(s.full_name))
       and p.state_code = s.state_code
       and lower(btrim(p.jurisdiction)) = lower(btrim(s.jurisdiction))
),

openstates_terms as (
    select
        o.ocd_membership_id::text                                       as person_id,
        o.title::text                                                   as role,
        o.district::text                                                as district,
        o.jurisdiction::text                                            as jurisdiction,
        o.state_code::text                                              as state_code,
        o.start_date                                                    as start_date,
        extract(year from o.start_date)::int                            as start_year,
        o.end_date                                                      as end_date,
        extract(year from o.end_date)::int                              as end_year,
        case when o.end_date is not null and o.end_date < current_date then 'unknown' end::text as end_reason,
        'openstates'::text                                              as term_source,
        null::text                                                      as source_url,
        o.synced_at::date                                               as verified_on,
        null::date                                                      as first_seen_on,
        null::date                                                      as last_seen_on
    from {{ ref('stg_openstates__official') }} as o
    inner join people as p on p.person_id = o.ocd_membership_id
    where o.start_date is not null or o.end_date is not null
),

snapshot_terms as (
    select
        r.id::text                                                      as person_id,
        r.title::text                                                   as role,
        r.district::text                                                as district,
        r.jurisdiction::text                                            as jurisdiction,
        r.state_code::text                                              as state_code,
        null::date                                                      as start_date,
        null::int                                                       as start_year,
        null::date                                                      as end_date,
        null::int                                                       as end_year,
        null::text                                                      as end_reason,
        'roster_snapshot'::text                                         as term_source,
        null::text                                                      as source_url,
        null::date                                                      as verified_on,
        r.dbt_valid_from::date                                          as first_seen_on,
        r.dbt_valid_to::date                                            as last_seen_on
    from {{ ref('officials_roster_snapshot') }} as r
    inner join people as p on p.person_id = r.id
    where r.is_current
),

unioned as (
    select * from seed_terms
    union all select * from openstates_terms
    union all select * from snapshot_terms
)

select distinct on (person_government_term_id)
    md5(
        person_id || '|' || role || '|' || coalesce(district, '') || '|' || term_source || '|'
        || coalesce(start_date::text, start_year::text, first_seen_on::text, '')
    )::text                                                             as person_government_term_id,
    person_id, role, district, jurisdiction, state_code,
    start_date, start_year, end_date, end_year, end_reason,
    term_source, source_url, verified_on, first_seen_on, last_seen_on
from unioned
where role is not null
order by person_government_term_id, verified_on desc nulls last
