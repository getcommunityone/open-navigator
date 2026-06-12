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

  * place / topic / question rows come from int_browse_entity_transcripts, the
    DISTINCT (entity, video) bridge, GROUP BY-ed to COUNT(DISTINCT video_id).
    state_code is the per-video state, so an entity may span several states; the
    GROUP BY collapses to ONE row per (entity_type, entity_id) because the bridge
    already has at most one state_code per video and we aggregate over the entity.
    (A topic that appears in multiple states is summed into a single national
    row here; per-state breakdowns live in browse_directory_summary.)
  * cause rows are unioned in from public.tag (vocabulary='ntee') with
    transcript_count = 0 and state_code = NULL — there is NO cause->transcript
    linkage in the warehouse, so 0 is the honest value (no fabricated data).

SOURCE : ref('int_browse_entity_transcripts') + ref('tag').
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
),

causes as (
    select
        'cause'::text                           as entity_type,
        t.tag_id::text                          as entity_id,
        t.label::text                           as entity_name,
        cast(null as text)                      as state_code,
        0::integer                              as transcript_count
    from {{ ref('tag') }} t
    where t.vocabulary = 'ntee'
)

select
    entity_type::text                           as entity_type,
    entity_id::text                             as entity_id,
    entity_name::text                           as entity_name,
    state_code::text                            as state_code,
    transcript_count::integer                   as transcript_count
from linked

union all

select
    entity_type,
    entity_id,
    entity_name,
    state_code,
    transcript_count
from causes
