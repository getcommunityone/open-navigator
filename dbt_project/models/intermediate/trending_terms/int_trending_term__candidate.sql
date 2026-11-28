{{ config(
    post_hook=["analyze {{ this }}"],
    materialized='table',
    tags=['intermediate', 'trending_terms'],
    indexes=[{'columns': ['term_key'], 'unique': true}],
    pre_hook=["set local work_mem = '64MB'", "set local statement_timeout = '30min'"]
) }}

/*
    Candidate trending terms (#1399): one row per term key (a 1-3 word phrase in its stemmed full-text form, so
    "data center" and "data centers" are one term), with the filter decision. Free and deterministic: no LLM.

    WHERE CANDIDATES COME FROM. int_trending_term__sample_term: surface terms said in public-comment speaker turns of a
    fixed sample of meetings (see that model). Terms then get counted over every meeting's transcript in
    int_trending_term__jurisdiction_year.

    FILTERS, in order (drop_reason; null = kept):
      excluded_word     first or last word is in trending_term_excluded with match = 'word' (filler, procedural,
                        generic: "going", "motion", "council", "people").
      excluded_phrase   contains a trending_term_excluded phrase ("public hearing", "roll call", "my name").
      thin_sample       fewer than var trending_sample_min_meetings sampled meetings or
                        var trending_sample_min_jurisdictions governments.
      too_common        said in more than var trending_max_doc_share of the sampled meetings: a word everyone says
                        can't be a trend.
      person_name       shaped like a person's name (privacy, blocking): a single name word (see name_word below:
                        name data int_trending_term__name_lexicon, weighed against how often the word is said), or a
                        phrase with a given-name word followed by a surname word. Kept only when it is a reviewed public figure
                        (trending_term_public_figure) or, for a first+last name, a public official's name
                        (int_trending_term__official_name); a word on trending_term_common_word ("bill", "park") is
                        not treated as a name. Counted after the other filters, so the number dropped for privacy
                        is the number of otherwise-eligible candidates.
      place_name        the name of a place with var trending_place_min_population (20,000) people or more (a city, or
                        a county without "County"): it rises when we start recording that place, not with talk.
    is_sensitive marks terms naming a health condition, religion, immigration status, sexual orientation, disability,
    race/ethnicity, criminal history or finances (trending_term_sensitive): aggregate counts only, never tied to a
    speaker (the evidence mart drops the speaker for them).
*/

{%- set min_m = var('trending_sample_min_meetings', 6) %}
{%- set min_j = var('trending_sample_min_jurisdictions', 3) %}
{%- set max_share = var('trending_max_doc_share', 0.35) %}
{%- set name_ratio = var('trending_name_ratio', 0.25) %}

with surface as (
    select term, n_words, sample_meetings, sample_jurisdictions from {{ ref('int_trending_term__sample_term') }}
),

sample_size as (
    select coalesce(max(sample_size), 0)::numeric as n from {{ ref('int_trending_term__sample_term') }}
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

-- A word that is a person's name here: used as a given name by 2+ people or a surname by 3+ in our name data, AND
-- those name uses are at least var trending_name_ratio of the sampled meetings that say it ("john": 1,050 name uses,
-- said in 298 meetings -> a name; "budget": 3 surname uses, said in 474 meetings -> a word). A word too rare to be a
-- unigram candidate counts as a name whenever it is in the name data. Common civic words that are also names
-- (trending_term_common_word) never count.
name_word as (
    select
        l.word,
        (l.n_given >= 2 and (l.n_given + l.n_surname) >= {{ name_ratio }} * coalesce(u.sample_meetings, 0)) as is_given,
        (l.n_surname >= 2 and (l.n_given + l.n_surname) >= {{ name_ratio }} * coalesce(u.sample_meetings, 0)) as is_surname,
        ((l.n_given >= 2 or l.n_surname >= 3)
         and (l.n_given + l.n_surname) >= {{ name_ratio }} * coalesce(u.sample_meetings, 0))                  as is_name
    from {{ ref('int_trending_term__name_lexicon') }} as l
    left join term as u on u.n_words = 1 and u.term = l.word
    where l.word not in (select term from common_word)
),

-- Names of places with 20,000+ people (a city "Ann Arbor", a county "DeKalb County" -> "dekalb"): a place name rising
-- mostly says which places we started recording, not what people talk about.
place_name as (
    select distinct lower(btrim(regexp_replace(name,
        '\s+(county|city|town|township|village|borough|parish|municipality|cdp)$', '', 'i'))) as term
    from {{ ref('jurisdictions') }}
    where population >= {{ var('trending_place_min_population', 20000) }} and name is not null
),

-- Phrases with a given-name word followed by a surname word, anywhere in the phrase.
name_pair as (
    select distinct wd.tsq
    from words as wd
    cross join lateral generate_series(1, array_length(wd.w, 1) - 1) as i
    inner join name_word as g on g.word = wd.w[i] and g.is_given
    inner join name_word as sn on sn.word = wd.w[i + 1] and sn.is_surname
    where array_length(wd.w, 1) >= 2
),

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
        (sn1.word is not null)                                                          as single_name,
        exists (select 1 from place_name pl where pl.term = t.term)                     as place_name,
        (np.tsq is not null)                                                            as name_pair,
        (select min(sv.category) from {{ ref('trending_term_sensitive') }} sv
         where (' ' || t.term || ' ') like ('% ' || sv.term || ' %'))                   as sensitive_category
    from term as t
    inner join words as wd on wd.tsq = t.tsq
    left join name_word as sn1 on array_length(wd.w, 1) = 1 and sn1.word = wd.w[1] and sn1.is_name
    left join name_pair as np on np.tsq = t.tsq
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
        when f.place_name then 'place_name'
     end)::text                                                            as drop_reason
from flags as f
cross join sample_size as ss
