{{ config(materialized='view', tags=['staging', 'meeting_comments']) }}

/*
    Public comments segmented from meeting captions (#1233). Grain: one row per comment.
    Typed pass-through of bronze.bronze_meeting_comment_segment; the segmenter
    (python -m ingestion.meetings.comment_segments) already scrubbed home addresses from
    comment_text and intro_text. intro_name stays here and in intermediate: marts serve only
    a "First L." display form.
*/

select
    comment_segment_id::text            as comment_segment_id,
    trim(video_id)::text                as video_id,
    comment_index::int                  as comment_index,
    block_index::int                    as block_index,
    start_seconds::numeric(12, 3)       as start_seconds,
    end_seconds::numeric(12, 3)         as end_seconds,
    comment_text::text                  as comment_text,
    word_count::int                     as word_count,
    nullif(trim(intro_text), '')::text  as intro_text,
    nullif(trim(intro_name), '')::text  as intro_name,
    boundary_basis::text                as boundary_basis,
    in_public_comment_section::boolean  as in_public_comment_section,
    segmenter_version::text             as segmenter_version,
    loaded_at::timestamp                as loaded_at
from {{ source('bronze', 'bronze_meeting_comment_segment') }}
where nullif(trim(video_id), '') is not null
