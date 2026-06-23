{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'meeting-browse'],
        contract={'enforced': true}
    )
}}

/*
public.meeting_browse — one row per meeting; the serving rollup the meeting-level
browse cards read.

GRAIN: one row per event_meeting_id.
PK   : event_meeting_id.
FK   : event_meeting_id -> event_meeting (enforced).

INCLUSION: a meeting appears here if it has SOMETHING to show — a transcript OR at
least one decision / topic / question link. Bare meetings with no transcript and
no links are excluded (nothing to browse). No counts are fabricated: an honest
meeting with a transcript and 0 decisions keeps decision_count = 0.

title: event_meeting has no dedicated title column; body_name (the meeting body,
e.g. "City Council Regular Meeting") is the best human label, with meeting_summary
as a soft fallback only when body_name is null. Both are real source values.
*/

with publishable_analysis as (
    select id as analysis_id
    from {{ source('bronze', 'bronze_events_analysis_ai') }}
    where {{ is_publishable_governance_analysis('structured_analysis') }}
),

meeting as (
    select
        m.event_meeting_id,
        m.c1_event_id,
        m.video_id,
        m.body_name,
        m.meeting_summary,
        {{ coerce_plausible_meeting_date('m.meeting_date', 'm.meeting_id') }} as meeting_date,
        m.state_code,
        m.state,
        m.city,
        m.jurisdiction_name
    from {{ ref('event_meeting') }} m
    inner join publishable_analysis pa on pa.analysis_id = m.event_meeting_id
),

transcript as (
    select distinct m.event_meeting_id
    from meeting m
    join {{ ref('event_documents') }} d
        on d.video_id = m.video_id
       and d.document_type = 'transcript'
    where m.video_id is not null
),

-- DRILLABLE decisions only. The meeting->decisions drill (/api/decisions?meeting_id=)
-- serves ONLY public.item_interestingness (the scored subset). Count exactly those
-- rows, keyed on the same meeting_id the drill uses, so the card never promises a
-- decision the drill can't return. Unscored decisions are intentionally excluded:
-- a meeting with only unscored decisions correctly becomes non-expandable.
decision_counts as (
    select
        meeting_id as event_meeting_id,
        count(*) as decision_count
    from {{ ref('item_interestingness') }}
    where meeting_id is not null
    group by meeting_id
),

question_counts as (
    select
        event_meeting_id,
        count(distinct question_id) as question_count
    from {{ ref('meeting_question_link') }}
    group by event_meeting_id
),

topic_counts as (
    select
        event_meeting_id,
        count(*) as topic_link_count
    from {{ ref('meeting_topic_link') }}
    group by event_meeting_id
),

interest as (
    select
        meeting_id as event_meeting_id,
        max(interestingness_score) as top_interestingness_score
    from {{ ref('item_interestingness') }}
    where meeting_id is not null
    group by meeting_id
)

select
    m.event_meeting_id,
    m.c1_event_id,
    m.video_id,
    coalesce(m.body_name, m.meeting_summary)        as meeting_title,
    m.meeting_date,
    m.state_code,
    m.state,
    m.city,
    m.jurisdiction_name,
    (t.event_meeting_id is not null)                as has_transcript,
    coalesce(dc.decision_count, 0)                  as decision_count,
    coalesce(qc.question_count, 0)                  as question_count,
    coalesce(tc.topic_link_count, 0)                as topic_link_count,
    i.top_interestingness_score
from meeting m
left join transcript     t  on t.event_meeting_id  = m.event_meeting_id
left join decision_counts dc on dc.event_meeting_id = m.event_meeting_id
left join question_counts qc on qc.event_meeting_id = m.event_meeting_id
left join topic_counts    tc on tc.event_meeting_id = m.event_meeting_id
left join interest        i  on i.event_meeting_id  = m.event_meeting_id
-- INCLUSION: keep only meetings with something to show.
where t.event_meeting_id is not null            -- has a transcript
   or dc.event_meeting_id is not null           -- has >=1 drillable (scored) decision
   or tc.event_meeting_id is not null           -- has >=1 topic link
   or qc.event_meeting_id is not null           -- has >=1 question link
