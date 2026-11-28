{{ config(
    materialized='table',
    on_schema_change='fail',
    contract={'enforced': true},
    tags=['marts', 'bodies', 'api'],
    indexes=[
      {'columns': ['governing_body_id'], 'unique': True},
      {'columns': ['jurisdiction_id'], 'type': 'btree'}
    ]
) }}

/*
    governing_body (#1442): the bodies that govern a place, one row per jurisdiction x body.

    From meetings (int_meeting_body__matched: YouTube titles and the AI body name, Legistar/Granicus body fields,
    scraped agenda/minutes body names) and from official rosters (person_government: a place with a mayor or
    council members has a governing body even before we hold any of its meetings).

    body_name: the multi-word name most meetings use for the body (ties: the longer name), else a default for the
    body type.
    meeting_count: distinct meeting dates on file (re-uploads and the same meeting from two sources count once);
    undated meetings count once each.
    is_primary: the place's own legislative body (city council / county commission / a school district's board).
    Design: web_docs/docs/development/governing-bodies.md
*/

with meeting as (
    select * from {{ ref('int_meeting_body__matched') }}
),

jur as (
    select jurisdiction_id, name, jurisdiction_type, state_code, state_name
    from {{ ref('jurisdictions') }}
),

meeting_body_stats as (
    select
        m.jurisdiction_id,
        m.body_key,
        count(distinct coalesce(m.meeting_date::text, m.source || ':' || m.source_key)) as meeting_count,
        min(m.meeting_date)                                                   as first_meeting_date,
        max(m.meeting_date)                                                   as last_meeting_date,
        string_agg(distinct m.source, ',' order by m.source)                  as sources
    from meeting as m
    group by m.jurisdiction_id, m.body_key
),

name_vote as (
    select distinct on (m.jurisdiction_id, m.body_key)
        m.jurisdiction_id,
        m.body_key,
        m.body_name
    from meeting as m
    where m.body_name is not null
    group by m.jurisdiction_id, m.body_key, m.body_name
    -- A multi-word name ("City Council") beats a bare one ("Council") some sources use.
    order by m.jurisdiction_id, m.body_key, (position(' ' in m.body_name) > 0) desc, count(*) desc,
             length(m.body_name) desc, m.body_name
),

type_vote as (
    select distinct on (m.jurisdiction_id, m.body_key)
        m.jurisdiction_id,
        m.body_key,
        m.body_type
    from meeting as m
    group by m.jurisdiction_id, m.body_key, m.body_type
    order by m.jurisdiction_id, m.body_key, count(*) desc, m.body_type
),

-- A place whose officials include a mayor or council members has a governing body, meetings or not.
roster_body as (
    select distinct
        p.jurisdiction_id,
        case when j.jurisdiction_type = 'school_district' then 'school_board' else 'governing_body' end as body_key
    from {{ ref('person_government') }} as p
    join jur as j on j.jurisdiction_id = p.jurisdiction_id
    where p.jurisdiction_id is not null
      and coalesce(p.is_current, true)
      and p.title ~* '(mayor|council|alder|commission|selectm|select board|trustee|supervisor|board member)'
),

body as (
    select jurisdiction_id, body_key from meeting_body_stats
    union
    select jurisdiction_id, body_key from roster_body
)

select
    md5(b.jurisdiction_id || '|' || b.body_key)::text                       as governing_body_id,
    b.jurisdiction_id::text                                                  as jurisdiction_id,
    j.state_code::text                                                       as state_code,
    j.state_name::text                                                       as state,
    b.body_key::text                                                         as body_key,
    coalesce(
        nv.body_name,
        case
            when b.body_key = 'school_board' then 'Board of Education'
            when b.body_key = 'governing_body' and j.jurisdiction_type = 'county' then 'County Commission'
            when b.body_key = 'governing_body' and j.jurisdiction_type = 'town' then 'Town Council'
            when b.body_key = 'governing_body' then 'City Council'
        end,
        initcap(replace(b.body_key, '_', ' '))
    )::text                                                                  as body_name,
    coalesce(
        tv.body_type,
        case
            when b.body_key = 'school_board' then 'school_board'
            when j.jurisdiction_type = 'county' then 'county_commission'
            else 'council'
        end
    )::text                                                                  as body_type,
    (b.body_key = 'governing_body'
        or (b.body_key = 'school_board' and j.jurisdiction_type = 'school_district'))::boolean as is_primary,
    coalesce(s.meeting_count, 0)::integer                                    as meeting_count,
    s.first_meeting_date::date                                               as first_meeting_date,
    s.last_meeting_date::date                                                as last_meeting_date,
    concat_ws(',', s.sources, case when r.body_key is not null then 'roster' end)::text as sources
from body as b
join jur as j on j.jurisdiction_id = b.jurisdiction_id
left join meeting_body_stats as s on s.jurisdiction_id = b.jurisdiction_id and s.body_key = b.body_key
left join name_vote as nv on nv.jurisdiction_id = b.jurisdiction_id and nv.body_key = b.body_key
left join type_vote as tv on tv.jurisdiction_id = b.jurisdiction_id and tv.body_key = b.body_key
left join roster_body as r on r.jurisdiction_id = b.jurisdiction_id and r.body_key = b.body_key
