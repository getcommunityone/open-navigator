{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'browse', 'transcripts'],
        contract={'enforced': true}
    )
}}

/*
public.browse_entity_place_transcript_count — per-(entity, PLACE) count of
distinct transcripts linked to each browseable homepage entity. The city-grain
sibling of browse_entity_state_transcript_count: where that mart keeps the
per-STATE grain, this one drills one level finer to (state_code,
jurisdiction_name) so the browse pages can filter topics to a single city like
Tuscaloosa, AL and show only the entities actually discussed there with a
city-scoped transcript count.

GRAIN: one row per (entity_type, entity_id, state_code, jurisdiction_name) for
place | topic | question. PK = all four columns.

BOTH state_code AND jurisdiction_name are NEVER NULL here. A place-scoped count
needs a fully resolved place: a row whose per-video state OR jurisdiction name is
unknown cannot be attributed to a city, so it is dropped (the coarser
browse_entity_state_transcript_count keeps the state-only rows; the national
browse_transcript_count keeps the rest). No fabricated place rows.

TOPIC is the leg that matters here: ed.jurisdiction_name is carried per-video
from public.event_documents, so a topic spanning many cities yields one honest
row per city it was actually discussed in.

QUESTIONs are honestly ABSENT at city grain: the question join path
(policy_question -> event_meeting) exposes state but no clean normalized place
name, so jurisdiction_name is NULL on every question bridge row and they are all
dropped by the WHERE. Likewise CAUSES have no transcript linkage at all. Neither
is fabricated into existence at this grain.

SOURCE : ref('int_browse_entity_transcripts') — the DISTINCT (entity, video)
         bridge that now carries both per-video state_code AND jurisdiction_name.
TARGET : public.browse_entity_place_transcript_count (served via
         publish_public_serving).
*/

with bridge as (
    select * from {{ ref('int_browse_entity_transcripts') }}
)

select
    entity_type::text                       as entity_type,
    entity_id::text                         as entity_id,
    state_code::text                        as state_code,
    jurisdiction_name::text                 as jurisdiction_name,
    max(entity_name)::text                  as entity_name,
    count(distinct video_id)::integer       as transcript_count
from bridge
where state_code is not null
  and jurisdiction_name is not null
group by entity_type, entity_id, state_code, jurisdiction_name
