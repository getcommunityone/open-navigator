{{ config(materialized='view', tags=['staging', 'meetings', 'platform_meetings', 'transcripts']) }}

/*
staging.stg_bronze_platform_meeting_caption — caption text a meeting platform serves for
a meeting's video (#536). Grain: one row per (platform, meeting_uid).

segments keeps the {start, duration, text} cue shape of YouTube transcripts, so the
event_documents / data center passage logic that reads cues reads these the same way.
Rows with no text are dropped.

SOURCE: bronze.bronze_platform_meeting_caption.
*/

select
    md5(platform || '|' || meeting_uid)                     as platform_meeting_id,
    platform::text                                          as platform,
    meeting_uid::text                                       as meeting_uid,
    caption_source::text                                    as caption_source,
    caption_url::text                                       as caption_url,
    caption_format::text                                    as caption_format,
    coalesce(nullif(btrim(language), ''), 'en')::text       as language,
    raw_text::text                                          as raw_text,
    case
        when jsonb_typeof(segments) = 'array' and jsonb_array_length(segments) > 0 then segments
    end                                                     as segments,
    cue_count::integer                                      as cue_count,
    fetched_at::timestamptz                                 as fetched_at
from {{ source('bronze', 'bronze_platform_meeting_caption') }}
where nullif(btrim(raw_text), '') is not null
