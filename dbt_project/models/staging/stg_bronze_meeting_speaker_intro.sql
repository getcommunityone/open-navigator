{{ config(materialized='view', tags=['staging', 'transcripts', 'speakers']) }}

/*
    Speaker self-introductions (#1231), typed and trimmed from bronze.bronze_meeting_speaker_intro (written by
    `python -m ingestion.youtube.speaker_intros`). One row per (video_id, char_offset, pattern_id).
    name_tokens stay private: the mart meeting_speaker_intro serves only the display form.
    Design: web_docs/docs/development/speaker-names-from-self-introductions.md
*/

select
    btrim(i.video_id)::text                 as video_id,
    i.char_offset::integer                  as char_offset,
    i.pattern_id::text                      as pattern_id,
    i.start_seconds::numeric(10, 3)         as start_seconds,
    i.end_seconds::numeric(10, 3)           as end_seconds,
    i.confidence::numeric(3, 2)             as confidence,
    i.name_tokens::text[]                   as name_tokens,
    coalesce(array_length(i.name_tokens, 1), 0)::integer as name_token_count,
    nullif(btrim(i.title_token), '')::text  as title_token,
    coalesce(i.mentions_minor, false)       as mentions_minor,
    -- The intro says the speaker lives here (role "Resident" only when the record says so).
    (i.pattern_id = 'i_am_live'
        or i.matched_text ~* '\m(i live|i reside|resident)')::boolean as says_resident,
    i.extractor_version::text               as extractor_version,
    i.extracted_at                          as extracted_at
from {{ source('bronze', 'bronze_meeting_speaker_intro') }} as i
where i.name_tokens is not null and array_length(i.name_tokens, 1) >= 1
