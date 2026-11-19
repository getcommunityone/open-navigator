{{ config(severity='warn', tags=['event_documents', 'transcripts', 'freshness']) }}

/*
#563: gold/public event_documents must not lag bronze transcripts by more than 24h.

A transcript loaded after the last `events_text_search` / `event_documents` build
never reaches What's New until those models run again. This test returns one row
when the newest captioned bronze transcript is more than 24 hours newer than the
newest event_documents.created_at, so the nightly freshness run names the gap.
*/

with bronze_newest as (
    select max(t.created_at) as newest_transcript_at
    from {{ source('bronze', 'bronze_event_youtube_transcript') }} t
    where nullif(trim(t.video_id), '') is not null
      and length(trim(coalesce(t.raw_text, ''))) >= 100
      and lower(coalesce(trim(t.transcript_source), '')) not like 'excluded:%'
      and lower(coalesce(trim(t.transcript_source), '')) not like 'tombstone:%'
),

docs_newest as (
    select max(created_at) as newest_document_at
    from {{ ref('event_documents') }}
)

select
    b.newest_transcript_at,
    d.newest_document_at,
    extract(epoch from (b.newest_transcript_at - d.newest_document_at)) / 3600.0
        as lag_hours
from bronze_newest b
cross join docs_newest d
where b.newest_transcript_at is not null
  and d.newest_document_at is not null
  and b.newest_transcript_at > d.newest_document_at + interval '24 hours'
