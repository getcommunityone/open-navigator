{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'topics', 'serving'],
        contract={'enforced': true},
        indexes=[
            {'columns': ['meeting_year', 'topic_id'], 'type': 'btree'},
            {'columns': ['state_code', 'meeting_year'], 'type': 'btree'}
        ]
    )
}}

/*
    Meetings per topic, government and calendar year (#1361): the numerator for
    Browse all topics (`GET /api/topics/yoy`), covering every topic in
    `civicsearch_topic` (both curated stories and CivicSearch major topics).

    GRAIN: one row per (topic_id, state_code, jurisdiction_name, meeting_year).
    - `data-centers` reads `data_center_meeting_mention` (distinct video_id),
      matching the Data Center Story's timeline and map.
    - Every other topic reads `int_transcript_keyword_topic` joined to the
      canonical transcript in `event_documents` (longest transcript with
      `content_tsv`), so curated topics match `topic_transcript_link` and
      CivicSearch topics count their `>= 2` multi-word phrase hits without
      requiring a curated-only `topic_transcript_link` build.

    Undated and future-dated meetings (`> current_date`) are left out (#472).
    `state_code` and `jurisdiction_name` are trimmed and null-normalized before
    grouping so NULL and '' never collide in the MD5 primary key.
*/

with dc_topic as (
    select topic_id
    from {{ ref('civicsearch_topic') }}
    where query_id = 'data-centers'
    limit 1
),

dc_meetings as (
    select distinct on (m.video_id)
        dc.topic_id::integer                   as topic_id,
        m.video_id,
        nullif(trim(m.state_code), '')         as state_code,
        nullif(trim(m.state), '')              as state,
        nullif(trim(m.jurisdiction_name), '')  as jurisdiction_name,
        m.meeting_date                         as event_date
    from {{ ref('data_center_meeting_mention') }} m
    cross join dc_topic dc
    where m.meeting_date is not null
      and m.meeting_date <= current_date
    order by m.video_id, m.meeting_date desc
),

doc as (
    select distinct on (d.video_id)
        d.video_id,
        d.event_date,
        nullif(trim(d.state_code), '') as state_code,
        nullif(trim(d.state), '')      as state
    from {{ ref('event_documents') }} d
    where d.document_type = 'transcript'
      and d.video_id is not null
      and d.content_tsv is not null
      and d.event_date is not null
      and d.event_date <= current_date
    order by d.video_id, d.content_length desc nulls last
),

other_meetings as (
    select
        c.topic_id::integer                   as topic_id,
        k.video_id,
        nullif(trim(k.state_code), '')        as state_code,
        case when d.state_code = nullif(trim(k.state_code), '') then d.state end as state,
        nullif(trim(k.jurisdiction_name), '') as jurisdiction_name,
        d.event_date
    from {{ ref('int_transcript_keyword_topic') }} k
    join doc d
        on d.video_id = k.video_id
    join {{ ref('civicsearch_topic') }} c
        on c.topic_id = k.topic_id::integer
    where c.topic_id is distinct from (select topic_id from dc_topic)
),

all_meetings as (
    select * from dc_meetings
    union all
    select * from other_meetings
)

select
    md5(
        topic_id::text || '|' || coalesce(state_code, '') || '|'
        || coalesce(jurisdiction_name, '') || '|' || extract(year from event_date)::int::text
    )::text                                         as topic_meeting_year_id,
    topic_id::integer                               as topic_id,
    state_code::text                                as state_code,
    max(state)::text                                as state,
    jurisdiction_name::text                         as jurisdiction_name,
    extract(year from event_date)::integer          as meeting_year,
    count(distinct video_id)::integer               as meetings,
    max(event_date)::date                           as latest_meeting_date
from all_meetings
group by topic_id, state_code, jurisdiction_name, extract(year from event_date)
