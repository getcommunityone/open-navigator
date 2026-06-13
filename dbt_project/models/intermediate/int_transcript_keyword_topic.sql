{{
    config(
        materialized='table',
        tags=['intermediate', 'browse', 'transcripts', 'topic', 'keyword-fts'],
        post_hook=[
            "create index if not exists {{ this.name }}_topic_idx on {{ this }} (topic_id)",
            "create index if not exists {{ this.name }}_video_idx on {{ this }} (video_id)"
        ]
    )
}}

/*
int_transcript_keyword_topic — pure-SQL/dbt full-text TOPIC tagging of the FULL
transcript universe (~119k videos), NOT just the ~6k AI-analyzed event_meeting
grain. This is the high-recall keyword layer the homepage Browse cards needed:
the AI path (int_meeting_topic_civicsearch -> meeting_topic_link's
'civicsearch_topic'/'canonical_theme') only ever touches videos that became an
event_meeting, so topic transcript coverage was stuck at ~3k. This model matches
every texted transcript in gold.event_documents directly.

NO LLM. Reuses gold.event_documents.content_tsv (already populated for all
119,394 transcript videos) and its existing GIN index
(event_documents_content_tsv_idx) — no new tsvector/index is built.

GRAIN: one row per (video_id, topic_id) — DISTINCT — carrying the place's
state_code + jurisdiction_name (from int_browse_entity_transcripts' place leg) so
the link rolls up by state/place downstream. link_type is stamped
'transcript_keyword' by the consuming mart so it stays HONESTLY distinguishable
from the AI 'civicsearch_topic'/'canonical_theme' tags (these are high-recall /
lower-precision keyword hits, NOT AI themes — see CLAUDE.md No Fabricated Data).

PRECISION STRATEGY (spot-checked before materializing): the CivicSearch
keyword_stats vocabulary is generic ("house", "million", "officer"), so a loose
OR over single words matched ~100k/119k videos for EVERY topic — useless. We
therefore:
  1. keep ONLY multi-word phrases (>= 2 tokens) from keyword_stats — the
     specific, on-topic phrases ("affordable housing", "police chief"); single
     generic words are dropped.
  2. DROP procedural-boilerplate phrases that CivicSearch's keyword_stats include
     but that carry no topical meaning ("moving forward", "motion to adjourn",
     "floor is yours", "will faithfully" — present in 20k-66k meetings each and
     the dominant cause of over-matching on "Development projects" before the
     filter). See stop_phrase below.
  3. match each phrase with phraseto_tsquery (ordered <-> phrase match, not loose
     AND), and
  4. REQUIRE >= 2 DISTINCT phrase hits per (video, topic). One incidental phrase
     is not a topic; two distinct on-topic phrases is a defensible signal.
Eyeballed ~housing/budget/police/mental-health samples: matches are genuinely
on-topic at this threshold.

INJECTION SAFETY: every phrase goes through phraseto_tsquery('english', <kw>),
which fully sanitizes free text into lexemes; no raw keyword becomes a tsquery
operator.

SOURCE : civicsearch_topic (keyword_stats[]), event_documents (transcript,
         content_tsv, state_code, jurisdiction_name — the same columns the
         bridge's place leg derives from; read here directly to avoid a DAG
         cycle with int_browse_entity_transcripts, which consumes this model).
TARGET : gold.int_transcript_keyword_topic (consumed by
         int_browse_entity_transcripts).
*/

with

-- Procedural-boilerplate phrases to exclude: present in 20k-66k meetings, carry
-- no topical meaning. Matched on the normalized lexeme form so casing/stemming
-- variants are all caught.
stop_phrase(pq_text) as (
    select phraseto_tsquery('english', p)::text
    from (values
        ('moving forward'),
        ('move forward'),
        ('floor is yours'),
        ('motion to adjourn'),
        ('entertain a motion to adjourn'),
        ('will faithfully')
    ) as v(p)
),

-- Multi-word topic phrases only (>= 2 tokens), sanitized to a phrase tsquery,
-- minus the procedural stop-phrases.
topic_phrase as (
    select
        t.topic_id,
        t.name                                              as topic_name,
        kw.elem                                             as keyword,
        nullif(phraseto_tsquery('english', kw.elem)::text, '') as pq
    from {{ ref('civicsearch_topic') }} t
    cross join lateral jsonb_array_elements_text(t.keyword_stats) as kw(elem)
    where array_length(regexp_split_to_array(trim(kw.elem), '\s+'), 1) >= 2
      and nullif(phraseto_tsquery('english', kw.elem)::text, '')
          not in (select pq_text from stop_phrase where pq_text is not null)
),

valid_phrase as (
    select topic_id, topic_name, keyword, pq
    from topic_phrase
    where pq is not null
),

-- Canonical transcript universe with its place state/jurisdiction, read
-- straight from event_documents (one row per transcript video_id). Only videos
-- that resolve to a place (state_code present) are kept, so every keyword-topic
-- link carries a real state_code + jurisdiction.
transcript_place as (
    select distinct on (d.video_id)
        d.video_id,
        d.jurisdiction_name,
        d.state_code
    from {{ ref('event_documents') }} d
    where d.document_type = 'transcript'
      and d.video_id is not null
      and d.state_code is not null
    order by d.video_id, d.content_length desc nulls last
),

doc as (
    select distinct on (d.video_id)
        d.video_id,
        d.content_tsv
    from {{ ref('event_documents') }} d
    where d.document_type = 'transcript'
      and d.video_id is not null
      and d.content_tsv is not null
    order by d.video_id, d.content_length desc nulls last
),

-- One row per (video, topic, phrase) that hit; count DISTINCT phrases per pair.
phrase_hit as (
    select
        d.video_id,
        vp.topic_id,
        vp.topic_name,
        vp.keyword
    from doc d
    join valid_phrase vp
        on d.content_tsv @@ vp.pq::tsquery
),

scored as (
    select
        video_id,
        topic_id,
        max(topic_name)             as topic_name,
        count(distinct keyword)     as n_phrase_hits
    from phrase_hit
    group by video_id, topic_id
)

select distinct
    s.video_id::text            as video_id,
    s.topic_id::text            as topic_id,
    s.topic_name::text          as topic_name,
    tp.state_code::text         as state_code,
    tp.jurisdiction_name::text  as jurisdiction_name,
    s.n_phrase_hits::integer    as n_phrase_hits
from scored s
join transcript_place tp
    on tp.video_id = s.video_id
where s.n_phrase_hits >= 2
