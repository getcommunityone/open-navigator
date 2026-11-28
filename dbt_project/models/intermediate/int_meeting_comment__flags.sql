{{ config(materialized='table', tags=['intermediate', 'meeting_comments'],
          indexes=[{'columns': ['video_id']}]) }}

/*
    Free (no LLM) per-comment flags for every segmented comment (#1233, epic #1232).
    Grain: one row per comment (stg_meeting_comment_segment). Topic-agnostic: the
    meeting is segmented once and every topic reads these rows.

    All rules are keyword lists in seeds, matched with Postgres regex on lower(text):
      topic_ids       curated_topics keywords found in the comment's own words
                      (word-bounded, same phrases the transcript topic links use);
      concern_keys    comment_concern_terms (per topic; data-centers has the reference list);
      company_keys,
      person_keys     comment_entity_terms (entity_type company / person);
      mentions_ai     comment_entity_terms entity_type ai;
      role_keys       comment_role_terms matched on the INTRODUCTION (intro_text, the first
                      40 words from the self-introduction), i.e. how speakers describe
                      themselves, never inferred from the rest of what they said;
      is_public_comment  false when the introduction says staff, applicant or consultant, or when a piece split
                      off at a ">>" / hand-off (no introduction) lies outside an opened public-comment section;
      possible_minor  the introduction says a child's age / grade / school year: the
                      display name is dropped downstream (AGENTS.md, minors).
    comment_text stays in this intermediate table (private); marts carry no text.
*/

with comments as (
    select * from {{ ref('stg_meeting_comment_segment') }}
),

lowered as (
    select
        comment_segment_id,
        lower(comment_text)                 as t,
        lower(coalesce(intro_text, ''))     as intro
    from comments
),

topics as (
    select
        topic_id,
        query_id,
        '\y(' || string_agg(
            regexp_replace(lower(btrim(kw)), '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g'), '|'
        ) || ')\y' as pattern
    from {{ ref('curated_topics') }}
    cross join lateral unnest(string_to_array(keywords, '|')) as kw
    where btrim(kw) <> ''
    group by topic_id, query_id
),

topic_hits as (
    select l.comment_segment_id,
           array_agg(tp.topic_id order by tp.topic_id)  as topic_ids,
           array_agg(tp.query_id order by tp.topic_id)  as topic_query_ids
    from lowered as l
    inner join topics as tp on l.t ~ tp.pattern
    group by l.comment_segment_id
),

concern_hits as (
    select l.comment_segment_id,
           array_agg(distinct c.concern_key order by c.concern_key) as concern_keys
    from lowered as l
    inner join {{ ref('comment_concern_terms') }} as c on l.t ~ c.pattern
    group by l.comment_segment_id
),

entity_hits as (
    select l.comment_segment_id,
           array_agg(distinct e.entity_key order by e.entity_key) filter (where e.entity_type = 'company') as company_keys,
           array_agg(distinct e.entity_key order by e.entity_key) filter (where e.entity_type = 'person')  as person_keys,
           bool_or(e.entity_type = 'ai')                                                                 as mentions_ai
    from lowered as l
    inner join {{ ref('comment_entity_terms') }} as e on l.t ~ e.pattern
    group by l.comment_segment_id
),

role_hits as (
    select l.comment_segment_id,
           array_agg(distinct r.role_key order by r.role_key) filter (where r.role_key <> 'possible_minor') as role_keys,
           bool_or(not r.is_public_comment)                                                               as is_staff_or_applicant,
           bool_or(r.role_key = 'possible_minor')                                                         as possible_minor
    from lowered as l
    inner join {{ ref('comment_role_terms') }} as r on l.intro ~ r.pattern
    group by l.comment_segment_id
)

select
    c.comment_segment_id,
    c.video_id,
    c.comment_index,
    c.block_index,
    c.start_seconds,
    c.end_seconds,
    c.word_count,
    c.comment_text,
    c.intro_text,
    c.intro_name,
    c.boundary_basis,
    c.in_public_comment_section,
    c.segmenter_version,
    coalesce(th.topic_ids, '{}'::int[])            as topic_ids,
    coalesce(th.topic_query_ids, '{}'::text[])     as topic_query_ids,
    coalesce(ch.concern_keys, '{}'::text[])        as concern_keys,
    coalesce(eh.company_keys, '{}'::text[])        as company_keys,
    coalesce(eh.person_keys, '{}'::text[])         as person_keys,
    coalesce(eh.mentions_ai, false)                as mentions_ai,
    coalesce(rh.role_keys, '{}'::text[])           as role_keys,
    -- A piece the segmenter split off at a ">>" or a chair hand-off with no introduction (#1383) is a new voice, but
    -- only inside an opened public-comment section is it a public commenter; elsewhere it is council or staff talk.
    (not coalesce(rh.is_staff_or_applicant, false)
     and not (c.boundary_basis ~ '^(turn_marker|handoff)>' and not c.in_public_comment_section)) as is_public_comment,
    coalesce(rh.possible_minor, false)             as possible_minor
from comments as c
left join topic_hits   as th on th.comment_segment_id = c.comment_segment_id
left join concern_hits as ch on ch.comment_segment_id = c.comment_segment_id
left join entity_hits  as eh on eh.comment_segment_id = c.comment_segment_id
left join role_hits    as rh on rh.comment_segment_id = c.comment_segment_id
