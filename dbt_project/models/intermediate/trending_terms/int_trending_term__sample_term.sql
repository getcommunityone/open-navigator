{{ config(
    post_hook=["analyze {{ this }}"],
    materialized='table',
    tags=['intermediate', 'trending_terms'],
    indexes=[{'columns': ['term']}],
    pre_hook=["set local work_mem = '64MB'", "set local statement_timeout = '30min'"]
) }}

/*
    Surface 1-3 word terms said in public-comment speaker turns of a fixed sample of meetings (#1399): one row per
    (term, n_words) with the sampled meetings and governments that said it (3+ meetings). The input of
    int_trending_term__candidate, kept as its own table so the filters can change without re-tokenizing.

    Sample: up to var trending_sample_per_year counted meetings with turns per year, ordered by md5(video_id), so
    every rebuild picks the same meetings. Text: the meeting's public-comment segments (is_public_comment, never a
    possible minor). Each meeting is tokenized inside a LATERAL, one at a time, so no table ever holds every token.
    A term never starts or ends with an English stopword, a word with an apostrophe or a one- or two-letter word.
*/

{%- set per_year = var('trending_sample_per_year', 750) %}

with meeting_text as (
    select
        f.video_id,
        string_agg(f.comment_text, ' | ' order by f.comment_index) as txt
    from {{ ref('int_meeting_comment__flags') }} as f
    inner join {{ ref('int_trending_term__meeting') }} as m on m.video_id = f.video_id and m.counted
    where f.is_public_comment and not f.possible_minor
    group by f.video_id
),

sample as (
    select s.video_id, s.jurisdiction_key, mt.txt
    from (
        select m.video_id, m.jurisdiction_key,
               row_number() over (partition by m.meeting_year order by md5(m.video_id)) as rn
        from {{ ref('int_trending_term__meeting') }} as m
        where m.counted and m.has_turns and m.video_id in (select video_id from meeting_text)
    ) as s
    inner join meeting_text as mt on mt.video_id = s.video_id
    where s.rn <= {{ per_year }}
),

sample_size as (
    select count(*)::numeric as n from sample
),

-- Per meeting: its distinct 1-3 word terms (computed inside the lateral, one meeting at a time).
meeting_term as (
    select s.video_id, s.jurisdiction_key, g.term, g.n_words
    from sample as s
    cross join lateral (
        select distinct u.term, u.n_words
        from (
            select w, lead(w) over (order by o) as w2, lead(w, 2) over (order by o) as w3
            from regexp_split_to_table(lower(s.txt), '[^a-z'']+') with ordinality as t(w, o)
        ) as x
        cross join lateral (values
            (x.w, 1, x.w, x.w),
            (x.w || ' ' || x.w2, 2, x.w, x.w2),
            (x.w || ' ' || x.w2 || ' ' || x.w3, 3, x.w, x.w3)
        ) as u(term, n_words, first_w, last_w)
        where u.term is not null
          and u.first_w ~ '^[a-z]{3,}$' and u.last_w ~ '^[a-z]{3,}$'
          and ts_lexize('english_stem', u.first_w) <> '{}'
          and ts_lexize('english_stem', u.last_w) <> '{}'
    ) as g
),

surface as (
    select term, n_words,
           count(*)::int                          as sample_meetings,
           count(distinct jurisdiction_key)::int   as sample_jurisdictions
    from meeting_term
    group by term, n_words
    having count(*) >= 3
)

select term::text as term, n_words::int as n_words, sample_meetings::int as sample_meetings,
       sample_jurisdictions::int as sample_jurisdictions, ss.n::int as sample_size
from surface
cross join sample_size as ss
