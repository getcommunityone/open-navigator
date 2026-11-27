{{ config(materialized='table', tags=['intermediate', 'topic', 'organization']) }}

/*
    Nonprofits named in a recorded meeting on a curated topic, near the topic's words, in their own state (#1345).
    One row per (topic_id, master_org_id): the most recent such mention.

    High precision by construction:
      1. Passages: every stretch of a topic meeting's transcript (topic_transcript_link -> event_documents) within
         about 400 characters of one of the topic's keyword phrases (civicsearch_topic.keyword_stats). A name said
         elsewhere in a three-hour meeting does not count.
      2. Candidates: nonprofits in the meeting's state whose cleaned name (Inc, Corp, The ... dropped) is at least 12
         characters and two indexed words long, is held by no other nonprofit in that state, and has at least one
         word that is not common in topic passages (in 2% of them or fewer), so "Health Services" or "People Place"
         never match. A candidate must be based in the meeting's city, or already tied to the topic by a rule
         (int_topic_organization__rule_match), e.g. a statewide advocacy group.
      3. Match: the passage contains the whole name, word for word (a full-text phrase match, then a regex on the
         passage's own words).

    match_text is the passage with the name and the topic's words in <mark>; match_video_id / match_source_url /
    match_date / match_place name the meeting.
*/

{%- set common_share = 0.02 -%}

with

curated_topic as (
    select topic_id, keyword_stats
    from {{ ref('civicsearch_topic') }}
    where source = 'curated'
),

topic_rx as (
    select t.topic_id, '(' || string_agg(distinct lower(k.elem), '|') || ')' as rx
    from curated_topic as t
    cross join lateral jsonb_array_elements_text(t.keyword_stats) as k(elem)
    where k.elem ~ '^[A-Za-z0-9 -]+$'
    group by t.topic_id
),

topic_doc as (
    select distinct on (k.topic_id, k.video_id)
        k.topic_id,
        k.video_id,
        k.state_code,
        lower(nullif(trim(k.city), ''))                                  as city,
        k.event_date,
        coalesce(k.video_url, 'https://www.youtube.com/watch?v=' || k.video_id) as video_url,
        coalesce(nullif(trim(k.jurisdiction_name), ''), nullif(trim(k.city), '')) as place_name
    from {{ ref('topic_transcript_link') }} as k
    where k.state_code is not null
    order by k.topic_id, k.video_id, k.event_date desc nulls last
),

passage as (
    select
        d.topic_id, d.video_id, d.state_code, d.city, d.event_date, d.video_url, d.place_name, r.rx,
        w.ord                                                            as passage_no,
        w.m[1]                                                           as passage_text
    from topic_doc as d
    inner join topic_rx as r on r.topic_id = d.topic_id
    inner join {{ ref('event_documents') }} as e on e.video_id = d.video_id
    cross join lateral regexp_matches(lower(e.content), '(.{0,400}\m' || r.rx || '\M.{0,400})', 'g')
        with ordinality as w(m, ord)
),

passage_lex as (
    select distinct p.topic_id, p.video_id, p.passage_no, p.state_code, x.lexeme
    from passage as p
    cross join lateral unnest(to_tsvector('english', p.passage_text)) as x
),

lex_df as (
    select lexeme, count(*) as n from passage_lex group by lexeme
),

n_passages as (
    select count(*)::numeric as n from passage
),

nonprofit as (
    select
        o.master_org_id,
        o.state_code,
        o.city_norm,
        o.org_name,
        trim(regexp_replace(
            regexp_replace(lower(o.org_name), '\m(inc|incorporated|corp|corporation|co|ltd|llc|the)\M', ' ', 'g'),
            '[^a-z0-9]+', ' ', 'g'))                                     as clean
    from {{ ref('mdm_organization') }} as o
    inner join {{ ref('mdm_organization_nonprofit') }} as n on n.master_org_id = o.master_org_id
    where o.state_code is not null and o.org_name is not null
),

unique_name as (
    select *, array(select l.lexeme from unnest(to_tsvector('english', clean)) as l) as lex
    from (
        select *, count(*) over (partition by state_code, clean) as n_same
        from nonprofit
    ) as x
    where n_same = 1 and length(clean) >= 12
),

-- Each candidate's rarest word across topic passages: the key passages are looked up by.
candidate as (
    select u.master_org_id, u.state_code, u.city_norm, u.org_name, u.clean, rare.lexeme as rare_lexeme
    from unique_name as u
    cross join lateral (
        select l.lexeme, coalesce(df.n, 0) as n
        from unnest(u.lex) as l(lexeme)
        left join lex_df as df on df.lexeme = l.lexeme
        order by coalesce(df.n, 0), l.lexeme
        limit 1
    ) as rare
    cross join n_passages as np
    where cardinality(u.lex) >= 2
      and rare.n between 1 and greatest(1, np.n * {{ common_share }})
),

rule_linked as (
    select distinct topic_id, master_org_id from {{ ref('int_topic_organization__rule_match') }}
),

pairs as (
    select c.master_org_id, c.org_name, c.clean, pl.topic_id, pl.video_id, pl.passage_no
    from candidate as c
    inner join passage_lex as pl
        on pl.lexeme = c.rare_lexeme
       and pl.state_code = c.state_code
),

matched as (
    select
        pr.topic_id, pr.master_org_id, pr.org_name, p.video_id, p.event_date, p.video_url, p.place_name, p.rx, p.passage_text,
        '\m' || regexp_replace(pr.clean, ' +', '\W+', 'g') || '\M'      as name_rx
    from pairs as pr
    inner join passage as p
        on p.topic_id = pr.topic_id and p.video_id = pr.video_id and p.passage_no = pr.passage_no
    inner join candidate as c on c.master_org_id = pr.master_org_id
    where (c.city_norm = p.city
           or exists (select 1 from rule_linked as r where r.topic_id = pr.topic_id and r.master_org_id = pr.master_org_id))
      and to_tsvector('english', p.passage_text) @@ phraseto_tsquery('english', pr.clean)
),

verified as (
    select * from matched where passage_text ~ name_rx
)

select distinct on (v.topic_id, v.master_org_id)
    v.topic_id::integer                                                    as topic_id,
    v.master_org_id::text                                                  as master_org_id,
    -- The name in <mark>, and the topic's words too unless the name holds them (no nested marks).
    (case when v.passage_text ~ ('(' || v.name_rx || ')') and lower(v.org_name) ~ ('\m' || v.rx || '\M')
          then regexp_replace(trim(v.passage_text), '(' || v.name_rx || ')', '<mark>\1</mark>', 'g')
          else regexp_replace(
                   regexp_replace(trim(v.passage_text), '(\m' || v.rx || '\M)', '<mark>\1</mark>', 'g'),
                   '(' || replace(v.name_rx, '\W+', '(?:\W+|</?mark>)+') || ')', '<mark>\1</mark>', 'g')
     end)::text                                                            as match_text,
    v.video_id::text                                                       as match_video_id,
    v.video_url::text                                                      as match_source_url,
    v.event_date::date                                                     as match_date,
    v.place_name::text                                                     as match_place
from verified as v
order by v.topic_id, v.master_org_id, v.event_date desc nulls last, v.video_id
