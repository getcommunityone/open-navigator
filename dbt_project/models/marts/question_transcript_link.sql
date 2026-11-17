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

MATCH EVIDENCE (#499): every row carries `evidence`, a verbatim passage of the
transcript with the question's alias words <mark>ed by ts_headline (CLAUDE.md
"Show the match evidence on filtered tiles"), and `start_seconds`, the moment
to jump to. It is computed here, in the local warehouse, because production
Neon's event_documents carries no transcript text (#496): the passage travels on
this table instead.
  * Timed (the transcript has caption segments): cues are cut into ~3-minute
    windows (floor(start / 180)); the first window whose text matches the
    question's alias query is the passage, and start_seconds is the first cue
    in it (alone or joined with the next cue of the window, so a phrase split
    across two cues still counts) that matches, else the window's start.
  * Untimed (no segments): ts_headline over the whole transcript text;
    start_seconds is null and the UI links to the meeting without a time.
A link whose evidence has no <mark> is dropped: no bare tile, no spurious match.

GRAIN: one row per (question_id, video_id) — DISTINCT.
PK   : question_transcript_link_id = md5(question_id|video_id).
FK   : question_id -> policy_question (enforced).

SOURCE : int_question_transcript_link__match (the alias matches: curated_policy_questions
         x event_documents.content_tsv, junk-channel gated by event_youtube_with_jurisdiction),
         int_question_transcript_link__evidence (the passage + jump time).
TARGET : public.question_transcript_link (served via publish_public_serving).
*/

select
    md5(m.question_id || '|' || m.video_id) as question_transcript_link_id,
    m.question_id::text                     as question_id,
    m.video_id::text                        as video_id,
    m.event_title::text                     as event_title,
    m.event_date::date                      as event_date,
    m.state_code::text                      as state_code,
    m.state::text                           as state,
    m.city::text                            as city,
    m.jurisdiction_name::text               as jurisdiction_name,
    m.video_url::text                       as video_url,
    m.n_alias_hits::integer                 as n_alias_hits,
    e.evidence::text                        as evidence,
    e.start_seconds::numeric(12, 3)         as start_seconds
from {{ ref('int_question_transcript_link__match') }} m
join {{ ref('int_question_transcript_link__evidence') }} e
  on e.question_id = m.question_id
 and e.video_id = m.video_id
where e.evidence like '%<mark>%'
