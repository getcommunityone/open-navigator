{{
  config(
    materialized='table',
    tags=['intermediate', 'browse', 'transcripts'],
    post_hook=[
      "create index if not exists {{ this.name }}_entity_idx on {{ this }} (entity_type, entity_id)",
      "create index if not exists {{ this.name }}_video_idx on {{ this }} (video_id)"
    ]
  )
}}

/*
  int_browse_entity_transcripts — the bridge/linking table that ties each
  browseable homepage entity (place | topic | question) to the distinct
  transcript videos it is associated with. One row per
  (entity_type, entity_id, video_id); DISTINCT-ed so a downstream
  COUNT(DISTINCT video_id) is the genuine transcript count.

  Canonical transcript universe: public.event_documents
  (document_type = 'transcript', one row per video_id). All three legs are
  scoped to THAT same universe so counts are comparable across entity types.

  CAUSES + the high-recall TOPIC leg now arrive via the pure-SQL keyword FTS
  models (int_transcript_keyword_topic / int_transcript_keyword_cause). These
  match the curated topic/cause keyword vocabularies against the FULL transcript
  universe (~119k videos) — NOT the ~6k AI event_meeting grain — so topic
  coverage jumps and causes get genuine transcript counts for the first time.
  They are a SEPARATE, honestly high-recall keyword signal (see those models'
  headers); the AI civicsearch-snippet topic leg below is kept intact alongside
  them.

  Join paths (verified against localhost:5433/open_navigator):
    * PLACE    — event_documents.jurisdiction_name = jurisdictions.name AND
                 event_documents.state_code = jurisdictions.state_code.
                 entity_id = jurisdictions.geoid. A (name, state_code) pair maps
                 to MULTIPLE geoids (9.6k pairs do), so we pick ONE canonical
                 geoid per place via a window (order by jurisdiction_type, geoid).
                 NB: the simple jurisdiction_type='city' filter was rejected — it
                 drops ~13k transcripts (117,877 -> 104,937) AND still leaves dup
                 geoids; the window preserves the full 117,877 with one geoid/place.
    * TOPIC    — civicsearch_topic ⋈ stg_civicsearch__snippet (topic_id) ⋈
                 event_documents (video_id = snippet.vid_id). This counts the SAME
                 transcript universe as places (the ~3k overlap), NOT the 34k
                 native CivicSearch snippet universe. entity_id = topic_id.
                 state_code is carried per-video from event_documents (a topic
                 spans many videos across many states).
    * QUESTION — policy_question ⋈ question_instance (source_type='local_decision')
                 ⋈ event_decision (event_decision_id = qi.source_id) ⋈
                 event_meeting (legacy_event_id), WHERE video_id IS NOT NULL.
                 entity_id = question_id; state_code from event_meeting.
*/

with

transcripts as (
    select
        video_id,
        jurisdiction_name,
        state_code
    from {{ ref('event_documents') }}
    where document_type = 'transcript'
      and video_id is not null
),

-- One canonical geoid per (name, state_code): a place name maps to several
-- geoids, so collapse to a single representative to avoid fan-out.
jurisdictions_canonical as (
    select
        name,
        state_code,
        geoid,
        row_number() over (
            partition by name, state_code
            order by jurisdiction_type, geoid
        ) as rn
    from {{ ref('jurisdictions') }}
),

place as (
    select distinct
        'place'::text                       as entity_type,
        j.geoid::text                       as entity_id,
        j.name::text                        as entity_name,
        j.state_code::text                  as state_code,
        j.name::text                        as jurisdiction_name,
        t.video_id::text                    as video_id
    from transcripts t
    join jurisdictions_canonical j
        on t.jurisdiction_name = j.name
       and t.state_code = j.state_code
       and j.rn = 1
),

snippets as (
    select distinct
        topic_id,
        vid_id
    from {{ ref('stg_civicsearch__snippet') }}
    where topic_id is not null
      and vid_id is not null
),

topic as (
    select distinct
        'topic'::text                       as entity_type,
        tp.topic_id::text                   as entity_id,
        tp.name::text                       as entity_name,
        ed.state_code::text                 as state_code,
        ed.jurisdiction_name::text          as jurisdiction_name,
        ed.video_id::text                   as video_id
    from {{ ref('civicsearch_topic') }} tp
    join snippets s
        on s.topic_id = tp.topic_id
    join {{ ref('event_documents') }} ed
        on ed.video_id = s.vid_id
       and ed.document_type = 'transcript'
),

question as (
    select distinct
        'question'::text                    as entity_type,
        q.question_id::text                 as entity_id,
        q.canonical_text::text              as entity_name,
        m.state_code::text                  as state_code,
        m.jurisdiction_name::text           as jurisdiction_name,
        m.video_id::text                    as video_id
    from {{ ref('policy_question') }} q
    join {{ ref('question_instance') }} qi
        on qi.question_id = q.question_id
       and qi.source_type = 'local_decision'
    join {{ ref('event_decision') }} d
        on d.event_decision_id = qi.source_id
    join {{ ref('event_meeting') }} m
        on m.legacy_event_id = d.legacy_event_id
    where m.video_id is not null
),

-- Keyword-FTS TOPIC leg: high-recall topic tags over the full transcript
-- universe. Same entity_id space (topic_id) as the AI `topic` leg above, so the
-- two simply UNION more videos onto the same topic entities.
topic_keyword as (
    select distinct
        'topic'::text                       as entity_type,
        tk.topic_id::text                   as entity_id,
        tk.topic_name::text                 as entity_name,
        tk.state_code::text                 as state_code,
        tk.jurisdiction_name::text          as jurisdiction_name,
        tk.video_id::text                   as video_id
    from {{ ref('int_transcript_keyword_topic') }} tk
),

-- Keyword-FTS CAUSE leg: the first real cause -> transcript linkage. entity_id
-- is the EveryOrg cause_id (the taxonomy the Browse Causes pills already use).
cause_keyword as (
    select distinct
        'cause'::text                       as entity_type,
        ck.cause_id::text                   as entity_id,
        ck.cause_name::text                 as entity_name,
        ck.state_code::text                 as state_code,
        ck.jurisdiction_name::text          as jurisdiction_name,
        ck.video_id::text                   as video_id
    from {{ ref('int_transcript_keyword_cause') }} ck
)

select * from place
union all
select * from topic
union all
select * from topic_keyword
union all
select * from cause_keyword
union all
select * from question
