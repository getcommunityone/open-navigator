{{ config(tags=['data_quality', 'event_documents']) }}

-- A transcript is a recording of a meeting that already happened, so its event_date
-- cannot be after tomorrow (one day of slack for time zones). A later date is a typo
-- in the video title (2926 for 2026, a two-digit year read as 20xx) and sorts or
-- filters the transcript wrongly: max(event_date) once read 2926-04-01 (#564).
-- event_youtube_with_jurisdiction replaces such a date with the upload day or NULL.

select
    video_id,
    event_date,
    event_title,
    state_code
from {{ ref('event_documents') }}
where video_id is not null
  and event_date > current_date + 1
