{{ config(materialized='table', tags=['marts', 'data_centers', 'serving', 'sentiment']) }}

/*
    The public comments behind data_center_meeting_position (#930), so every count links to
    the speaker's own words and the moment in the recording. Grain: one row per public
    comment that int_data_center__public_comment counts as about a data center item (the
    rule and its known misses are written there).

    quote is public_comment.stance_evidence, verbatim (25 words or fewer); null when the
    extraction kept none. decision_headline names the item when the comment counts because
    of the decision it is linked to (match_basis = data_center_decision), so a quote that
    doesn't itself say "data center" still shows why it is here.
    is_counted: the one row counted for the speaker in that meeting.
    Design: web_docs/docs/development/data-center-who-spoke-up.md
*/

select
    c.public_comment_id::text                                   as public_comment_id,
    p.data_center_meeting_position_id::text                     as data_center_meeting_position_id,
    c.event_meeting_id::integer                                 as event_meeting_id,
    c.event_decision_id::text                                   as event_decision_id,
    c.decision_headline::text                                   as decision_headline,
    c.match_basis::text                                         as match_basis,
    c.speaker_id::text                                          as speaker_id,
    c.speaker_role::text                                        as speaker_role,
    c.stance_bucket::text                                       as stance_bucket,
    c.stance_evidence::text                                     as quote,
    c.is_counted::boolean                                       as is_counted,
    c.timestamp_start_seconds::numeric(12, 3)                   as start_seconds,
    p.video_id::text                                            as video_id,
    ('https://www.youtube.com/watch?v=' || p.video_id)::text    as video_url,
    p.meeting_date::date                                        as meeting_date,
    p.jurisdiction_name::text                                   as jurisdiction_name,
    p.state_code::text                                          as state_code,
    p.state::text                                               as state
from {{ ref('int_data_center__public_comment') }} as c
inner join {{ ref('data_center_meeting_position') }} as p on p.event_meeting_id = c.event_meeting_id
