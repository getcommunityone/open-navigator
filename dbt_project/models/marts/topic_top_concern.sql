{{ config(materialized='table', tags=['meeting_comments', 'serving'],
          indexes=[{'columns': ['topic_id', 'scope_level', 'state_code']}]) }}

/*
    The most-cited concern among opposing or heated speaker turns, per topic and place scope (#1418): the rows behind
    "<concern> leads the complaints" in the chart-title picker (web_app/src/utils/chartInsight.ts).

    Concerns come from the existing free keyword classification (comment_concern_terms, per topic, matched on each
    comment's own words in int_meeting_comment__flags, the same list the Concerns screen uses); only topics that have a
    concern list appear. A turn is one speaker's uninterrupted stretch (meeting_speaker_turn); it counts when its words
    name the topic and its speaker, on that topic (meeting_speaker_topic_side, #1391), is
      basis 'opposing': side = 'against' (served at the side-confidence floor), or
      basis 'heated':   heat >= 4.
    turns_read = distinct such turns in scope; turns_with_concern = those that raise the top concern (a turn can raise
    several concerns; shares can sum past 1). The top concern is the one in the most turns (ties: concern_key order).
    GRAIN: one row per topic_id x basis x scope_level x scope_key. Minimum count: only with >= var('top_concern_min_turns')
    turns read; below it no row. No text, no names.
*/

{%- set min_turns = var('top_concern_min_turns') | int %}

with concern_terms as (
    select distinct topic_query_id as query_id, concern_key, concern_label
    from {{ ref('comment_concern_terms') }}
),

topics as (
    select distinct t.topic_id, ct.query_id
    from {{ ref('civicsearch_topic') }} as t
    inner join concern_terms as ct on ct.query_id = t.query_id
),

turns as (
    select
        c.meeting_speaker_turn_id,
        c.meeting_speaker_id,
        tp.topic_id,
        tp.query_id,
        min(c.jurisdiction_id)   as jurisdiction_id,
        min(c.jurisdiction_name) as jurisdiction_name,
        min(c.state_code)        as state_code,
        min(c.state)             as state,
        array_agg(distinct k) filter (where k is not null) as keys
    from {{ ref('meeting_comment') }} as c
    cross join lateral unnest(c.topic_ids) as tt(topic_id)
    inner join topics as tp on tp.topic_id = tt.topic_id
    left join lateral unnest(c.concern_keys) as k on true
    where c.is_public_comment
      and not c.possible_minor
      and c.meeting_speaker_turn_id is not null
      and c.meeting_speaker_id is not null
    group by c.meeting_speaker_turn_id, c.meeting_speaker_id, tp.topic_id, tp.query_id
),

read_turns as (
    select t.*, b.basis
    from turns as t
    inner join {{ ref('meeting_speaker_topic_side') }} as s
        on s.meeting_speaker_id = t.meeting_speaker_id and s.topic_id = t.topic_id
    cross join lateral (values
        ('opposing', s.side = 'against'),
        ('heated',   coalesce(s.heat, 0) >= 4)
    ) as b(basis, ok)
    where b.ok
),

scoped as (
    select r.topic_id, r.query_id, r.basis, r.meeting_speaker_turn_id, r.keys, sc.*
    from read_turns as r
    cross join lateral (values
        ('national', 'US'::text,         null::text,   null::text, null::text,         null::text),
        ('state',    r.state_code,        r.state_code, r.state,    null,               null),
        ('city',     r.jurisdiction_id,   r.state_code, r.state,    r.jurisdiction_name, r.jurisdiction_id)
    ) as sc(scope_level, scope_key, state_code, state, city, jurisdiction_id)
    where sc.scope_key is not null
),

totals as (
    select topic_id, basis, scope_level, scope_key,
           max(state_code) as state_code, max(state) as state, max(city) as city,
           max(jurisdiction_id) as jurisdiction_id,
           count(distinct meeting_speaker_turn_id) as turns_read
    from scoped
    group by topic_id, basis, scope_level, scope_key
    having count(distinct meeting_speaker_turn_id) >= {{ min_turns }}
),

by_concern as (
    select s.topic_id, s.basis, s.scope_level, s.scope_key, ct.concern_key, ct.concern_label,
           count(distinct s.meeting_speaker_turn_id) as turns_with_concern
    from scoped as s
    cross join lateral unnest(s.keys) as k
    inner join concern_terms as ct on ct.query_id = s.query_id and ct.concern_key = k
    group by s.topic_id, s.basis, s.scope_level, s.scope_key, ct.concern_key, ct.concern_label
),

ranked as (
    select *, row_number() over (
        partition by topic_id, basis, scope_level, scope_key
        order by turns_with_concern desc, concern_key
    ) as rn
    from by_concern
)

select
    t.topic_id::int                                         as topic_id,
    t.basis::text                                           as basis,
    t.scope_level::text                                     as scope_level,
    t.scope_key::text                                       as scope_key,
    t.state_code::text                                      as state_code,
    t.state::text                                           as state,
    t.city::text                                            as city,
    t.jurisdiction_id::text                                 as jurisdiction_id,
    r.concern_key::text                                     as concern_key,
    r.concern_label::text                                   as concern_label,
    r.turns_with_concern::int                               as turns_with_concern,
    t.turns_read::int                                       as turns_read,
    round(r.turns_with_concern::numeric / t.turns_read, 3)::numeric(4, 3) as share
from totals as t
inner join ranked as r
    on r.topic_id = t.topic_id and r.basis = t.basis and r.scope_level = t.scope_level
   and r.scope_key = t.scope_key and r.rn = 1
