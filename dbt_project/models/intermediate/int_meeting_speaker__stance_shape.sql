{{ config(materialized='table', tags=['intermediate', 'meeting_comments'],
          indexes=[{'columns': ['meeting_speaker_id'], 'unique': true}]) }}

/*
    One position per meeting x speaker (#1383, epic #1232): all of a speaker's segments joined in order and
    read once with the same cue rules as a single segment (stance_shape_sql), so "I support data centers" in
    one turn and "but not at this site" in another still read as for_concept_against_project. Private: it
    reads comment text. cue_texts keeps each segment's own verbatim cue phrase, in order.
*/

with units as (
    select
        t.meeting_speaker_id                                              as unit_id,
        string_agg(f.comment_text, ' ' order by t.comment_index)          as unit_text,
        coalesce(max(cardinality(f.concern_keys)), 0)                     as concern_count
    from {{ ref('int_meeting_comment__turns') }} as t
    inner join {{ ref('int_meeting_comment__flags') }} as f on f.comment_segment_id = t.comment_segment_id
    group by t.meeting_speaker_id
),

cues as (
    select
        t.meeting_speaker_id,
        array_agg(distinct s.shape_cue_text) filter (where s.shape_cue_text is not null) as cue_texts
    from {{ ref('int_meeting_comment__turns') }} as t
    inner join {{ ref('int_meeting_comment__stance_shape') }} as s on s.comment_segment_id = t.comment_segment_id
    group by t.meeting_speaker_id
)

select
    p.unit_id::text as meeting_speaker_id,
    p.stance_shape,
    p.shape_cue_text,
    p.both_side_cues,
    coalesce(c.cue_texts, '{}'::text[]) as cue_texts
from ({{ stance_shape_sql('units') }}) as p
left join cues as c on c.meeting_speaker_id = p.unit_id
