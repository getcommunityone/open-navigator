{{ config(severity='warn', tags=['event_documents', 'transcripts']) }}

/*
#533 / #470: every captioned meeting transcript reaches event_documents.

Fails (returns rows) for a bronze transcript that has at least 100 characters of
caption text, is not a policy-pipeline reject (`excluded:%`) or tombstone, is
not junk-gated and is not a Canadian CivicSearch meeting, yet has no
event_documents row. Before #533 ~10.2k such rows were dropped because they
carried has_transcript = false.

Severity warn: transcripts loaded after the last event_documents build show up
here until the next build.
Output: counts by transcript_source and has_transcript.
*/

with captioned as (
    select trim(t.video_id) as video_id, t.transcript_source, t.has_transcript
    from {{ source('bronze', 'bronze_event_youtube_transcript') }} t
    where nullif(trim(t.video_id), '') is not null
      and length(trim(coalesce(t.raw_text, ''))) >= 100
      and lower(coalesce(trim(t.transcript_source), '')) not like 'excluded:%'
      and lower(coalesce(trim(t.transcript_source), '')) not like 'tombstone:%'
),

junk as (
    select b.video_id
    from {{ source('bronze', 'bronze_event_youtube') }} b
    where not exists (
        select 1 from {{ ref('event_youtube_with_jurisdiction') }} w
        where w.video_id = b.video_id
    )
),

non_us as (
    select c.vid_id as video_id
    from {{ ref('stg_civicsearch__event') }} c
    where c.location ~ '{{ canadian_location_regex() }}'
)

select c.transcript_source, c.has_transcript, count(*) as missing_count
from captioned c
where not exists (select 1 from {{ ref('event_documents') }} d where d.video_id = c.video_id)
  and not exists (select 1 from junk j where j.video_id = c.video_id)
  and not exists (select 1 from non_us n where n.video_id = c.video_id)
group by 1, 2
