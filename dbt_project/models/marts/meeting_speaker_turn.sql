{{ config(materialized='table', tags=['meeting_comments', 'serving'],
          indexes=[{'columns': ['video_id']}, {'columns': ['meeting_speaker_id']}]) }}

/*
    One row per meeting x speaker turn (#1383, epic #1232): an uninterrupted stretch by one speaker, in the order
    they spoke. A turn is one or more meeting_comment segments (the detail layer, FK'd to this table). Belongs to
    one speaker (meeting_speaker_position). Times are seconds into the recording.
*/

select
    t.meeting_speaker_turn_id::text                                 as meeting_speaker_turn_id,
    t.video_id::text                                                as video_id,
    t.meeting_speaker_id::text                                      as meeting_speaker_id,
    min(t.turn_index)::int                                          as turn_index,
    count(*)::int                                                   as segment_count,
    sum(f.word_count)::int                                          as word_count,
    min(f.start_seconds)::numeric(12, 3)                            as start_seconds,
    max(f.end_seconds)::numeric(12, 3)                              as end_seconds,
    (array_agg(t.attribution_method order by t.attribution_confidence desc, t.comment_index))[1]::text as attribution_method,
    max(t.attribution_confidence)::numeric(3, 2)                    as attribution_confidence,
    {{ attribution_tier('max(t.attribution_confidence)') }}::text   as attribution_tier,
    (array_agg(t.attribution_evidence order by t.attribution_confidence desc, t.comment_index))[1]::text as attribution_evidence,
    (array_agg(t.attribution_evidence_seconds order by t.attribution_confidence desc, t.comment_index))[1]::numeric(12, 3) as attribution_evidence_seconds,
    max(t.attribution_version)::text                                as attribution_version,
    max(t.attributed_at)::timestamp                                 as attributed_at
from {{ ref('int_meeting_comment__turns') }} as t
inner join {{ ref('int_meeting_comment__flags') }} as f on f.comment_segment_id = t.comment_segment_id
inner join {{ ref('meeting_speaker_position') }} as p on p.meeting_speaker_id = t.meeting_speaker_id
group by t.meeting_speaker_turn_id, t.video_id, t.meeting_speaker_id
