{{ config(
    materialized='table',
    tags=['intermediate', 'bodies'],
    indexes=[
      {'columns': ['jurisdiction_id', 'body_key'], 'type': 'btree'},
      {'columns': ['video_id'], 'type': 'btree'}
    ]
) }}

/*
    int_meeting_body__matched (#1442): every meeting we hold, with the governing body its title or body field names.
    Grain: one row per meeting that matched a body (source + source_key unique).

    Meetings:
      youtube   event_youtube_with_jurisdiction (videos with a jurisdiction), minus videos the meeting-kind screen
                says are not a public meeting. Text tried: the video title, then event_meeting.body_name (AI).
      platform  platform_meeting (Legistar Web API, Granicus). Text tried: the platform's body name, then the title.
      document  event_meeting_document (scraped SuiteOne/CivicPlus agendas and minutes), one meeting per
                jurisdiction x date x body name. Text tried: the body name, then the meeting title.

    Matching: clean_meeting_title_for_body (macros/governing_body_title.sql), then the first seed pattern
    (seeds/governing_body_pattern.csv, by priority) whose applies_to fits the jurisdiction. The first text that
    names a body wins. __skip__ (a county body in a city's video) and no match leave the meeting out.
    Python twin for tests: ingestion.governance.body_titles.
*/

with event_meeting_one as (
    select distinct on (em.video_id)
        em.video_id,
        em.event_meeting_id,
        em.body_name
    from {{ ref('event_meeting') }} as em
    where em.video_id is not null
    order by em.video_id, em.event_meeting_id
),

not_meeting as (
    select k.video_id
    from {{ ref('meeting_video_kind') }} as k
    where k.is_public_meeting = false
),

youtube as (
    select
        'youtube'::text                                     as source,
        y.video_id::text                                    as source_key,
        y.video_id::text                                    as video_id,
        cast(null as text)                                  as platform_meeting_id,
        em.event_meeting_id::integer                        as event_meeting_id,
        y.jurisdiction_id::text                             as jurisdiction_id,
        y.title::text                                       as meeting_title,
        coalesce(y.event_date, y.published_at::date)        as meeting_date,
        y.video_url::text                                   as video_url,
        y.title::text                                       as text_1,
        'title'::text                                       as text_1_kind,
        em.body_name::text                                  as text_2,
        'body_name'::text                                   as text_2_kind
    from {{ ref('event_youtube_with_jurisdiction') }} as y
    left join event_meeting_one as em on em.video_id = y.video_id
    where y.jurisdiction_id is not null
      and y.video_id is not null
      and y.video_id not in (select video_id from not_meeting)
),

platform as (
    select
        'platform'::text,
        p.platform_meeting_id::text,
        cast(null as text),
        p.platform_meeting_id::text,
        cast(null as integer),
        p.jurisdiction_id::text,
        coalesce(p.title, p.body_name)::text,
        p.meeting_date,
        p.video_url::text,
        p.body_name::text,
        'platform_body'::text,
        p.title::text,
        'title'::text
    from {{ ref('platform_meeting') }} as p
    where p.jurisdiction_id is not null
),

document as (
    select
        'document'::text,
        md5(d.jurisdiction_id || '|' || coalesce(d.doc_date::text, '') || '|'
            || coalesce(d.body_name, d.meeting_title, ''))::text,
        cast(null as text),
        cast(null as text),
        min(d.event_meeting_id)::integer,
        d.jurisdiction_id::text,
        coalesce(min(d.meeting_title), min(d.body_name))::text,
        d.doc_date,
        cast(null as text),
        d.body_name::text,
        'document_body'::text,
        min(d.meeting_title)::text,
        'title'::text
    from {{ ref('event_meeting_document') }} as d
    where d.jurisdiction_id is not null
      and coalesce(d.body_name, d.meeting_title) is not null
    group by d.jurisdiction_id, d.doc_date, d.body_name, coalesce(d.body_name, d.meeting_title, '')
),

meeting as (
    select * from youtube
    union all
    select * from platform
    union all
    select * from document
),

placed as (
    select
        m.*,
        j.name                                              as jurisdiction_name,
        {{ body_jurisdiction_kind('j.jurisdiction_type') }} as kind
    from meeting as m
    join {{ ref('jurisdictions') }} as j on j.jurisdiction_id = m.jurisdiction_id
),

candidate as (
    select p.source, p.source_key, 1 as rank, p.text_1_kind as matched_on, p.kind,
           {{ clean_meeting_title_for_body('p.text_1', 'p.jurisdiction_name') }} as cleaned
    from placed as p
    where nullif(btrim(p.text_1), '') is not null
    union all
    select p.source, p.source_key, 2, p.text_2_kind, p.kind,
           {{ clean_meeting_title_for_body('p.text_2', 'p.jurisdiction_name') }}
    from placed as p
    where nullif(btrim(p.text_2), '') is not null
),

resolved as (
    {{ resolve_governing_body('candidate') }}
),

best as (
    select distinct on (c.source, c.source_key)
        c.source,
        c.source_key,
        c.matched_on,
        r.pattern_id,
        r.body_key,
        r.body_type,
        r.body_name
    from candidate as c
    join resolved as r on r.cleaned = c.cleaned and r.kind = c.kind
    order by c.source, c.source_key, c.rank
)

select
    p.source,
    p.source_key,
    p.video_id,
    p.platform_meeting_id,
    p.event_meeting_id,
    p.jurisdiction_id,
    p.kind                as jurisdiction_kind,
    p.meeting_title,
    p.meeting_date,
    p.video_url,
    b.matched_on,
    b.pattern_id,
    b.body_key,
    b.body_type,
    b.body_name
from placed as p
join best as b on b.source = p.source and b.source_key = p.source_key
