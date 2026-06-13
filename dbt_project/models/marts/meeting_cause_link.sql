{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'meeting-browse', 'cause'],
        contract={'enforced': true}
    )
}}

/*
public.meeting_cause_link — meeting <-> EveryOrg cause linkages, the cause
counterpart to meeting_topic_link.

LINKAGE MODEL (decision-primary + transcript-fallback):
  * DECISION leg (link_source='decision', PRIMARY): a meeting's DECISIONS
    (event_decision, joined via c1_event_id) keyword-matched a cause's curated
    keyword set (int_decision_cause). A meeting has many decisions hitting the
    same cause, so this leg is DISTINCT per (event_meeting_id, cause_id).
  * TRANSCRIPT leg (link_source='transcript', FALLBACK): ONLY for meetings whose
    c1_event_id produced ZERO decision-derived cause rows. For those meetings we
    fall back to the existing transcript full-text matches (int_meeting_cause).

A meeting is therefore in EXACTLY ONE leg (decision OR transcript, never both),
which keeps the md5(event_meeting_id|cause_id) PK unique across the union.

GRAIN: one row per (event_meeting_id, cause_id).
PK   : meeting_cause_link_id = md5(event_meeting_id|cause_id).
FK   : event_meeting_id -> event_meeting (enforced).

link_source is honest: 'decision' rows trace to a keyword hit on a real decision;
'transcript' rows to a keyword hit on the meeting transcript. Neither is an AI
theme (CLAUDE.md No Fabricated Data).
*/

with meeting as (
    select
        event_meeting_id,
        c1_event_id,
        state_code,
        state,
        city,
        jurisdiction_name,
        meeting_date,
        video_id
    from {{ ref('event_meeting') }}
),

-- has_transcript flag per meeting (reused for passthrough; mirrors topic mart).
meeting_transcript as (
    select distinct m.event_meeting_id
    from meeting m
    join {{ ref('event_documents') }} d
        on d.video_id = m.video_id
       and d.document_type = 'transcript'
    where m.video_id is not null
),

-- DECISION leg: decision-derived cause rows rolled up to the meeting via
-- c1_event_id. DISTINCT collapses the many decisions per (meeting, cause).
decision_cause as (
    select distinct
        m.event_meeting_id,
        dc.cause_id,
        dc.cause_name,
        dc.icon,
        dc.popularity_rank
    from meeting m
    join {{ ref('int_decision_cause') }} dc
        on dc.c1_event_id = m.c1_event_id
    where m.c1_event_id is not null
),

-- Meetings that already have at least one decision-derived cause row; these are
-- excluded from the transcript fallback so each meeting lands in exactly one leg.
meetings_with_decision_cause as (
    select distinct event_meeting_id from decision_cause
),

-- TRANSCRIPT fallback leg: existing transcript keyword matches, but ONLY for
-- meetings with zero decision-derived cause rows.
transcript_cause as (
    select
        l.event_meeting_id,
        l.cause_id,
        l.cause_name,
        l.icon,
        l.popularity_rank
    from {{ ref('int_meeting_cause') }} l
    where l.event_meeting_id not in (
        select event_meeting_id from meetings_with_decision_cause
    )
),

all_links as (
    select event_meeting_id, cause_id, cause_name, icon, popularity_rank,
           'decision'::text as link_source
    from decision_cause
    union all
    select event_meeting_id, cause_id, cause_name, icon, popularity_rank,
           'transcript'::text as link_source
    from transcript_cause
)

select
    md5(a.event_meeting_id::text || '|' || a.cause_id) as meeting_cause_link_id,
    a.event_meeting_id,
    a.cause_id,
    a.cause_name        as cause_label,
    a.icon              as cause_icon,
    a.popularity_rank,
    a.link_source,
    m.state_code,
    m.state,
    m.city,
    m.jurisdiction_name,
    m.meeting_date,
    m.video_id,
    (mt.event_meeting_id is not null) as has_transcript
from all_links a
join meeting m
    on m.event_meeting_id = a.event_meeting_id
left join meeting_transcript mt
    on mt.event_meeting_id = a.event_meeting_id
