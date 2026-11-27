/*
    public.topic_place_meeting — a topic story's meetings per government (#1349), for the state county map
    (StoryCountyMap, the same map the Data Center Story draws from data_center_meeting_mention's by_place).

    GRAIN: one row per (topic_id, jurisdiction_id): the distinct meetings in topic_transcript_link whose recording is
    attached to that government (event_youtube_with_jurisdiction, one government per video), plus the AI reading of
    those meetings (topic_meeting_lean, the same counts and thresholds as the state map's /state-map).

    PLACED: a meeting counts here only when its government
      * is in jurisdictions,
      * is in the same state as the topic link (a recording filed under another state's government is left out, so a
        town is never drawn on the wrong state), and
      * can be drawn: a county by its geoid, or any government with coordinates (the front end then places it in the
        county its point falls in, by point-in-polygon on the county shapes it already loads; jurisdictions has no
        city -> county link).
    Every other meeting is "unplaced": the API reports state total minus sum(meetings) and the map footnotes it.

    The lean counts are an AI reading (Jev) per meeting, never counted speakers, never tied to a person.

    PK : topic_place_meeting_id = md5(topic_id|jurisdiction_id)
    FK : topic_id -> civicsearch_topic, jurisdiction_id -> jurisdictions
*/

with link as (
    select topic_id, video_id, state_code
    from {{ ref('topic_transcript_link') }}
    where state_code is not null
),

video as (
    select distinct on (video_id) video_id, nullif(trim(jurisdiction_id), '') as jurisdiction_id
    from {{ ref('event_youtube_with_jurisdiction') }}
    order by video_id
),

placed as (
    select
        l.topic_id,
        l.video_id,
        j.jurisdiction_id,
        j.state_code,
        j.state_name,
        coalesce(nullif(trim(j.name), ''), j.display_name) as jurisdiction_name,
        j.jurisdiction_type,
        j.geoid,
        j.latitude,
        j.longitude
    from link as l
    join video as v on v.video_id = l.video_id
    join {{ ref('jurisdictions') }} as j on j.jurisdiction_id = v.jurisdiction_id
    where j.state_code = l.state_code
      and (
          (j.jurisdiction_type = 'county' and j.geoid is not null)
          or (j.latitude is not null and j.longitude is not null)
      )
),

lean as (
    select
        t.topic_id,
        t.video_id,
        t.public_lean,
        t.public_lean_p,
        t.public_against,
        t.public_for,
        t.officials_sided_against_public
    from {{ ref('topic_meeting_lean') }} as t
)

select
    md5(p.topic_id::text || '|' || p.jurisdiction_id)::text                         as topic_place_meeting_id,
    p.topic_id::integer                                                              as topic_id,
    p.jurisdiction_id::text                                                          as jurisdiction_id,
    max(p.state_code)::text                                                          as state_code,
    max(p.state_name)::text                                                          as state,
    max(p.jurisdiction_name)::text                                                   as jurisdiction_name,
    max(p.jurisdiction_type)::text                                                   as jurisdiction_type,
    max(p.geoid)::text                                                               as geoid,
    max(p.latitude)::double precision                                                as latitude,
    max(p.longitude)::double precision                                               as longitude,
    count(distinct p.video_id)::integer                                              as meetings,
    count(distinct p.video_id) filter (where l.video_id is not null)::integer        as lean_meetings,
    count(distinct p.video_id) filter (where l.public_against)::integer              as public_against_meetings,
    count(distinct p.video_id) filter (where l.public_for)::integer                  as public_for_meetings,
    count(distinct p.video_id) filter (
        where l.public_lean = 'mixed'
           or (l.public_lean in ('mostly_opposed', 'mostly_supportive') and coalesce(l.public_lean_p, 0) < 0.7)
    )::integer                                                                       as no_side_meetings,
    count(distinct p.video_id) filter (where l.public_lean = 'did_not_speak')::integer as silent_meetings,
    count(distinct p.video_id) filter (where l.officials_sided_against_public)::integer as disagreement_meetings
from placed as p
left join lean as l
    on l.topic_id = p.topic_id and l.video_id = p.video_id
group by p.topic_id, p.jurisdiction_id
