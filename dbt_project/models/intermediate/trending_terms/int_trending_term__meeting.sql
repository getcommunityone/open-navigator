{{ config(
    post_hook=["analyze {{ this }}"],
    materialized='table',
    tags=['intermediate', 'trending_terms'],
    indexes=[{'columns': ['video_id'], 'unique': true}, {'columns': ['counted', 'meeting_year']}]
) }}

/*
    One row per recorded meeting dated in the comparison years (#1399): the meeting base of trending terms.

    "Recorded meeting" is recorded_meeting_year's definition, row for row (a distinct meeting video in
    event_youtube_with_jurisdiction with a usable transcript, dated, not in the future), so summing this model per year
    gives recorded_meeting_year's totals (tests/test_trending_terms.py checks it).

    counted = the meeting enters the trending-term counts and their denominator:
      * meeting_year is year_a (last full year) or year_b (this year to date);
      * not a school-board meeting (jurisdiction_type school_district): residents there are often students or speak
        about students, and AGENTS.md (Privacy, minors) keeps their speech out of anything we tag or quote. It also
        keeps the mix shift (6,950 school meetings in 2025, 559 in 2026) from reading as falling school words;
      * the transcript has a full-text vector in event_documents (the text we can read: ~99% of meetings).
    has_turns = the meeting also has public-comment speaker turns (meeting_speaker_turn, #1387). Candidate terms come
    from those turns; presence is read from the transcript for every meeting (see the decision page for why).
*/

{%- set ya = var('trending_year_a', 2025) %}
{%- set yb = var('trending_year_b', 2026) %}

with transcripts as (
    select distinct video_id
    from {{ ref('stg_bronze_event_youtube_transcript') }}
),

meetings as (
    select distinct on (e.video_id)
        e.video_id,
        case when e.event_date > current_date then null else e.event_date end as meeting_date,
        nullif(trim(e.state_code), '')                                        as state_code,
        nullif(trim(e.state), '')                                             as state,
        nullif(trim(e.jurisdiction_id), '')                                   as jurisdiction_id,
        nullif(trim(e.jurisdiction_name), '')                                 as jurisdiction_name,
        nullif(trim(e.jurisdiction_type), '')                                 as jurisdiction_type
    from {{ ref('event_youtube_with_jurisdiction') }} as e
    inner join transcripts as t on t.video_id = e.video_id
    where nullif(trim(e.video_id), '') is not null
    order by e.video_id, e.event_date desc nulls last
),

docs as (
    select distinct d.video_id
    from {{ ref('event_documents') }} as d
    where d.document_type = 'transcript' and d.video_id is not null and d.content_tsv is not null
),

turns as (
    select distinct video_id from {{ ref('meeting_speaker_turn') }}
)

select
    m.video_id::text                                                    as video_id,
    m.meeting_date::date                                                as meeting_date,
    extract(year from m.meeting_date)::integer                          as meeting_year,
    m.state_code::text                                                  as state_code,
    m.state::text                                                       as state,
    m.jurisdiction_id::text                                             as jurisdiction_id,
    m.jurisdiction_name::text                                           as jurisdiction_name,
    coalesce(m.jurisdiction_id, lower(m.jurisdiction_name), m.video_id)::text as jurisdiction_key,
    m.jurisdiction_type::text                                           as jurisdiction_type,
    (coalesce(m.jurisdiction_type, '') = 'school_district')::boolean    as is_school_board,
    (d.video_id is not null)::boolean                                   as has_transcript_text,
    (t.video_id is not null)::boolean                                   as has_turns,
    (coalesce(m.jurisdiction_type, '') <> 'school_district' and d.video_id is not null)::boolean as counted
from meetings as m
left join docs as d on d.video_id = m.video_id
left join turns as t on t.video_id = m.video_id
where m.meeting_date is not null
  and extract(year from m.meeting_date)::int in ({{ ya }}, {{ yb }})
