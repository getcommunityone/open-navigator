{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'meeting-browse', 'topic', 'transcript', 'keyword-fts'],
        contract={'enforced': true},
        post_hook=[
            "create index if not exists {{ this.name }}_topic_state_idx on {{ this }} (topic_id, state_code)"
        ]
    )
}}

/*
public.topic_transcript_link — curated TOPIC <-> meeting transcript links, each
carrying a VERBATIM, highlighted evidence passage. Powers the "Meetings that
discuss <topic>" tiles on Browse Topics (issue #500, e.g. "Data centers").

WHY A STORED PASSAGE: the CLAUDE.md match-evidence rule wants every filtered tile
to quote where the term appears. Production (Neon) event_documents carries NO
transcript `content` (#496), so the API can't run ts_headline live there. The
passage is cut here, in dbt, from the full local transcript, and published as a
small column (one ~500-char passage per row).

SCOPE: curated topics only (civicsearch_topic.source = 'curated'). The
CivicSearch topics' keyword links number ~80k and would cost tens of MB on Neon;
they keep their existing decision cards.

LINKS = int_transcript_keyword_topic's curated rows, unchanged (1 specific
keyword-phrase hit; the place must resolve to a state). So this mart's counts
equal browse_transcript_count / browse_entity_state_transcript_count for the topic.

PASSAGE: ts_headline('english', content, <OR of the topic's phrase tsqueries>)
with <mark>…</mark> around the matched words (the highlightSnippet convention).
It is a verbatim excerpt of the caption text: never paraphrased. NO LLM.
On very long transcripts ts_headline over the whole text can return no highlight;
the passage is then re-cut from a 3,000-char window around the first mention. If
neither carries a <mark>, evidence_passage is NULL (never an unhighlighted quote
posing as evidence) and the tile shows no quote.

GRAIN: one row per (topic_id, video_id).
PK   : topic_transcript_link_id = md5(topic_id|video_id).
FK   : topic_id -> civicsearch_topic (enforced).

SOURCE : int_transcript_keyword_topic, civicsearch_topic, event_documents.
TARGET : public.topic_transcript_link (served via publish_public_serving).
*/

{%- set hl_opts = "'MaxFragments=2, MinWords=12, MaxWords=35, FragmentDelimiter=\" … \", StartSel=<mark>, StopSel=</mark>'" -%}

with

curated_topic as (
    select topic_id, keyword_stats
    from {{ ref('civicsearch_topic') }}
    where source = 'curated'
),

-- One OR-tsquery per curated topic, built from the same phrases the link model
-- matched (phraseto_tsquery sanitizes each keyword; no raw text becomes an
-- operator). Used only to place the <mark> highlights.
-- kw_regex: the same keywords as a case-insensitive word-start regex (regex
-- metacharacters escaped, spaces -> \s+), used only to find WHERE in a very long
-- transcript the first mention sits (see PASSAGE below).
topic_query as (
    select
        t.topic_id,
        string_agg(distinct nullif(phraseto_tsquery('english', kw.elem)::text, ''), ' | ') as tsq,
        string_agg(
            distinct '\m' || regexp_replace(
                regexp_replace(trim(kw.elem), '([.^$*+?()\[\]{}|\\])', '\\\1', 'g'),
                '\s+', '\\s+', 'g'
            ),
            '|'
        ) as kw_regex
    from curated_topic t
    cross join lateral jsonb_array_elements_text(t.keyword_stats) as kw(elem)
    group by t.topic_id
),

link as (
    select
        l.topic_id::integer     as topic_id,
        l.video_id,
        l.state_code,
        l.jurisdiction_name,
        l.n_phrase_hits
    from {{ ref('int_transcript_keyword_topic') }} l
    join curated_topic t
        on t.topic_id = l.topic_id::integer
),

-- Same canonical transcript the link model matched: longest per video_id.
doc as (
    select distinct on (d.video_id)
        d.video_id,
        d.content,
        d.event_title,
        d.event_date,
        d.state_code,
        d.state,
        d.city,
        d.jurisdiction_name,
        d.video_url
    from {{ ref('event_documents') }} d
    where d.document_type = 'transcript'
      and d.video_id in (select video_id from link)
      and d.content_tsv is not null
    order by d.video_id, d.content_length desc nulls last
)

select
    md5(l.topic_id::text || '|' || l.video_id)::text as topic_transcript_link_id,
    l.topic_id::integer                              as topic_id,
    l.video_id::text                                 as video_id,
    d.event_title::text                              as event_title,
    d.event_date::date                               as event_date,
    -- Place comes from the link model (the same place its state counts use);
    -- state/city are only carried when the document agrees on the state.
    l.state_code::text                               as state_code,
    case when d.state_code = l.state_code then d.state end::text as state,
    case when d.state_code = l.state_code then d.city end::text  as city,
    l.jurisdiction_name::text                        as jurisdiction_name,
    d.video_url::text                                as video_url,
    l.n_phrase_hits::integer                         as n_keyword_hits,
    case
        when h.full_hl like '%<mark>%' then h.full_hl
        when h.window_hl like '%<mark>%' then h.window_hl
    end::text                                        as evidence_passage
from link l
join doc d
    on d.video_id = l.video_id
join topic_query q
    on q.topic_id = l.topic_id
cross join lateral (
    select
        nullif(trim(ts_headline('english', d.content, to_tsquery('english', q.tsq), {{ hl_opts }})), '') as full_hl,
        -- Fallback for very long transcripts, where ts_headline over the whole
        -- text can come back without a highlight: re-cut it from a 3,000-char
        -- window around the first regex mention.
        nullif(trim(ts_headline(
            'english',
            substr(d.content, greatest(1, regexp_instr(d.content, q.kw_regex, 1, 1, 0, 'i') - 1500), 3000),
            to_tsquery('english', q.tsq),
            {{ hl_opts }}
        )), '') as window_hl
) h
