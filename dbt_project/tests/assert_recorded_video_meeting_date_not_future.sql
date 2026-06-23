{{ config(severity='warn', tags=['data_quality', 'event_meeting']) }}

-- Recorded meetings (video_id present) must not carry a future meeting_date.
-- A YouTube transcript is evidence the meeting already happened; a date after
-- current_date is almost always an extraction or OCR typo (e.g. 2926 vs 2026,
-- or 2028 when the recording title said 2026).
--
-- SEVERITY = warn while legacy rows are cleaned up; flip to error once this
-- query returns zero rows.

select
    event_meeting_id,
    video_id,
    meeting_id,
    body_name,
    meeting_date
from {{ ref('event_meeting') }}
where video_id is not null
  and meeting_date ~ '^\d{4}-\d{2}-\d{2}$'
  and meeting_date::date > current_date
