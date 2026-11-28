{{ config(
    materialized='table',
    tags=['intermediate', 'bodies'],
    indexes=[{'columns': ['jurisdiction_id', 'body_key'], 'type': 'btree'}]
) }}

/*
    int_body_member__candidate (#1443): every known seat on a governing body, before it is tied to governing_body.
    Grain: one row per source x body x member x role.

    Sources, in order of trust:
      officials       person_government (office 'government', with a place) and its terms (person_government_term):
                      mayors and council members on the place's own governing body. Rows from the council roster
                      scraper (person_id 'ocd-membership/scraped-...') say source 'council_roster'.
      legistar        current Legistar office records (stg_legistar__office_record); the body name is resolved with
                      the same title rules as meetings (macros/governing_body_title.sql). The member is tied to a
                      person_government row only on an exact name key in the same place.
      openstates      state legislators' chamber seats (stg_openstates__chamber_member) on two chamber bodies at the
                      state jurisdiction, tied to the legislator mart.
    Roles: body_role() over the title (seeds/body_role_rule.csv). Nothing here comes from speech.
*/

with jur as (
    select jurisdiction_id, name, jurisdiction_type, state_code, state_name
    from {{ ref('jurisdictions') }}
),

official as (
    select
        p.person_id,
        p.full_name,
        p.title,
        p.district,
        p.jurisdiction_id,
        coalesce(p.is_current, true) as is_current,
        j.jurisdiction_type
    from {{ ref('person_government') }} as p
    join jur as j on j.jurisdiction_id = p.jurisdiction_id
    where p.office = 'government'
      and p.full_name is not null
),

term as (
    select distinct on (t.person_id, {{ body_role('t.role') }})
        t.person_id,
        t.role,
        {{ body_role('t.role') }} as role_key,
        t.district,
        coalesce(t.start_date, make_date(t.start_year, 1, 1)) as start_date,
        coalesce(t.end_date, make_date(t.end_year, 12, 31)) as end_date,
        t.source_url
    from {{ ref('person_government_term') }} as t
    where t.person_id in (select person_id from official)
      and t.role is not null
      -- A state-wide role (governor) is not a seat on a local body.
      and {{ body_role('t.role') }} not in ('legislator')
    order by t.person_id, {{ body_role('t.role') }},
             (t.term_source = 'seed') desc, (t.end_date is null) desc, t.start_date desc nulls last, t.verified_on desc nulls last
),

official_seat as (
    -- Roles from terms where the person has any; else the title on the official row.
    select
        o.person_id, o.full_name, o.jurisdiction_id, o.jurisdiction_type,
        t.role as role_title, t.role_key as role, coalesce(t.district, o.district) as district,
        t.start_date, t.end_date, t.source_url,
        o.is_current and (t.end_date is null or t.end_date >= current_date) as is_current
    from official as o
    join term as t on t.person_id = o.person_id
    union all
    select
        o.person_id, o.full_name, o.jurisdiction_id, o.jurisdiction_type,
        o.title, {{ body_role('o.title') }}, o.district,
        cast(null as date), cast(null as date), cast(null as text),
        o.is_current
    from official as o
    where not exists (select 1 from term as t where t.person_id = o.person_id)
),

officials as (
    select
        s.jurisdiction_id,
        case when s.jurisdiction_type = 'school_district' then 'school_board' else 'governing_body' end as body_key,
        cast(null as text)                       as body_name,
        case when s.jurisdiction_type = 'school_district' then 'school_board'
             when s.jurisdiction_type = 'county' then 'county_commission'
             else 'council' end                  as body_type,
        s.full_name                              as member_name,
        s.person_id,
        cast(null as text)                       as legislator_person_uid,
        s.role,
        s.role_title,
        s.district,
        s.start_date,
        s.end_date,
        s.is_current,
        case when s.person_id like 'ocd-membership/scraped-%' then 'council_roster' else 'officials' end as source,
        s.source_url,
        0.95::numeric(3, 2)                      as confidence
    from official_seat as s
),

legistar_rec as (
    select
        r.*,
        j.name as jurisdiction_name,
        {{ body_jurisdiction_kind('j.jurisdiction_type') }} as kind,
        {{ clean_meeting_title_for_body('r.body_name', 'j.name') }} as cleaned
    from {{ ref('stg_legistar__office_record') }} as r
    join jur as j on j.jurisdiction_id = r.jurisdiction_id
    where r.body_name is not null
),

legistar_body as (
    {{ resolve_governing_body('legistar_rec') }}
),

official_key as (
    select o.jurisdiction_id, {{ person_name_key('o.full_name') }} as name_key, min(o.person_id) as person_id,
           count(distinct o.person_id) as n
    from official as o
    group by 1, 2
),

legistar as (
    select
        r.jurisdiction_id,
        coalesce(b.body_key, 'board:' || {{ body_slug("coalesce(nullif(r.cleaned, ''), lower(r.body_name))") }}) as body_key,
        coalesce(b.body_name, r.body_name)       as body_name,
        coalesce(b.body_type, 'board')           as body_type,
        r.full_name                              as member_name,
        case when k.n = 1 then k.person_id end   as person_id,
        cast(null as text)                       as legislator_person_uid,
        {{ body_role("coalesce(r.title, r.member_type)") }} as role,
        coalesce(r.title, r.member_type)         as role_title,
        cast(null as text)                       as district,
        r.start_date,
        r.end_date,
        (r.end_date is null or r.end_date >= current_date) as is_current,
        'legistar'::text                         as source,
        r.source_url,
        0.95::numeric(3, 2)                      as confidence
    from legistar_rec as r
    left join legistar_body as b on b.cleaned = r.cleaned and b.kind = r.kind
    left join official_key as k
        on k.jurisdiction_id = r.jurisdiction_id and k.name_key = {{ person_name_key('r.full_name') }}
),

openstates as (
    select
        j.jurisdiction_id,
        'legislature_' || c.chamber              as body_key,
        j.state_name || ' ' || case
            when c.chamber_name = 'House' then 'House of Representatives'
            when c.chamber_name is not null then c.chamber_name
            when c.chamber = 'upper' then 'Senate'
            else 'House of Representatives' end  as body_name,
        'legislature_chamber'::text              as body_type,
        c.full_name                              as member_name,
        cast(null as text)                       as person_id,
        l.person_uid                             as legislator_person_uid,
        'legislator'::text                       as role,
        case when c.chamber = 'upper' then 'Senator' else 'Representative' end as role_title,
        c.district,
        c.start_date,
        c.end_date,
        true                                     as is_current,
        'openstates'::text                       as source,
        cast(null as text)                       as source_url,
        0.95::numeric(3, 2)                      as confidence
    from {{ ref('stg_openstates__chamber_member') }} as c
    join jur as j on j.jurisdiction_type = 'state' and j.state_code = c.state_code
    left join {{ ref('legislator') }} as l
        on l.person_uid = md5('bronze_jurisdiction_openstates|' || c.ocd_person_id)
)

select * from officials
union all
select * from legistar
union all
select * from openstates
