{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'serving', 'transcripts', 'timeline'],
        contract={'enforced': true},
        post_hook=[
            "create index if not exists recorded_meeting_year_state_idx on {{ this }} (state_code, meeting_year)",
            "create index if not exists recorded_meeting_year_jurisdiction_name_idx on {{ this }} (jurisdiction_name)"
        ]
    )
}}

/*
    Recorded meetings per government per year (#1140): the denominator for a topic's share of the record.

    GRAIN: one row per (state_code, jurisdiction_id, jurisdiction_name, meeting_year).
    A "recorded meeting" is a distinct meeting video in event_youtube_with_jurisdiction (junk channels already gated
    out) that has a usable transcript in stg_bronze_event_youtube_transcript (not excluded / tombstoned, with text or
    timed cues). Every topic count on the story timeline (data_center_meeting_mention, topic_transcript_link) is drawn
    from transcripts of this same catalog, so meetings / recorded_meetings is a real share.

    Meetings with no date, or a date in the future (a wrong source date, #472), are left out: they can't be placed on a
    year. meeting_year is an integer (CLAUDE.md, calendar years); the API serializes it as a string.
    No LLM, rebuilt on every dbt run. Slow to compute live (~3 min over ~180k transcripts), hence a table.
*/

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
        nullif(trim(e.jurisdiction_name), '')                                 as jurisdiction_name
    from {{ ref('event_youtube_with_jurisdiction') }} as e
    inner join transcripts as t on t.video_id = e.video_id
    where nullif(trim(e.video_id), '') is not null
    order by e.video_id, e.event_date desc nulls last
)

select
    md5(
        coalesce(state_code, '') || '|' || coalesce(jurisdiction_id, '') || '|'
        || coalesce(jurisdiction_name, '') || '|' || extract(year from meeting_date)::int::text
    )::text                                         as recorded_meeting_year_id,
    state_code::text                                as state_code,
    max(state)::text                                as state,
    jurisdiction_id::text                           as jurisdiction_id,
    jurisdiction_name::text                         as jurisdiction_name,
    extract(year from meeting_date)::integer        as meeting_year,
    count(*)::integer                               as recorded_meetings
from meetings
where meeting_date is not null
group by state_code, jurisdiction_id, jurisdiction_name, extract(year from meeting_date)
