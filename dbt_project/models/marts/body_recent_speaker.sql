{{ config(
    materialized='table',
    on_schema_change='fail',
    contract={'enforced': true},
    tags=['marts', 'bodies', 'speakers', 'api'],
    indexes=[
      {'columns': ['body_recent_speaker_id'], 'unique': True},
      {'columns': ['governing_body_id', 'last_heard_date'], 'type': 'btree'}
    ]
) }}

/*
    body_recent_speaker (#1444): officials heard in a body's recent meetings. Grain: one row per body x member heard
    in the last 18 months of that body's meetings (meeting_body). PK md5(governing_body_id | body_membership_id).

    Evidence, all tied to a roster (body_membership) of the meeting's place; nothing from speech alone:
      chair_call / roll_call / self_intro  bronze_meeting_official_mention (the chair names a roster member and the
                                           next turn starts, the member answers a roll call, or names themself)
      official_roster_match                meeting_speaker_intro rows whose speaker_kind is 'official' (an exact first
                                           and last name match to the place's officials)
    A member who sits on several bodies is shown with the membership on the place's primary body when they have one.
    Residents never appear: only body_membership rows can.

    last_moment_url: the YouTube recording at the moment of the most recent evidence (a few seconds early), when the
    meeting is on YouTube and the moment has a time.
*/

with meeting as (
    select mb.video_id, mb.governing_body_id, mb.jurisdiction_id, mb.meeting_date
    from {{ ref('meeting_body') }} as mb
    where mb.video_id is not null
      and mb.meeting_date >= current_date - interval '18 months'
),

membership as (
    select
        bm.*,
        g.is_primary,
        {{ person_name_key('bm.member_name') }} as name_key
    from {{ ref('body_membership') }} as bm
    join {{ ref('governing_body') }} as g on g.governing_body_id = bm.governing_body_id
    where g.body_type <> 'legislature_chamber'
),

-- One membership per person per place: the primary body first, a current seat first, a ranked role first.
member as (
    select distinct on (m.jurisdiction_id, coalesce(m.person_id, m.name_key))
        m.*
    from membership as m
    where m.name_key is not null
    order by m.jurisdiction_id, coalesce(m.person_id, m.name_key), m.is_primary desc, m.is_current desc,
             case m.role when 'mayor' then 1 when 'president' then 2 when 'president_pro_tem' then 3
                         when 'vice_mayor' then 4 when 'chair' then 5 when 'vice_chair' then 6 else 9 end
),

evidence as (
    select o.video_id, o.jurisdiction_id, o.person_id, o.member_name_key as name_key,
           o.start_seconds, o.pattern_id as attribution_method
    from {{ source('bronze', 'bronze_meeting_official_mention') }} as o
    union all
    select i.video_id, mt.jurisdiction_id, i.person_id, {{ person_name_key('i.speaker_display_name') }},
           i.start_seconds, 'official_roster_match'
    from {{ ref('meeting_speaker_intro') }} as i
    join meeting as mt on mt.video_id = i.video_id
    where i.speaker_kind = 'official' and i.person_id is not null
),

heard as (
    select
        mt.governing_body_id,
        mem.body_membership_id,
        mem.person_id,
        mem.member_name,
        mem.role,
        e.video_id,
        mt.meeting_date,
        e.start_seconds,
        e.attribution_method
    from evidence as e
    join meeting as mt on mt.video_id = e.video_id and mt.jurisdiction_id = e.jurisdiction_id
    join member as mem
        on mem.jurisdiction_id = e.jurisdiction_id
       and (mem.person_id = e.person_id or (e.person_id is null and mem.name_key = e.name_key)
            or (mem.person_id is null and mem.name_key = e.name_key))
),

last_moment as (
    select distinct on (h.governing_body_id, h.body_membership_id)
        h.governing_body_id, h.body_membership_id, h.video_id, h.meeting_date, h.start_seconds, h.attribution_method
    from heard as h
    order by h.governing_body_id, h.body_membership_id, h.meeting_date desc, h.start_seconds desc nulls last
)

select
    md5(h.governing_body_id || '|' || h.body_membership_id)::text           as body_recent_speaker_id,
    h.governing_body_id::text                                               as governing_body_id,
    h.body_membership_id::text                                              as body_membership_id,
    max(h.person_id)::text                                                  as person_id,
    max(h.member_name)::text                                                as member_name,
    max(h.role)::text                                                       as role,
    count(distinct h.video_id)::integer                                     as meetings_heard,
    count(*)::integer                                                       as mentions,
    max(lm.meeting_date)::date                                              as last_heard_date,
    max(lm.video_id)::text                                                  as last_video_id,
    max(lm.start_seconds)::numeric(10, 3)                                   as last_start_seconds,
    max(case
        when lm.video_id is not null and lm.start_seconds is not null
            then 'https://www.youtube.com/watch?v=' || lm.video_id || '&t='
                 || greatest(floor(lm.start_seconds)::integer - 3, 0)::text || 's'
        when lm.video_id is not null then 'https://www.youtube.com/watch?v=' || lm.video_id
    end)::text                                                              as last_moment_url,
    max(lm.attribution_method)::text                                        as attribution_method
from heard as h
join last_moment as lm on lm.governing_body_id = h.governing_body_id and lm.body_membership_id = h.body_membership_id
group by h.governing_body_id, h.body_membership_id
