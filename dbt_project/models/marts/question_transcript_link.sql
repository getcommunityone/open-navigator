{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'policy-questions', 'transcript', 'keyword-fts'],
        contract={'enforced': true}
    )
}}

/*
public.question_transcript_link — curated policy QUESTION <-> transcript links via
the question's ALIAS keyword phrases. This is the "discussed in N meetings"
fallback surface for the Browse Questions page: many featured questions (e.g.
water fluoridation) have ZERO structured decision-instances because the Gemini
analysis never minted a themed event_decision, yet the topic is genuinely debated
in real meetings. This mart finds those meetings honestly — NO LLM, NO fabricated
links — by full-text matching each question's curated alias phrases against the
transcript universe.

WHY ALIASES (not canonical_text): canonical_text is a neutral question SENTENCE
("Should the jurisdiction adjust its water fluoridation policy?") that never
appears verbatim in a transcript. The curated `aliases` column
(curated_policy_questions seed, pipe-delimited: 'fluoridation|fluoride|water
fluoridation') is the on-topic keyword vocabulary that DOES appear — so aliases
do double duty: /search synonyms AND this transcript matcher.

NO LLM. Reuses gold.event_documents.content_tsv (already populated + GIN-indexed
for all ~119k transcript videos). No new tsvector/index is built.

PRECISION: each alias is a SPECIFIC term/phrase (unlike the generic CivicSearch
keyword vocab that forced int_transcript_keyword_topic's >=2-phrase threshold), so
a single alias-phrase hit is a defensible "this meeting discussed it" signal.
n_alias_hits is kept so the API can order by relevance and the UI can label the
match honestly ("mentioned in N meetings"). Matches are scoped to curated/featured
questions only (the seed) — the same set the Browse Questions page surfaces.

INJECTION SAFETY: every alias goes through phraseto_tsquery('english', <alias>),
which fully sanitizes free text into lexemes; no raw alias becomes a tsquery
operator.

GRAIN: one row per (question_id, video_id) — DISTINCT.
PK   : question_transcript_link_id = md5(question_id|video_id).
FK   : question_id -> policy_question (enforced).

SOURCE : curated_policy_questions (canonical_text/primary_theme/aliases),
         event_documents (transcript, content_tsv, place + video metadata).
TARGET : public.question_transcript_link (served via publish_public_serving).
*/

with

-- Curated featured questions exploded to one row per (question_id, alias). The
-- question_id mirrors policy_question's curated branch:
-- md5(primary_theme || '|' || canonical_text). Aliases are pipe-delimited in the
-- seed; blanks are dropped so a question with no aliases contributes nothing.
question_alias as (
    select
        md5(primary_theme || '|' || canonical_text) as question_id,
        trim(a)                                     as alias
    from {{ ref('curated_policy_questions') }},
         unnest(string_to_array(aliases, '|')) as a
    where trim(coalesce(a, '')) <> ''
),

-- Sanitize each alias into a phrase tsquery; drop any that lexes to nothing.
valid_alias as (
    select
        question_id,
        alias,
        nullif(phraseto_tsquery('english', alias)::text, '') as pq
    from question_alias
),

valid as (
    select question_id, alias, pq
    from valid_alias
    where pq is not null
),

-- Canonical transcript universe: one row per video_id (longest transcript wins),
-- carrying the place + video metadata used for the drill-through cards.
doc as (
    select distinct on (d.video_id)
        d.video_id,
        d.content_tsv,
        d.event_title,
        d.event_date,
        d.state_code,
        d.state,
        d.city,
        d.jurisdiction_name,
        d.video_url
    from {{ ref('event_documents') }} d
    where d.document_type = 'transcript'
      and d.video_id is not null
      and d.content_tsv is not null
    order by d.video_id, d.content_length desc nulls last
),

-- One row per (video, question, alias) that hit.
hit as (
    select
        d.video_id,
        v.question_id,
        v.alias,
        d.event_title,
        d.event_date,
        d.state_code,
        d.state,
        d.city,
        d.jurisdiction_name,
        d.video_url
    from doc d
    join valid v
        on d.content_tsv @@ v.pq::tsquery
),

scored as (
    select
        question_id,
        video_id,
        max(event_title)            as event_title,
        max(event_date)             as event_date,
        max(state_code)             as state_code,
        max(state)                  as state,
        max(city)                   as city,
        max(jurisdiction_name)      as jurisdiction_name,
        max(video_url)              as video_url,
        count(distinct alias)       as n_alias_hits
    from hit
    group by question_id, video_id
)

select
    md5(question_id || '|' || video_id) as question_transcript_link_id,
    question_id::text                   as question_id,
    video_id::text                      as video_id,
    event_title::text                   as event_title,
    event_date::date                    as event_date,
    state_code::text                    as state_code,
    state::text                         as state,
    city::text                          as city,
    jurisdiction_name::text             as jurisdiction_name,
    video_url::text                     as video_url,
    n_alias_hits::integer               as n_alias_hits
from scored
