{{ config(materialized='table', tags=['meeting_comments', 'serving']) }}

/*
    Meetings whose captions were split into comments (#1233). Grain: one row per meeting
    video that has at least one segmented comment. The parent of meeting_comment: the
    comment segmenter runs once per meeting, topic-agnostic, and every topic reads it.
    Place and date come from event_youtube_with_jurisdiction (junk channels gated out); a
    video dated in the future has a wrong source date (#472) and gets a null date.
*/

with segs as (
    select
        video_id,
        count(*)                                        as comment_count,
        count(*) filter (where is_public_comment)       as public_comment_count,
        max(segmenter_version)                          as segmenter_version
    from {{ ref('int_meeting_comment__flags') }}
    group by video_id
),

videos as (
    select distinct on (video_id)
        video_id,
        nullif(trim(title), '')                                                         as meeting_title,
        case when event_date::date > current_date then null else event_date::date end   as meeting_date,
        nullif(trim(jurisdiction_id), '')                                               as jurisdiction_id,
        nullif(trim(jurisdiction_name), '')                                             as jurisdiction_name,
        nullif(trim(state_code), '')                                                    as state_code
    from {{ ref('event_youtube_with_jurisdiction') }}
    where video_id in (select video_id from segs)
    order by video_id, event_date desc nulls last
),

known_jurisdictions as (
    select jurisdiction_id, name as jurisdiction_name from {{ ref('jurisdictions') }}
)

select
    s.video_id::text                                                as video_id,
    ('https://www.youtube.com/watch?v=' || s.video_id)::text        as video_url,
    v.meeting_title::text                                           as meeting_title,
    v.meeting_date::date                                            as meeting_date,
    j.jurisdiction_id::text                                         as jurisdiction_id,
    coalesce(v.jurisdiction_name, j.jurisdiction_name)::text        as jurisdiction_name,
    v.state_code::text                                              as state_code,
    (case when v.state_code is not null then {{ state_code_to_name('v.state_code') }} end)::text as state,
    s.comment_count::int                                            as comment_count,
    s.public_comment_count::int                                     as public_comment_count,
    s.segmenter_version::text                                       as segmenter_version
from segs as s
left join videos as v on v.video_id = s.video_id
left join known_jurisdictions as j on j.jurisdiction_id = v.jurisdiction_id
