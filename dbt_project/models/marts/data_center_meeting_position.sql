{{ config(materialized='table', tags=['marts', 'data_centers', 'serving', 'sentiment']) }}

/*
    Who spoke for and against, and how the vote went, per meeting where a data center came
    up (#930). Grain: one row per event_meeting (the preferred analysis of one recording).

    A meeting has a row when any of these holds:
      * its recording has a passage in data_center_meeting_mention (the meeting's own words
        say a data center word);
      * it has a decision whose headline or decision_statement says a data center word
        (data_center_regex);
      * it has a public comment that int_data_center__public_comment counts.
    Only analysed meetings can have a row (event_meeting_id is the analysis), so this is a
    subset of the recordings in data_center_meeting_mention.

    SPEAKERS: public speakers on a data center item only (the rule and its known misses are
    in int_data_center__public_comment), each speaker once per meeting, by stance_bucket.
    A speaker whose stance is unknown (null) is in none of the four counts. 0 means the
    meeting was analysed and no such speaker was found.

    VOTES: event_decision.vote_tally is JSONB {"yes": n, "no": n}; either value may be a
    number, a numeric string or null. A decision has a recorded tally only when BOTH parse
    as whole numbers. decisions_with_tally counts those among the meeting's data center
    decisions; votes_for / votes_against sum them and are NULL (not 0) when there is none.
    Votes on uncontested (consent) items are not in event_decision and are not counted.
    Design: web_docs/docs/development/data-center-who-spoke-up.md
*/

{%- set dc_regex = data_center_regex() %}
{%- set whole_number = "'^[0-9]+(\\.0+)?$'" %}

with meetings as (
    select event_meeting_id, video_id, meeting_date, event_date, jurisdiction_name, state_code, state
    from (
        select
            *,
            row_number() over (partition by event_meeting_id order by extracted_at desc) as _rn
        from {{ ref('event_meeting') }}
    ) as m
    where _rn = 1
),

mention_videos as (
    select video_id, max(meeting_date) as meeting_date
    from {{ ref('data_center_meeting_mention') }}
    group by video_id
),

dc_decisions as (
    select
        d.analysis_id as event_meeting_id,
        d.event_decision_id,
        case when (d.vote_tally ->> 'yes') ~ {{ whole_number }} and (d.vote_tally ->> 'no') ~ {{ whole_number }}
             then (d.vote_tally ->> 'yes')::numeric::integer end as votes_yes,
        case when (d.vote_tally ->> 'yes') ~ {{ whole_number }} and (d.vote_tally ->> 'no') ~ {{ whole_number }}
             then (d.vote_tally ->> 'no')::numeric::integer end  as votes_no
    from (
        select distinct on (event_decision_id)
            event_decision_id, analysis_id, headline, decision_statement, vote_tally
        from {{ ref('event_decision') }}
        order by event_decision_id, extracted_at desc
    ) as d
    where coalesce(d.headline, '') || ' ' || coalesce(d.decision_statement, '') ~* '{{ dc_regex }}'
),

votes as (
    select
        event_meeting_id,
        count(*) filter (where votes_yes is not null)::integer as decisions_with_tally,
        sum(votes_yes)::integer                                as votes_for,
        sum(votes_no)::integer                                 as votes_against
    from dc_decisions
    group by event_meeting_id
),

speakers as (
    select
        event_meeting_id,
        count(*) filter (where stance_bucket = 'for')::integer      as speakers_for,
        count(*) filter (where stance_bucket = 'against')::integer  as speakers_against,
        count(*) filter (where stance_bucket = 'question')::integer as speakers_question,
        count(*) filter (where stance_bucket = 'neutral')::integer  as speakers_neutral
    from {{ ref('int_data_center__public_comment') }}
    where is_counted
    group by event_meeting_id
),

commented as (
    select distinct event_meeting_id from {{ ref('int_data_center__public_comment') }}
),

dated as (
    select
        m.*,
        coalesce(
            mv.meeting_date,
            case when m.meeting_date ~ '^\d{4}-\d{2}-\d{2}$' then m.meeting_date::date end,
            case when m.event_date ~ '^\d{4}-\d{2}-\d{2}$' then m.event_date::date end
        ) as meeting_day,
        (mv.video_id is not null) as has_mention
    from meetings as m
    left join mention_videos as mv on mv.video_id = m.video_id
)

select
    md5('data_center_meeting_position|' || m.event_meeting_id::text)::text as data_center_meeting_position_id,
    m.event_meeting_id::integer                                 as event_meeting_id,
    m.video_id::text                                            as video_id,
    -- a date later than the load date is a wrong source date (#472): unknown is better than wrong
    (case when m.meeting_day > current_date then null else m.meeting_day end)::date as meeting_date,
    m.jurisdiction_name::text                                   as jurisdiction_name,
    m.state_code::text                                          as state_code,
    m.state::text                                               as state,
    coalesce(s.speakers_for, 0)::integer                        as speakers_for,
    coalesce(s.speakers_against, 0)::integer                    as speakers_against,
    coalesce(s.speakers_question, 0)::integer                   as speakers_question,
    coalesce(s.speakers_neutral, 0)::integer                    as speakers_neutral,
    coalesce(v.decisions_with_tally, 0)::integer                as decisions_with_tally,
    (case when coalesce(v.decisions_with_tally, 0) > 0 then v.votes_for end)::integer     as votes_for,
    (case when coalesce(v.decisions_with_tally, 0) > 0 then v.votes_against end)::integer as votes_against
from dated as m
left join speakers as s on s.event_meeting_id = m.event_meeting_id
left join votes as v on v.event_meeting_id = m.event_meeting_id
left join commented as c on c.event_meeting_id = m.event_meeting_id
where m.has_mention
   or v.event_meeting_id is not null
   or c.event_meeting_id is not null
