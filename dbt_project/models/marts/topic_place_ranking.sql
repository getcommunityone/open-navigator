{{ config(materialized='table', tags=['meeting_comments', 'serving'],
          indexes=[{'columns': ['topic_id', 'size_band']}, {'columns': ['state_code']}]) }}

/*
    Where places stand on a topic (#1437): one row per place x topic x window, from the public speakers' own sides
    (meeting_speaker_topic_side, the classifier readings of #1391). Decision record:
    web_docs/docs/development/topic-place-rankings.md.

    Counting: each public speaker counts ONCE per place and topic, on their majority side across the window's
    meetings; a speaker evenly split between for and against takes no side (speakers_split). Only served 'for' /
    'against' readings count: concerns only, no side and not sure (under the confidence floor) are left out. A speaker
    is recognised across meetings only inside one place, by the name the site already shows ("First L."); an unnamed
    speaker ("Speaker N") cannot be recognised and counts once per meeting. The person key never leaves this model.

    Evidence minimum: ranked only with >= var('ranking_min_speakers') sided speakers across >= var('ranking_min_meetings')
    meetings in the window.

    Score: against_share = against / (for + against). shrunk_against_share adds var('ranking_prior_weight')
    pseudo-speakers at the topic's national against-rate (all places' sided speakers in the window), so a place with
    little evidence sits near the national rate. band_rank: 1 = the most against among ranked places in the same Census
    population band (large >= 250k, mid 50k-250k, small < 50k, unknown = no ACS population).

    Officials are kept apart: an official counts only when roster-confirmed (attribution_method =
    'official_roster_match'), is never added to the residents' counts, and gives officials_side on its own.
    No names are carried. School-district places are left out (their residents are never read, AGENTS.md).
*/

{%- set as_of = var('ranking_as_of') %}
{%- set months = var('ranking_window_months') | int %}
{%- set as_of_sql = ("date '" ~ as_of ~ "'") if as_of else 'current_date' %}

with readings as (
    select
        s.topic_id,
        s.jurisdiction_id,
        s.video_id,
        s.meeting_date,
        s.side,
        (p.attribution_method = 'official_roster_match')                    as is_confirmed_official,
        case when p.speaker_named then 'name:' || lower(p.speaker_label)
             else 'speaker:' || s.meeting_speaker_id end                    as person_key
    from {{ ref('meeting_speaker_topic_side') }} as s
    inner join {{ ref('meeting_speaker_position') }} as p on p.meeting_speaker_id = s.meeting_speaker_id
    where s.side in ('for', 'against')
      and s.jurisdiction_id is not null
      and not p.possible_minor
      and s.meeting_date > ({{ as_of_sql }} - interval '{{ months }} months')::date
      and s.meeting_date <= {{ as_of_sql }}
),

places as (
    select j.jurisdiction_id, j.name, j.state_code, j.state_name, j.population
    from {{ ref('jurisdictions') }} as j
    where j.jurisdiction_type is distinct from 'school_district'
),

-- one row per person x place x topic: their majority side across the window's meetings
people as (
    select
        r.topic_id, r.jurisdiction_id, r.person_key, r.is_confirmed_official,
        count(*) filter (where r.side = 'for')     as n_for,
        count(*) filter (where r.side = 'against') as n_against
    from readings as r
    inner join places as pl on pl.jurisdiction_id = r.jurisdiction_id
    group by 1, 2, 3, 4
),

sided as (
    select *, case when n_for > n_against then 'for' when n_against > n_for then 'against' else 'split' end as side
    from people
),

residents as (
    select
        topic_id, jurisdiction_id,
        count(*) filter (where side = 'for')     as speakers_for,
        count(*) filter (where side = 'against') as speakers_against,
        count(*) filter (where side = 'split')   as speakers_split
    from sided
    where not is_confirmed_official
    group by 1, 2
),

officials as (
    select
        topic_id, jurisdiction_id,
        count(*) filter (where side = 'for')     as officials_for,
        count(*) filter (where side = 'against') as officials_against
    from sided
    where is_confirmed_official
    group by 1, 2
),

meetings as (
    select r.topic_id, r.jurisdiction_id, count(distinct r.video_id) as meetings,
           min(r.meeting_date) as first_meeting_date, max(r.meeting_date) as last_meeting_date
    from readings as r
    where not r.is_confirmed_official
    group by 1, 2
),

national as (
    select topic_id,
           sum(speakers_against)::numeric / nullif(sum(speakers_for + speakers_against), 0) as national_against_share
    from residents
    group by 1
),

scored as (
    select
        rs.topic_id, rs.jurisdiction_id,
        pl.name as jurisdiction_name, pl.state_code, pl.state_name as state, pl.population,
        case when pl.population is null then 'unknown'
             when pl.population >= 250000 then 'large'
             when pl.population >= 50000 then 'mid'
             else 'small' end                                                    as size_band,
        rs.speakers_for, rs.speakers_against, rs.speakers_split,
        coalesce(m.meetings, 0) as meetings, m.first_meeting_date, m.last_meeting_date,
        rs.speakers_against::numeric / nullif(rs.speakers_for + rs.speakers_against, 0) as against_share,
        n.national_against_share,
        (rs.speakers_against + {{ var('ranking_prior_weight') }} * n.national_against_share)
            / (rs.speakers_for + rs.speakers_against + {{ var('ranking_prior_weight') }})   as shrunk_against_share,
        (rs.speakers_for + rs.speakers_against >= {{ var('ranking_min_speakers') }}
            and coalesce(m.meetings, 0) >= {{ var('ranking_min_meetings') }})               as is_ranked,
        coalesce(o.officials_for, 0) as officials_for, coalesce(o.officials_against, 0) as officials_against
    from residents as rs
    inner join places as pl on pl.jurisdiction_id = rs.jurisdiction_id
    inner join national as n on n.topic_id = rs.topic_id
    left join meetings as m on m.topic_id = rs.topic_id and m.jurisdiction_id = rs.jurisdiction_id
    left join officials as o on o.topic_id = rs.topic_id and o.jurisdiction_id = rs.jurisdiction_id
    where rs.speakers_for + rs.speakers_against > 0
)

select
    s.jurisdiction_id::text                                         as jurisdiction_id,
    s.topic_id::int                                                 as topic_id,
    {{ months }}::int                                               as window_months,
    s.jurisdiction_name::text                                       as jurisdiction_name,
    s.state_code::text                                              as state_code,
    s.state::text                                                   as state,
    s.population::bigint                                            as population,
    s.size_band::text                                               as size_band,
    s.speakers_for::int                                             as speakers_for,
    s.speakers_against::int                                         as speakers_against,
    s.speakers_split::int                                           as speakers_split,
    s.meetings::int                                                 as meetings,
    s.first_meeting_date::date                                      as first_meeting_date,
    s.last_meeting_date::date                                       as last_meeting_date,
    round(s.against_share, 4)::numeric(5, 4)                        as against_share,
    round(s.national_against_share, 4)::numeric(5, 4)               as national_against_share,
    round(s.shrunk_against_share, 4)::numeric(5, 4)                 as shrunk_against_share,
    {{ var('ranking_prior_weight') }}::int                          as prior_weight,
    s.is_ranked::boolean                                            as is_ranked,
    (case when s.is_ranked then rank() over (
        partition by s.topic_id, s.size_band, s.is_ranked
        order by s.shrunk_against_share desc, (s.speakers_for + s.speakers_against) desc) end)::int as band_rank,
    (case when s.is_ranked then count(*) over (partition by s.topic_id, s.size_band, s.is_ranked) end)::int
                                                                    as band_ranked_count,
    s.officials_for::int                                            as officials_for,
    s.officials_against::int                                        as officials_against,
    (case when s.officials_for + s.officials_against = 0 then null
          when s.officials_for > s.officials_against then 'for'
          when s.officials_against > s.officials_for then 'against'
          else 'split' end)::text                                   as officials_side,
    {{ as_of_sql }}::date                                           as window_end_date,
    now()::timestamp                                                as built_at
from scored as s
