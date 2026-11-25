{{
    config(
        materialized='table',
        indexes=[
          {'columns': ["topic_id"], 'type': 'btree'},
          {'columns': ["c1_event_id"], 'type': 'btree'}
        ],
        tags=['intermediate', 'browse', 'decisions', 'topic', 'keyword-fts']
    )
}}

/*
int_decision_topic — pure-SQL/dbt full-text TOPIC tagging at the DECISION grain
(public.event_decision). The decision sibling of int_transcript_keyword_topic.

WHY: the meeting browse for topics should link to DECISIONS first (rolled up to
meetings via c1_event_id), falling back to transcript keyword matches only when a
meeting has no decisions. This model is the decision leg: it matches the SAME
CivicSearch multi-word phrase vocabulary against the decision TEXT (headline +
decision_statement), NOT the AI primary_theme — a deliberate keyword-match
choice so the linkage is an honest, traceable keyword signal.

NO LLM.

GRAIN: one row per (event_decision_id, topic_id) — DISTINCT. Carries c1_event_id
(for the meeting roll-up) + topic_name.

PRECISION STRATEGY: mirrors int_transcript_keyword_topic EXACTLY —
  1. keep ONLY multi-word phrases (>= 2 tokens) from civicsearch_topic.keyword_stats
     (drop generic single words),
  2. DROP the same procedural-boilerplate stop-phrases,
  3. match each phrase with phraseto_tsquery (ordered <-> phrase match), and
  4. REQUIRE >= 2 DISTINCT phrase hits per (decision, topic).
Matched against the much shorter decision headline+statement instead of the full
transcript, so the >= 2 distinct phrase threshold is, if anything, stricter here.

CURATED TOPICS (issue #500, source = 'curated', e.g. "Data centers"): their
keywords are hand-picked SPECIFIC phrases ("data center", "hyperscale"), so steps
1 and 4 are relaxed for them: single-word keywords are kept and ONE phrase hit is
a match. This is the same rule question_transcript_link applies to curated
question aliases. CivicSearch topics keep the >= 2 rule.

INJECTION SAFETY: every phrase goes through phraseto_tsquery('english', <kw>);
no raw keyword becomes a tsquery operator.

SOURCE : civicsearch_topic (keyword_stats[]), event_decision (headline,
         decision_statement, c1_event_id).
TARGET : gold.int_decision_topic (consumed by meeting_topic_link).
*/

with

-- Procedural-boilerplate phrases to exclude — KEEP IN SYNC with
-- int_transcript_keyword_topic.stop_phrase.
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
        t.source                                            as topic_source,
        kw.elem                                             as keyword,
        nullif(phraseto_tsquery('english', kw.elem)::text, '') as pq
    from {{ ref('civicsearch_topic') }} t
    cross join lateral jsonb_array_elements_text(t.keyword_stats) as kw(elem)
    -- CivicSearch: multi-word phrases only. Curated (issue #500): every keyword,
    -- single words included ("hyperscale") — the vocabulary is hand-picked.
    where (
            t.source = 'curated'
         or array_length(regexp_split_to_array(trim(kw.elem), '\s+'), 1) >= 2
      )
      and nullif(phraseto_tsquery('english', kw.elem)::text, '')
          not in (select pq_text from stop_phrase where pq_text is not null)
),

valid_phrase as (
    select topic_id, topic_name, topic_source, keyword, pq
    from topic_phrase
    where pq is not null
),

-- Decision text universe: one tsvector per decision from headline +
-- decision_statement. Only decisions with a c1_event_id (the meeting roll-up
-- key) are kept.
decision_doc as (
    select
        d.event_decision_id,
        d.c1_event_id,
        to_tsvector(
            'english',
            lower(coalesce(d.headline, '') || ' ' || coalesce(d.decision_statement, ''))
        ) as content_tsv
    from {{ ref('event_decision') }} d
    where d.c1_event_id is not null
      and (
            nullif(trim(coalesce(d.headline, '')), '') is not null
         or nullif(trim(coalesce(d.decision_statement, '')), '') is not null
      )
),

phrase_hit as (
    select
        dd.event_decision_id,
        dd.c1_event_id,
        vp.topic_id,
        vp.topic_name,
        vp.topic_source,
        vp.keyword
    from decision_doc dd
    join valid_phrase vp
        on dd.content_tsv @@ vp.pq::tsquery
),

scored as (
    select
        event_decision_id,
        c1_event_id,
        topic_id,
        max(topic_name)             as topic_name,
        max(topic_source)           as topic_source,
        count(distinct keyword)     as n_phrase_hits
    from phrase_hit
    group by event_decision_id, c1_event_id, topic_id
)

select distinct
    s.event_decision_id::text   as event_decision_id,
    s.c1_event_id::text         as c1_event_id,
    s.topic_id::text            as topic_id,
    s.topic_name::text          as topic_name,
    s.n_phrase_hits::integer    as n_phrase_hits
from scored s
-- CivicSearch topics need >= 2 distinct phrases (generic vocabulary); a curated
-- topic's keywords are specific, so 1 hit is a match (as question_transcript_link
-- does for curated question aliases).
where s.n_phrase_hits >= case when s.topic_source = 'curated' then 1 else 2 end
