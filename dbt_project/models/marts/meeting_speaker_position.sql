{{ config(materialized='table', tags=['meeting_comments', 'serving'],
          indexes=[{'columns': ['video_id']}, {'columns': ['state_code, meeting_date']}]) }}

/*
    One row per meeting x speaker (#1383, epic #1232): everyone who spoke in a meeting's public-comment periods,
    with ONE position merged from all of their segments. This is the grain the site counts ("62 speakers");
    meeting_comment segments are the detail. A speaker is named "First L." (residents) or by name and title
    (matched officials), else "Speaker N" in order of first appearance; never linked across meetings. A
    possible minor, a student or a resident at a school board meeting is "Speaker N" with no cue phrase.
    stance_shape is how the position is stated (int_meeting_speaker__stance_shape, cue seed
    comment_stance_shape_terms); cue_texts are the verbatim phrases behind it. No comment text is carried.
*/

with sp as (
    select
        t.meeting_speaker_id,
        t.video_id,
        min(t.speaker_number)                                       as speaker_number,
        max(t.name_shown)                                           as name_shown,
        max(t.speaker_role)                                         as speaker_role,
        bool_or(t.possible_minor)                                   as possible_minor,
        bool_or(t.name_withheld)                                    as name_withheld,
        bool_and(t.is_public_comment)                               as is_public_comment,
        count(distinct t.meeting_speaker_turn_id)                   as turn_count,
        count(*)                                                    as segment_count,
        sum(f.word_count)                                           as word_count,
        min(f.start_seconds)                                        as first_start_seconds,
        max(t.candidate_name)                                       as candidate_name,
        -- the best-supported segment carries the speaker's provenance
        (array_agg(t.attribution_method order by t.attribution_confidence desc, t.comment_index))[1] as attribution_method,
        max(t.attribution_confidence)                               as attribution_confidence,
        (array_agg(t.attribution_evidence order by t.attribution_confidence desc, t.comment_index))[1] as attribution_evidence,
        (array_agg(t.attribution_evidence_seconds order by t.attribution_confidence desc, t.comment_index))[1] as attribution_evidence_seconds,
        max(t.attribution_version)                                  as attribution_version,
        max(t.attributed_at)                                        as attributed_at
    from {{ ref('int_meeting_comment__turns') }} as t
    inner join {{ ref('int_meeting_comment__flags') }} as f on f.comment_segment_id = t.comment_segment_id
    group by t.meeting_speaker_id, t.video_id
)

select
    sp.meeting_speaker_id::text                                     as meeting_speaker_id,
    sp.video_id::text                                               as video_id,
    m.meeting_date::date                                            as meeting_date,
    m.jurisdiction_id::text                                         as jurisdiction_id,
    m.jurisdiction_name::text                                       as jurisdiction_name,
    m.state_code::text                                              as state_code,
    m.state::text                                                   as state,
    sp.speaker_number::int                                          as speaker_number,
    (case when sp.name_shown is not null then sp.name_shown
          else 'Speaker ' || sp.speaker_number::text end)::text     as speaker_label,
    (sp.name_shown is not null)::boolean                            as speaker_named,
    sp.speaker_role::text                                           as speaker_role,
    sp.is_public_comment::boolean                                   as is_public_comment,
    sp.possible_minor::boolean                                      as possible_minor,
    sp.turn_count::int                                              as turn_count,
    sp.segment_count::int                                           as segment_count,
    sp.word_count::int                                              as word_count,
    sp.first_start_seconds::numeric(12, 3)                          as first_start_seconds,
    sp.candidate_name::text                                         as possible_name,
    sp.attribution_method::text                                     as attribution_method,
    sp.attribution_confidence::numeric(3, 2)                        as attribution_confidence,
    {{ attribution_tier('sp.attribution_confidence') }}::text       as attribution_tier,
    sp.attribution_evidence::text                                   as attribution_evidence,
    sp.attribution_evidence_seconds::numeric(12, 3)                 as attribution_evidence_seconds,
    sp.attribution_version::text                                    as attribution_version,
    sp.attributed_at::timestamp                                     as attributed_at,
    hh.heat::int                                                    as heat,
    hh.heat_method::text                                            as heat_method,
    hh.heat_confidence::numeric(3, 2)                               as heat_confidence,
    (case when hh.heat is not null then hh.heat_version end)::text as heat_version,
    q.stance_shape::text                                            as stance_shape,
    (case when sp.possible_minor or sp.name_withheld then null else q.shape_cue_text end)::text as shape_cue_text,
    (case when sp.possible_minor or sp.name_withheld then '{}'::text[] else q.cue_texts end)::text[] as cue_texts
from sp
inner join {{ ref('int_meeting_speaker__stance_shape') }} as q on q.meeting_speaker_id = sp.meeting_speaker_id
inner join {{ ref('int_meeting_speaker__heat') }} as hh on hh.meeting_speaker_id = sp.meeting_speaker_id
inner join {{ ref('segmented_meeting') }} as m on m.video_id = sp.video_id
