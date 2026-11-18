{{ config(materialized='view', tags=['staging', 'meetings', 'platform_meetings']) }}

/*
staging.stg_platform_meeting__whisper_queue — platform meeting videos with no captions,
waiting to be transcribed by Colab Whisper (#489). Grain: one row per meeting.

Nothing here transcribes anything. The Colab runner reads this list (or the TSV from
`python -m scrapers.platforms.run --export-whisper-queue`) and must itself check the
video host's robots.txt before downloading: Granicus' archive hosts disallow crawlers.
*/

select
    platform_meeting_id,
    platform,
    meeting_uid,
    jurisdiction_id,
    state_code,
    meeting_date,
    body_name,
    video_url,
    video_url_source,
    video_clip_id
from {{ ref('stg_bronze_platform_meeting') }}
where transcription_status = 'queued_whisper'
  and video_url is not null
  -- A meeting still ahead has a livestream link but no recording yet.
  and meeting_date <= current_date
