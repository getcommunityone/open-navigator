-- int_event_transcripts.sql
-- Unified transcript layer: one consistent row per video_id across every
-- transcript source, so downstream consumers read ONE shape regardless of
-- where the text came from.
--
-- Sources merged here:
--   * YouTube caption fetches  (bronze_events_text_ai via stg_bronze_events_text_ai)
--       -> source = 'youtube'; carry per-segment timing in `segments` (jsonb).
--   * LocalView scraped captions (bronze_events_localview source)
--       -> source = 'localview'; flat caption text only — there is NO per-segment
--          timing, so `segments` is NULL (nothing to convert) and `raw_text` is
--          the cleaned caption (`caption_text_clean`).
--
-- One row per video_id: where a video has both a YouTube fetch and a LocalView
-- caption, YouTube wins (it carries timing); ties break toward the fuller text.
-- Canonical event_id / jurisdiction geo are resolved from int_events_union
-- (the deduped event spine) when available, falling back to the source row.
--
-- This replaces physically copying the ~153K LocalView captions into
-- bronze_events_text_ai (which would duplicate ~3-4GB of text + rebuild the GIN
-- index); the captions stay put in bronze and are unioned logically here.

{{
    config(
        materialized='view',
        tags=['intermediate', 'events', 'transcripts'],
    )
}}

-- Same video_id extraction int_events_union uses: parse it out of the YouTube
-- URL, else fall back to datasource_id (which IS the video id for LocalView).
{% set youtube_video_id = "REGEXP_REPLACE(REGEXP_REPLACE(video_url, '.*[?&]v=([^&]+).*', '\\1'), '.*youtu\\.be/([^?]+).*', '\\1')" %}

with youtube as (

    -- Read the bronze source directly (the stg_bronze_events_text_ai view drops
    -- the geo columns we need for a consistent shape). Same light cleaning the
    -- staging view applies, inline.
    select
        trim(video_id)                  as video_id,
        event_id,
        nullif(trim(raw_text), '')      as raw_text,
        segments,
        lower(trim(language))           as language,
        is_auto_generated,
        lower(trim(transcript_source))  as transcript_source,
        has_transcript,
        lower(trim(transcript_quality)) as transcript_quality,
        state_code,
        state,
        jurisdiction_id,
        jurisdiction_name,
        'youtube' as source
    from {{ source('bronze', 'bronze_events_text_ai') }}
    where video_id is not null
      and trim(video_id) <> ''
      and raw_text is not null
      and length(btrim(raw_text)) > 0

),

localview as (

    select
        coalesce(
            case
                when video_url like '%youtube.com%' or video_url like '%youtu.be%'
                then {{ youtube_video_id }}
            end,
            nullif(trim(datasource_id), '')
        )                           as video_id,
        event_id,
        caption_text_clean          as raw_text,
        cast(null as jsonb)         as segments,            -- flat captions: no timing to convert
        'en'                        as language,            -- LocalView is English municipal meetings
        true                        as is_auto_generated,   -- scraped YouTube auto-captions
        'localview'                 as transcript_source,
        true                        as has_transcript,
        cast(null as varchar(20))   as transcript_quality,
        state_code,
        state,
        cast(null as text)          as jurisdiction_id,     -- not on bronze_events_localview; resolved below
        jurisdiction_name,
        'localview' as source
    from {{ source('bronze', 'bronze_events_localview') }}
    where caption_text_clean is not null
      and length(btrim(caption_text_clean)) > 0

),

unioned as (

    select * from youtube
    union all
    select * from localview

),

deduped as (

    select
        *,
        row_number() over (
            partition by video_id
            order by
                case source when 'youtube' then 0 else 1 end,  -- prefer YouTube (has timing)
                length(raw_text) desc                          -- then the fuller transcript
        ) as dedupe_rank
    from unioned
    where video_id is not null
      and length(btrim(video_id)) > 0

),

final as (

    select
        d.video_id,
        coalesce(u.event_id, d.event_id)                    as event_id,
        d.raw_text,
        d.segments,
        d.language,
        d.is_auto_generated,
        d.transcript_source,
        d.has_transcript,
        d.transcript_quality,
        coalesce(u.state_code, d.state_code)                as state_code,
        coalesce(u.state, d.state)                          as state,
        coalesce(u.jurisdiction_id, d.jurisdiction_id)      as jurisdiction_id,
        coalesce(u.jurisdiction_name, d.jurisdiction_name)  as jurisdiction_name,
        d.source
    from deduped d
    left join {{ ref('int_events_union') }} u
        on u.video_id = d.video_id
    where d.dedupe_rank = 1

)

select * from final
