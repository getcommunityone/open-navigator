/*
    Staging (#1230): Jev's reading of what kind of video a recording is, one row per video_id. Jev is a classifier
    (probabilities only, no text); this model only types and picks among its existing answers, it classifies nothing.

    meeting_kind is one of llm.typesafe.screen_transcripts.MEETING_KINDS: government_meeting, town_hall,
    government_other (press conference, ceremony, training, interview-like government video) or not_government.

    Two screens answer it: the transcript screen (bronze_transcript_screen_jev, reads the transcript) and the cheaper
    video-meta screen (bronze_video_meta_screen_jev, reads the title / description). The transcript screen wins where
    both exist; within a screen, the latest screened_at.

    Either bronze table may be missing in a fresh warehouse; the model then builds from the other, or empty.
*/

{%- set tx = source('bronze', 'bronze_transcript_screen_jev') -%}
{%- set meta = source('bronze', 'bronze_video_meta_screen_jev') -%}
{%- set tx_exists = execute and adapter.get_relation(
        database=tx.database, schema=tx.schema, identifier=tx.identifier) is not none -%}
{%- set meta_exists = execute and adapter.get_relation(
        database=meta.database, schema=meta.schema, identifier=meta.identifier) is not none -%}

with answers as (
    {% if tx_exists %}
    select video_id::text as video_id, meeting_kind::text as meeting_kind, 'transcript_screen'::text as kind_source,
           1 as source_rank, screened_at::timestamptz as screened_at
    from {{ tx }}
    where nullif(trim(meeting_kind), '') is not null and nullif(trim(video_id), '') is not null
    {% else %}
    select null::text as video_id, null::text as meeting_kind, null::text as kind_source, null::int as source_rank,
           null::timestamptz as screened_at
    where false
    {% endif %}
    union all
    {% if meta_exists %}
    select video_id::text, meeting_kind::text, 'video_meta_screen'::text, 2, screened_at::timestamptz
    from {{ meta }}
    where nullif(trim(meeting_kind), '') is not null and nullif(trim(video_id), '') is not null
    {% else %}
    select null::text as video_id, null::text as meeting_kind, null::text as kind_source, null::int as source_rank,
           null::timestamptz as screened_at
    where false
    {% endif %}
)

select distinct on (video_id)
    video_id,
    meeting_kind,
    kind_source,
    screened_at
from answers
order by video_id, source_rank, screened_at desc
