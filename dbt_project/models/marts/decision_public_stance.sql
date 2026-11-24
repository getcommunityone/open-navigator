{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'decision', 'ai', 'sentiment'],
        contract={'enforced': true}
    )
}}

/*
public.decision_public_stance — per-decision count of public speakers by stance, and how heated they were.

GRAIN  : one row per event_decision_id that has at least one public_comment row
         with a known stance. Decisions with no public-comment data have NO row
         (the UI shows "no public-comment data", never a neutral bar).
COUNTS : each speaker counts once per decision. A speaker with several rows on one
         decision takes their latest row.
HEAT   : heat_mean / heat_max over the speakers with a heat value; null when none has one.
BALANCE: (for - against) / (for + against), -1..+1, among speakers who took a side;
         null when nobody did. Speakers who asked questions or were neutral are reported, not folded in.
Design : web_docs/docs/development/meeting-sentiment-design.md
*/

with per_speaker as (
    select
        event_decision_id,
        speaker_id,
        stance_bucket,
        heat,
        row_number() over (
            partition by event_decision_id, speaker_id
            order by extracted_at desc, public_comment_id
        ) as _rn
    from {{ ref('public_comment') }}
    where event_decision_id is not null
      and stance_bucket is not null
),

counted as (
    select
        event_decision_id,
        count(*) filter (where stance_bucket = 'for')::integer     as speakers_for,
        count(*) filter (where stance_bucket = 'against')::integer as speakers_against,
        count(*) filter (where stance_bucket = 'question')::integer as speakers_question,
        count(*) filter (where stance_bucket = 'neutral')::integer as speakers_neutral,
        count(*)::integer                                          as speakers_total,
        round(avg(heat), 2)                                        as heat_mean,
        max(heat)::integer                                         as heat_max
    from per_speaker
    where _rn = 1
    group by event_decision_id
)

select
    event_decision_id::text as event_decision_id,
    speakers_for,
    speakers_against,
    speakers_question,
    speakers_neutral,
    speakers_total,
    case
        when speakers_for + speakers_against > 0
        then round((speakers_for - speakers_against)::numeric / (speakers_for + speakers_against), 4)
    end::numeric as stance_balance,
    heat_mean::numeric as heat_mean,
    heat_max
from counted
