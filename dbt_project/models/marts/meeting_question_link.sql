{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'meeting-browse', 'question'],
        contract={'enforced': true}
    )
}}

/*
public.meeting_question_link — meeting <-> policy-question linkages for the
meeting-level browse feature.

PATH: event_meeting -> event_decision (c1_event_id) -> question_instance
      (source_type='local_decision', source_id = event_decision_id) -> question_id
      -> policy_question (label).

GRAIN: one row per (event_meeting_id, question_id).
PK   : meeting_question_link_id = md5(event_meeting_id|question_id).
FK   : event_meeting_id -> event_meeting (enforced);
       question_id      -> policy_question (enforced).
*/

with meeting as (
    select
        event_meeting_id,
        c1_event_id,
        state_code,
        state,
        city,
        jurisdiction_name,
        meeting_date
    from {{ ref('event_meeting') }}
),

linked as (
    select distinct
        m.event_meeting_id,
        qi.question_id
    from meeting m
    join {{ ref('event_decision') }} ed
        on ed.c1_event_id = m.c1_event_id
    join {{ ref('question_instance') }} qi
        on qi.source_type = 'local_decision'
       and qi.source_id = ed.event_decision_id
    join {{ ref('policy_question') }} pq
        on pq.question_id = qi.question_id
)

select
    md5(l.event_meeting_id::text || '|' || l.question_id) as meeting_question_link_id,
    l.event_meeting_id,
    l.question_id,
    pq.canonical_text as question_label,
    m.state_code,
    m.state,
    m.city,
    m.jurisdiction_name,
    m.meeting_date
from linked l
join meeting m
    on m.event_meeting_id = l.event_meeting_id
join {{ ref('policy_question') }} pq
    on pq.question_id = l.question_id
