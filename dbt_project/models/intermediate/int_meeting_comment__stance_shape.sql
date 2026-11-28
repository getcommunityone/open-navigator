{{ config(materialized='table', tags=['intermediate', 'meeting_comments'],
          indexes=[{'columns': ['comment_segment_id'], 'unique': true}]) }}

/*
    The SHAPE of each comment's stance (#1383, epic #1232): not just which side, but how it is said.
    Grain: one row per comment segment (int_meeting_comment__flags). The rules are the stance_shape_sql macro
    (seed comment_stance_shape_terms), also run per speaker on all of their text; the first match of each cue kind is
    kept verbatim (shape_cue_text). No LLM. Private (it reads comment_text); meeting_comment serves only the
    shape and the short cue phrase.

    A comment that reads as both for and against is either two speakers merged (the segmenter now re-splits
    those) or one speaker with a qualified position. Shapes, in the order they are decided:
      for_concept_against_project  supports the idea, objects to this site ("I support data centers but not here")
      conditional                  a side + "only if" / "as long as" / "provided that" / "with conditions"
      against_concept_open_to_terms  opposes, but "unless" / "open to" / "would reconsider"
      clear_for / clear_against    only one side's cue
      concerns_only                no side, but raises a concern (water, noise, taxes, grid ...)
      unclear                      no cue, or both sides with no shape cue (may be more than one speaker)
    A shape is never counted as both sides.
*/

with units as (
    select comment_segment_id as unit_id, comment_text as unit_text,
           coalesce(cardinality(concern_keys), 0) as concern_count
    from {{ ref('int_meeting_comment__flags') }}
)

select unit_id::text as comment_segment_id, stance_shape, shape_cue_text, both_side_cues
from ({{ stance_shape_sql('units') }}) as s
