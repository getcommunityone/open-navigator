{{ config(materialized='table', tags=['meeting_comments', 'serving'],
          indexes=[{'columns': ['topic_id', 'scope_level', 'state_code']}]) }}

/*
    Public-speaker heat per topic, place scope and calendar year (#1418): the rows behind "heat doubled in 2026" in the
    chart-title picker (web_app/src/utils/chartInsight.ts). Source: meeting_speaker_topic_side (#1391), the classifier's
    1-5 heat reading of each public speaker's own words on a topic, served only at heat_confidence >= the floor; a
    speaker the classifier did not rate (heat null) is not counted. One speaker in one meeting is one rating.

    GRAIN: one row per topic_id x scope_level x scope_key x year.
      scope_level 'national' (scope_key 'US'), 'state' (scope_key = state_code), 'city' (scope_key = jurisdiction_id).
    Minimum count: a row exists only with >= var('heat_year_min_speakers') rated speakers, so a thin year is omitted,
    never shown as zero. year is an integer calendar year (the API serializes it as a string). Future-dated and
    undated meetings are left out. No names, no text.
*/

{%- set min_speakers = var('heat_year_min_speakers') | int %}

with rated as (
    select
        s.topic_id,
        s.heat,
        extract(year from s.meeting_date)::int as year,
        s.video_id,
        s.jurisdiction_id,
        s.jurisdiction_name,
        s.state_code,
        p.state
    from {{ ref('meeting_speaker_topic_side') }} as s
    inner join {{ ref('meeting_speaker_position') }} as p on p.meeting_speaker_id = s.meeting_speaker_id
    where s.heat is not null
      and s.meeting_date is not null
      and s.meeting_date <= current_date
),

scoped as (
    select r.topic_id, r.heat, r.year, r.video_id, sc.*
    from rated as r
    cross join lateral (values
        ('national', 'US'::text,      null::text,    null::text, null::text,         null::text),
        ('state',    r.state_code,    r.state_code,  r.state,    null,               null),
        ('city',     r.jurisdiction_id, r.state_code, r.state,   r.jurisdiction_name, r.jurisdiction_id)
    ) as sc(scope_level, scope_key, state_code, state, city, jurisdiction_id)
    where sc.scope_key is not null
)

select
    topic_id::int                                                      as topic_id,
    scope_level::text                                                  as scope_level,
    scope_key::text                                                    as scope_key,
    max(state_code)::text                                              as state_code,
    max(state)::text                                                   as state,
    max(city)::text                                                    as city,
    max(jurisdiction_id)::text                                         as jurisdiction_id,
    year::int                                                          as year,
    round(avg(heat), 2)::numeric(3, 2)                                 as mean_heat,
    round((count(*) filter (where heat >= 4))::numeric / count(*), 3)::numeric(4, 3) as share_heated,
    count(*)::int                                                      as speakers_rated,
    (count(*) filter (where heat >= 4))::int                           as speakers_heated,
    count(distinct video_id)::int                                      as meetings
from scoped
group by topic_id, scope_level, scope_key, year
having count(*) >= {{ min_speakers }}
