{{ config(materialized='table', tags=['intermediate', 'policy-questions', 'transcript', 'keyword-fts']) }}

/*
    Policy question <-> transcript matches by the question's curated alias phrases
    (#499 split this out of question_transcript_link so the evidence step reads a
    real table with statistics). Grain: one row per (question_id, video_id).
    See question_transcript_link for the matching rules; NO LLM.
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
      -- Junk-channel gate (#499): only videos the served YouTube feed keeps.
      -- event_youtube_with_jurisdiction drops channels the classifier marked junk
      -- or non-government (bronze_youtube_channel_classification).
      and d.video_id in (select video_id from {{ ref('event_youtube_with_jurisdiction') }})
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
    question_id::text          as question_id,
    video_id::text             as video_id,
    event_title::text          as event_title,
    event_date::date           as event_date,
    state_code::text           as state_code,
    state::text                as state,
    city::text                 as city,
    jurisdiction_name::text    as jurisdiction_name,
    video_url::text            as video_url,
    n_alias_hits::integer      as n_alias_hits
from scored
