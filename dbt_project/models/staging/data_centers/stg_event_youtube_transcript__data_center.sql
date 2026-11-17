{{ config(materialized='view', tags=['staging', 'data_centers', 'transcripts']) }}

/*
    Transcripts that say "data center" (#445). Grain: one row per video_id.

    Reads bronze.bronze_event_youtube_transcript directly (not stg_bronze_event_youtube_transcript)
    because the prefilter has to use the exact expression of the table's GIN index,
    to_tsvector('english', coalesce(raw_text, '')), to stay fast over ~176k transcripts.
    Quality filters: no 'excluded:%' policy-pipeline rejects or 'tombstone:%' rows, and the
    text itself must match. has_transcript is NOT used: ~10k rows loaded 2026-05-31..06-10
    carry full captions with has_transcript = false (e.g. Minneapolis council 2026-05-21), so
    the flag would drop real meetings. caption_text_timed is kept: it is the only timing for
    transcripts without segments.
*/

select
    trim(t.video_id)::text                              as video_id,
    t.raw_text::text                                    as raw_text,
    case
        when jsonb_typeof(t.segments) = 'array' and jsonb_array_length(t.segments) > 0
            then t.segments
    end                                                 as segments,
    nullif(trim(t.caption_text_timed), '')::text        as caption_text_timed,
    lower(trim(t.transcript_source))::text              as transcript_source
from {{ source('bronze', 'bronze_event_youtube_transcript') }} as t
where to_tsvector('english', coalesce(t.raw_text, '')) @@ {{ data_center_index_tsquery() }}
  and t.raw_text ~* '{{ data_center_regex() }}'
  and lower(coalesce(trim(t.transcript_source), '')) not like 'excluded:%'
  and lower(coalesce(trim(t.transcript_source), '')) not like 'tombstone:%'
  and nullif(trim(t.video_id), '') is not null
