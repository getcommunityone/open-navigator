{{
  config(
    materialized='table',
    tags=['marts', 'meetings', 'platform_meetings'],
    indexes=[
      {'columns': ['jurisdiction_id', 'meeting_date'], 'type': 'btree'},
      {'columns': ['transcription_status'], 'type': 'btree'}
    ]
  )
}}

/*
gold.platform_meeting — meetings read from Granicus portals and the Legistar Web API
(#536), one row per meeting, with the FK to the government whose meeting it is.

The sibling of event_meeting_document (which carries each meeting's agenda and minutes
as documents, with their text) and event_documents (which carries any platform caption
text as a transcript). This model is the meeting itself: date, body, title, the
agenda / minutes / video links, whether the platform served agenda or minutes text, and
transcription_status ('queued_whisper' = a video with no captions waiting for Colab
Whisper, #489).

jurisdiction_id is kept only when it is in jurisdictions (the FK target); a meeting
whose portal's government isn't there keeps a NULL FK rather than a dangling one.

SOURCE: stg_bronze_platform_meeting, jurisdictions.
*/

select
    m.platform_meeting_id,
    m.platform,
    m.meeting_uid,
    m.portal,
    j.jurisdiction_id,
    m.state_code,
    m.state,
    m.body_name,
    m.title,
    m.meeting_date,
    m.meeting_time,
    m.location,
    m.agenda_url,
    m.minutes_url,
    m.video_url,
    m.video_url_source,
    m.detail_url,
    (m.agenda_text is not null)                             as has_agenda_text,
    (m.minutes_text is not null)                            as has_minutes_text,
    m.has_captions,
    m.transcription_status,
    m.fetched_at::timestamp                                 as fetched_at
from {{ ref('stg_bronze_platform_meeting') }} as m
left join {{ ref('jurisdictions') }} as j
    on j.jurisdiction_id = m.jurisdiction_id
