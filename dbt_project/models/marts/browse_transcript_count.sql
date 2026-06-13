{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'browse', 'transcripts'],
        contract={'enforced': true}
    )
}}

/*
public.browse_transcript_count — item-grain count of distinct transcripts linked
to each browseable homepage entity (place | topic | question | cause).

GRAIN: one row per (entity_type, entity_id, state_code). PK = (entity_type,
entity_id) — see note below on why state_code is NOT in the PK.

  * place / topic / question / cause rows ALL come from
    int_browse_entity_transcripts, the DISTINCT (entity, video) bridge, GROUP
    BY-ed to COUNT(DISTINCT video_id). state_code is the per-video state, so an
    entity may span several states; the GROUP BY collapses to ONE row per
    (entity_type, entity_id) because the bridge already has at most one
    state_code per video and we aggregate over the entity. (A topic/cause that
    appears in multiple states is summed into a single national row here;
    per-state breakdowns live in browse_directory_summary.)
  * cause rows now carry REAL transcript counts from the keyword-FTS layer
    (int_transcript_keyword_cause, EveryOrg cause taxonomy) — the prior
    honest-zero NTEE-tag union is retired now that a genuine cause->transcript
    linkage exists.

SOURCE : ref('int_browse_entity_transcripts').
TARGET : public.browse_transcript_count (served via publish_public_serving).

PK NOTE: the entity grain is (entity_type, entity_id). state_code here is a
denormalized "representative" attribute (NULL for causes; for place it is the
place's state; for topic/question it is a representative state). The grain is
one row per entity, so the PK is (entity_type, entity_id) — state_code is not
part of the key.
*/

with

bridge as (
    select * from {{ ref('int_browse_entity_transcripts') }}
),

linked as (
    select
        entity_type,
        entity_id,
        max(entity_name)                        as entity_name,
        -- A single representative state per entity (place is single-state; topic
        -- / question may span states — take the lexically-first non-null).
        min(state_code)                         as state_code,
        count(distinct video_id)::integer       as transcript_count
    from bridge
    group by entity_type, entity_id
)

select
    entity_type::text                           as entity_type,
    entity_id::text                             as entity_id,
    entity_name::text                           as entity_name,
    state_code::text                            as state_code,
    transcript_count::integer                   as transcript_count
from linked
