{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Every decision a local meeting took on a data center item, contested or not (#933).
    Grain: one row per decision: an event_decision (contested, debated) or an
    event_uncontested_item (taken up without debate: consent agenda, routine approval).

    A decision is about a data center when its headline (or, for a contested decision, its
    decision_statement) says a data center word (data_center_regex), the same test as
    data_center_meeting_position and int_data_center__public_comment. Moratoria and ordinances
    often pass on the consent agenda, so leaving out uncontested items hid the most decisive
    actions (#932 found 11 of them).

    VOTES: a contested decision's tally is used only when both yes and no parse as whole numbers
    (the rule data_center_meeting_position applies); otherwise votes_for / votes_against are null.
    An uncontested item's vote is text as said ("voice vote", "5-0") in vote_text, never parsed
    into numbers. Nothing is filled in when the record doesn't say.
    SAME ACTION, TWO LISTS: the analysis sometimes lists one action both as a debated decision and as
    an uncontested item (Wayne County: D001 "Data Center Ordinance Approved" 5-0 and U007 "Approve
    Data Center Ordinance" 5-0). An uncontested row is dropped when a debated data center decision
    in the same meeting reads like it: pg_trgm word_similarity of either headline against the other's
    headline + outcome >= 0.4. Measured on the 3 debated/uncontested pairs that shared a meeting
    (25 Nov 2026): the 2 that were one action scored 0.44-1.00, the 1 that was two actions scored
    0.18-0.30. A small sample: re-check the threshold as the table grows.
    PREFERRED: both parts read only the recording's preferred analysis (int_preferred_event_analysis);
    event_decision is append-only and still holds superseded analyses.
    KEYS: PK data_center_decision_id = the source row's own id (event_decision_id or
    event_uncontested_item_id; both are md5 of analysis id and item id, so they can't collide
    with each other's item ids D001 / U001). FK event_meeting_id -> event_meeting.
    Design: web_docs/docs/development/data-center-who-spoke-up.md
*/

{%- set dc_regex = data_center_regex() %}
{%- set whole_number = "'^[0-9]+(\\.0+)?$'" %}

with preferred as (
    select analysis_id from {{ ref('int_preferred_event_analysis') }}
),

meetings as (
    select event_meeting_id, video_id, meeting_date, event_date, jurisdiction_name, state_code, state
    from (
        select
            *,
            row_number() over (partition by event_meeting_id order by extracted_at desc) as _rn
        from {{ ref('event_meeting') }}
    ) as m
    where _rn = 1
),

contested as (
    select
        d.event_decision_id                                         as data_center_decision_id,
        d.analysis_id                                               as event_meeting_id,
        true                                                        as contested,
        d.decision_id                                               as item_id,
        d.headline,
        d.outcome,
        case when (d.vote_tally ->> 'yes') ~ {{ whole_number }} and (d.vote_tally ->> 'no') ~ {{ whole_number }}
             then (d.vote_tally ->> 'yes')::numeric::integer end    as votes_for,
        case when (d.vote_tally ->> 'yes') ~ {{ whole_number }} and (d.vote_tally ->> 'no') ~ {{ whole_number }}
             then (d.vote_tally ->> 'no')::numeric::integer end     as votes_against,
        null::text                                                  as vote_text
    from (
        select distinct on (event_decision_id)
            event_decision_id, analysis_id, decision_id, headline, decision_statement, outcome, vote_tally
        from {{ ref('event_decision') }}
        order by event_decision_id, extracted_at desc
    ) as d
    inner join preferred as pa on pa.analysis_id = d.analysis_id
    where coalesce(d.headline, '') || ' ' || coalesce(d.decision_statement, '') ~* '{{ dc_regex }}'
),

uncontested as (
    select
        u.event_uncontested_item_id                                 as data_center_decision_id,
        u.event_meeting_id,
        false                                                       as contested,
        u.item_id,
        u.headline,
        u.outcome,
        null::integer                                               as votes_for,
        null::integer                                               as votes_against,
        u.vote                                                      as vote_text
    from {{ ref('event_uncontested_item') }} as u
    where coalesce(u.headline, '') ~* '{{ dc_regex }}'
      and not exists (
          select 1
          from contested as c
          where c.event_meeting_id = u.event_meeting_id
            and greatest(
                word_similarity(coalesce(u.headline, ''), coalesce(c.headline, '') || ' ' || coalesce(c.outcome, '')),
                word_similarity(coalesce(c.headline, ''), coalesce(u.headline, '') || ' ' || coalesce(u.outcome, ''))
            ) >= 0.4
      )
),

decisions as (
    select * from contested
    union all
    select * from uncontested
)

select
    d.data_center_decision_id::text                             as data_center_decision_id,
    d.event_meeting_id::integer                                 as event_meeting_id,
    d.contested::boolean                                        as contested,
    d.item_id::text                                             as item_id,
    d.headline::text                                            as headline,
    d.outcome::text                                             as outcome,
    d.votes_for::integer                                        as votes_for,
    d.votes_against::integer                                    as votes_against,
    d.vote_text::text                                           as vote_text,
    -- a date later than the load date is a wrong source date (#472): unknown is better than wrong
    (case when x.meeting_day > current_date then null else x.meeting_day end)::date as meeting_date,
    m.jurisdiction_name::text                                   as jurisdiction_name,
    m.state_code::text                                          as state_code,
    m.state::text                                               as state,
    m.video_id::text                                            as video_id,
    case when m.video_id is not null
         then 'https://www.youtube.com/watch?v=' || m.video_id end::text as video_url,
    -- only contested decisions have a detail page (/decisions/:id reads event_decision)
    case when d.contested then '/decisions/' || d.data_center_decision_id end::text as decision_url
from decisions as d
inner join meetings as m on m.event_meeting_id = d.event_meeting_id
cross join lateral (
    select coalesce(
        case when m.meeting_date ~ '^\d{4}-\d{2}-\d{2}$' then m.meeting_date::date end,
        case when m.event_date ~ '^\d{4}-\d{2}-\d{2}$' then m.event_date::date end
    ) as meeting_day
) as x
