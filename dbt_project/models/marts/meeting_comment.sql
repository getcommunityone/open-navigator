{{ config(materialized='table', tags=['meeting_comments', 'serving'],
          indexes=[{'columns': ['video_id']}, {'columns': ['state_code, meeting_date']}]) }}

/*
    One row per comment segmented from a meeting's captions (#1233, epic #1232), with the
    free keyword flags of int_meeting_comment__flags. Topic-agnostic: topic_ids says which
    curated topics the comment's own words name. No comment text is carried (privacy by
    construction); speaker_display_name is "First L." from the self-introduction, null for a
    possible minor or a name that isn't two clean words (speaker_display_name macro).
    stance_shape / shape_cue_text (#1383) say HOW a position is stated (conditional, supports the idea but not
    this project, concerns only ...) from free cue rules; the cue is a short verbatim phrase, not the comment.
    Which side (for / against) as a count still needs the per-comment classifier (phase 2, on hold).
*/

with f as (
    select * from {{ ref('int_meeting_comment__flags') }}
)

select
    f.comment_segment_id::text                       as meeting_comment_id,
    f.video_id::text                                 as video_id,
    m.meeting_date::date                             as meeting_date,
    m.jurisdiction_id::text                          as jurisdiction_id,
    m.jurisdiction_name::text                        as jurisdiction_name,
    m.state_code::text                               as state_code,
    m.state::text                                    as state,
    f.comment_index::int                             as comment_index,
    f.block_index::int                               as block_index,
    f.start_seconds::numeric(12, 3)                  as start_seconds,
    f.end_seconds::numeric(12, 3)                    as end_seconds,
    f.word_count::int                                as word_count,
    (case when f.possible_minor then null
          else {{ speaker_display_name("regexp_replace(lower(f.intro_name), '[^a-z]+', '_', 'g')", "null") }}
     end)::text                                      as speaker_display_name,
    f.boundary_basis::text                           as boundary_basis,
    f.in_public_comment_section::boolean             as in_public_comment_section,
    f.is_public_comment::boolean                     as is_public_comment,
    f.possible_minor::boolean                        as possible_minor,
    f.topic_ids::int[]                               as topic_ids,
    f.concern_keys::text[]                           as concern_keys,
    f.company_keys::text[]                           as company_keys,
    f.person_keys::text[]                            as person_keys,
    f.mentions_ai::boolean                           as mentions_ai,
    f.role_keys::text[]                              as role_keys,
    f.segmenter_version::text                        as segmenter_version,
    tu.meeting_speaker_turn_id::text                 as meeting_speaker_turn_id,
    tu.meeting_speaker_id::text                      as meeting_speaker_id,
    sh.stance_shape::text                            as stance_shape,
    (case when f.possible_minor then null else sh.shape_cue_text end)::text as shape_cue_text
from f
inner join {{ ref('int_meeting_comment__stance_shape') }} as sh on sh.comment_segment_id = f.comment_segment_id
inner join {{ ref('int_meeting_comment__turns') }} as tu on tu.comment_segment_id = f.comment_segment_id
inner join {{ ref('meeting_speaker_turn') }} as mst on mst.meeting_speaker_turn_id = tu.meeting_speaker_turn_id
inner join {{ ref('segmented_meeting') }} as m on m.video_id = f.video_id
