{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'decision', 'ai', 'sentiment'],
        contract={'enforced': true}
    )
}}

/*
public.public_comment — one row per (meeting, public speaker, item) with the
speaker's stance toward the action being decided.

GRAIN  : one row per bronze public_participation key
         (source_event_id, speaker_id, decision_id-or-none), latest extraction.
SOURCE : bronze.bronze_public_participation_from_ai, emitted by BOTH analysis tiers
         (full: policy_analysis_part_1.md, light: policy_analysis_lite.md).
STANCE : `stance` is the extraction's own value; `stance_bucket` maps it to
         for / against / question / neutral with public_stance_bucket(). A missing or unrecognised
         stance stays null — unknown is never counted as neutral (CLAUDE.md No Fabricated Data).
HEAT   : 1-5, how heated the comment was by the prompt's rubric; null when unknown.
ROLE   : the capacity the speaker gave (Resident, Advocacy group, Expert, ...), as extracted.
LINKS  : event_meeting_id always; event_decision_id only when decision_id names a
         contested decision that exists in event_decision (uncontested items and
         general public comment have none).
KEYS   : single-column PK (public_comment_id). FK event_meeting_id -> event_meeting is
         an enforced constraint. event_decision is partitioned with a composite PK, so
         that FK is a relationships test, following the event_* family convention.
Design : web_docs/docs/development/meeting-sentiment-design.md
*/

with latest as (
    {{ latest_per_natural_key(ref('bronze_public_participation_from_ai'), 'source_event_id_speaker_id', 'extracted_at') }}
),

meetings as (
    select
        event_meeting_id,
        state_code,
        state,
        jurisdiction_name,
        video_id
    from (
        select
            *,
            row_number() over (partition by event_meeting_id order by extracted_at desc) as _rn
        from {{ ref('event_meeting') }}
    ) m
    where _rn = 1
),

decisions as (
    select distinct event_decision_id from {{ ref('event_decision') }}
)

select
    md5(l.source_event_id_speaker_id)::text            as public_comment_id,
    m.event_meeting_id::integer                        as event_meeting_id,
    d.event_decision_id::text                          as event_decision_id,
    l.decision_id::text                                as item_id,
    l.speaker_id::text                                 as speaker_id,
    l.stance::text                                     as stance,
    ({{ public_stance_bucket('l.stance') }})::text     as stance_bucket,
    nullif(btrim(l.stance_evidence), '')::text         as stance_evidence,
    l.heat::integer                                    as heat,
    l.speaker_role::text                               as speaker_role,
    l.summary::text                                    as summary,
    l.timestamp_start_seconds::numeric                 as timestamp_start_seconds,
    l.timestamp_end_seconds::numeric                   as timestamp_end_seconds,
    m.state_code::varchar(2)                           as state_code,
    m.state::text                                      as state,
    m.jurisdiction_name::varchar(200)                  as jurisdiction_name,
    m.video_id::varchar(64)                            as video_id,
    l.source_ai_model::text                            as source_ai_model,
    l.extracted_at::timestamp                          as extracted_at
from latest l
join meetings m on m.event_meeting_id = l.source_event_id
left join decisions d
    on d.event_decision_id = md5(l.source_event_id || '_' || l.decision_id)
