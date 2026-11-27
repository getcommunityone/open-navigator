{{ config(materialized='table', tags=['marts', 'topics', 'data-center', 'serving']) }}

/*
    What kind of video each quoted recording is (#1230), so the story maps quote only real public meetings. Grain: one
    row per video_id that a topic link (topic_transcript_link) or a data-center mention (data_center_meeting_mention)
    quotes AND that Jev screened for meeting kind. A recording with no row was never screened: consumers keep it
    (conservative, like the junk-channel gate in event_youtube_with_jurisdiction) but may rank it after a screened one.

    is_public_meeting: Jev read it as a governing-body meeting or a government town hall. government_other (media
    briefings, ceremonies, academy graduations, interviews) and not_government (podcasts, news shows, streams) are not.

    No classifier runs here: the answers are Jev's existing meeting_kind (stg_jev__video_meeting_kind). Title patterns
    were measured and rejected (they also hit real meetings, e.g. "Special Meeting - Candidate Interviews").
*/

with quoted as (
    select video_id from {{ ref('topic_transcript_link') }}
    union
    select video_id from {{ ref('data_center_meeting_mention') }}
)

select
    k.video_id::text                                                        as video_id,
    k.meeting_kind::text                                                    as meeting_kind,
    k.kind_source::text                                                     as kind_source,
    (k.meeting_kind in ('government_meeting', 'town_hall'))::boolean        as is_public_meeting,
    k.screened_at::timestamptz                                              as screened_at
from {{ ref('stg_jev__video_meeting_kind') }} as k
inner join quoted as q on q.video_id = k.video_id
