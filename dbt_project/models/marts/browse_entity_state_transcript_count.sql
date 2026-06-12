{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'browse', 'transcripts'],
        contract={'enforced': true}
    )
}}

/*
public.browse_entity_state_transcript_count — per-(entity, STATE) count of
distinct transcripts linked to each browseable homepage entity. The per-state
sibling of browse_transcript_count: where that mart COLLAPSES a topic/question
spanning many states into ONE national row (with a single representative
state_code), this one keeps the genuine per-state grain so the browse pages can
filter to the user's selected place and show ONLY the entities actually
discussed there.

GRAIN: one row per (entity_type, entity_id, state_code) for place | topic |
question. PK = all three columns.

state_code is NEVER NULL here — bridge rows whose per-video state is unknown are
dropped, because an entity with no resolvable state cannot be attributed to a
place. (browse_transcript_count keeps those in its national-collapsed row.)

CAUSES are ABSENT: no cause->transcript linkage and no per-state cause rows exist
in the warehouse, so a place-scoped cause browse honestly has nothing here
(the national honest-zero lives in browse_transcript_count). No fabricated rows.

SOURCE : ref('int_browse_entity_transcripts') — the DISTINCT (entity, video)
         bridge that already carries the per-video state_code.
TARGET : public.browse_entity_state_transcript_count (served via
         publish_public_serving).
*/

with bridge as (
    select * from {{ ref('int_browse_entity_transcripts') }}
)

select
    entity_type::text                       as entity_type,
    entity_id::text                         as entity_id,
    state_code::text                        as state_code,
    max(entity_name)::text                  as entity_name,
    count(distinct video_id)::integer       as transcript_count
from bridge
where state_code is not null
group by entity_type, entity_id, state_code
