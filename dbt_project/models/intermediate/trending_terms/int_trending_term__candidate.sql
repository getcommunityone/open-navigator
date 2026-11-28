{{ config(
    materialized='table',
    tags=['intermediate', 'trending_terms'],
    indexes=[{'columns': ['term_key'], 'unique': true}],
    pre_hook=["set local work_mem = '64MB'", "set local statement_timeout = '15min'"]
) }}

/*
    Candidate trending terms (#1399): one row per term key (a 1-3 word phrase in its stemmed full-text form, so
    "data center" and "data centers" are one term), with the filter decision. Free and deterministic: no LLM.

    WHERE CANDIDATES COME FROM. Public-comment speaker turns (int_meeting_comment__flags, is_public_comment, never a
    possible minor), in a fixed sample of up to var trending_sample_per_year counted meetings with turns per year
    (ordered by md5(video_id), so every rebuild picks the same meetings). Each meeting is tokenized on its own inside a
    LATERAL, so no table ever holds every token: this keeps the build light (an all-token table took the machine
    down). Terms then get counted over every meeting's transcript in int_trending_term__jurisdiction_year.

    FILTERS, in order (drop_reason; null = kept):
      stopword_edge     handled before grouping: a term never starts or ends with an English stopword, a word with an
                        apostrophe ("it's") or a one- or two-letter word.
      excluded_word     first or last word is in trending_term_excluded with match = 'word' (filler, procedural,
                        generic: "going", "motion", "council", "people").
      excluded_phrase   contains a trending_term_excluded phrase ("public hearing", "roll call", "my name").
      thin_sample       fewer than var trending_sample_min_meetings sampled meetings or
                        var trending_sample_min_jurisdictions governments.
      too_common        said in more than var trending_max_doc_share of the sampled meetings: a word everyone says
                        can't be a trend.
      person_name       shaped like a person's name (privacy, blocking): a single word used as a given name by 2+ people
                        or a surname by 3+ people in our name data (int_trending_term__name_lexicon), or a phrase with
                        a given-name word followed by a surname word. Kept only when it is a reviewed public figure
                        (trending_term_public_figure) or, for a first+last name, a public official's name
                        (int_trending_term__official_name); a word on trending_term_common_word ("bill", "park") is
                        not treated as a name. Counted after the other filters, so the number dropped for privacy
                        is the number of otherwise-eligible candidates.
    is_sensitive marks terms naming a health condition, religion, immigration status, sexual orientation, disability,
    race/ethnicity, criminal history or finances (trending_term_sensitive): aggregate counts only, never tied to a
    speaker (the evidence mart drops the speaker for them).
*/

{%- set per_year = var('trending_sample_per_year', 750) %}
{%- set min_m = var('trending_sample_min_meetings', 6) %}
{%- set min_j = var('trending_sample_min_jurisdictions', 3) %}
{%- set max_share = var('trending_max_doc_share', 0.35) %}

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
),

keyed as (
    select
        nullif(phraseto_tsquery('english', s.term)::text, '') as tsq,
        s.*
    from surface as s
),

-- One row per stemmed key; the display form is its most-said surface form.
term as (
    select
        tsq,
        (array_agg(term order by sample_meetings desc, length(term), term))[1]      as term,
        max(n_words)                                                                 as n_words,
        max(sample_meetings)                                                         as sample_meetings,
        max(sample_jurisdictions)                                                    as sample_jurisdictions
    from keyed
    where tsq is not null
    group by tsq
),

words as (
    select t.tsq, string_to_array(t.term, ' ') as w from term as t
),

excluded_word as (select term from {{ ref('trending_term_excluded') }} where match = 'word'),
excluded_phrase as (select term from {{ ref('trending_term_excluded') }} where match = 'phrase'),
common_word as (select term from {{ ref('trending_term_common_word') }}),

flags as (
    select
        t.*,
        wd.w,
        exists (select 1 from excluded_word e where e.term in (wd.w[1], wd.w[array_length(wd.w, 1)]))
            as excluded_word,
        exists (select 1 from excluded_phrase e where (' ' || t.term || ' ') like ('% ' || e.term || ' %'))
            as excluded_phrase,
        exists (select 1 from {{ ref('trending_term_public_figure') }} p where p.term = t.term) as public_figure,
        exists (select 1 from {{ ref('int_trending_term__official_name') }} o
                where o.name_key = t.term
                   or (array_length(wd.w, 1) = 3
                       and o.name_key in (wd.w[1] || ' ' || wd.w[2], wd.w[2] || ' ' || wd.w[3]))) as official_name,
        -- a single word that is a name
        (array_length(wd.w, 1) = 1
         and wd.w[1] not in (select term from common_word)
         and exists (select 1 from {{ ref('int_trending_term__name_lexicon') }} lex where lex.word = wd.w[1] and (lex.n_given >= 2 or lex.n_surname >= 3)))
            as single_name,
        -- a given-name word followed by a surname word, anywhere in the phrase
        (array_length(wd.w, 1) >= 2 and exists (
            select 1
            from generate_series(1, array_length(wd.w, 1) - 1) as i
            inner join {{ ref('int_trending_term__name_lexicon') }} as g on g.word = wd.w[i] and g.n_given >= 2
            inner join {{ ref('int_trending_term__name_lexicon') }} as s on s.word = wd.w[i + 1] and s.n_surname >= 2
            where wd.w[i] not in (select term from common_word)
              and wd.w[i + 1] not in (select term from common_word)
        )) as name_pair,
        (select min(sv.category) from {{ ref('trending_term_sensitive') }} sv
         where (' ' || t.term || ' ') like ('% ' || sv.term || ' %'))                   as sensitive_category
    from term as t
    inner join words as wd on wd.tsq = t.tsq
)

select
    md5(f.tsq)::text                                                       as term_key,
    f.tsq::text                                                            as term_tsquery,
    f.term::text                                                           as term,
    f.n_words::int                                                         as n_words,
    f.sample_meetings::int                                                 as sample_meetings,
    f.sample_jurisdictions::int                                            as sample_jurisdictions,
    (f.sensitive_category is not null)::boolean                            as is_sensitive,
    f.sensitive_category::text                                             as sensitive_category,
    (case
        when f.public_figure then 'public_figure'
        when f.official_name and (f.single_name or f.name_pair) then 'public_official'
     end)::text                                                            as name_allowed_as,
    (case
        when f.excluded_word then 'excluded_word'
        when f.excluded_phrase then 'excluded_phrase'
        when f.sample_meetings < {{ min_m }} or f.sample_jurisdictions < {{ min_j }} then 'thin_sample'
        when f.sample_meetings > {{ max_share }} * ss.n then 'too_common'
        when (f.single_name or f.name_pair) and not f.public_figure
             and not (f.official_name and f.n_words >= 2) then 'person_name'
     end)::text                                                            as drop_reason
from flags as f
cross join sample_size as ss
