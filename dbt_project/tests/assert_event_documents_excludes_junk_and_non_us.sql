{{ config(severity='error', tags=['event_documents', 'transcripts']) }}

/*
#533: event_documents never serves a transcript from a junk-gated channel or a
Canadian CivicSearch meeting.

  - junk gate: the video is in bronze_event_youtube but was removed from
    event_youtube_with_jurisdiction (channel classified is_junk / not government);
  - non-US: the CivicSearch location ends in a Canadian province or territory.

Output: one row per offending video_id with the reason.
*/

select d.video_id, 'junk_gated'::text as reason
from {{ ref('event_documents') }} d
join {{ source('bronze', 'bronze_event_youtube') }} b on b.video_id = d.video_id
where not exists (
    select 1 from {{ ref('event_youtube_with_jurisdiction') }} w
    where w.video_id = d.video_id
)

union all

select d.video_id, 'non_us_civicsearch'::text as reason
from {{ ref('event_documents') }} d
join {{ ref('stg_civicsearch__event') }} c on c.vid_id = d.video_id
where c.location ~ '{{ canadian_location_regex() }}'
