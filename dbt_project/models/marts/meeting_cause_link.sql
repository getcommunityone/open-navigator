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
counterpart to meeting_topic_link. Each row is a meeting whose transcript
full-text-matched a cause's curated keyword set (see int_meeting_cause).

GRAIN: one row per (event_meeting_id, cause_id).
PK   : meeting_cause_link_id = md5(event_meeting_id|cause_id).
FK   : event_meeting_id -> event_meeting (enforced).

Causes used to have NO meeting linkage in the warehouse (meeting_topic_link's
header even noted this). This mart supplies it, so the Browse Causes pills can
show a real per-cause meeting count instead of an empty state.
*/

with meeting as (
    select
        event_meeting_id,
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

cause_links as (
    select
        l.event_meeting_id,
        l.cause_id,
        l.cause_name,
        l.icon,
        l.popularity_rank
    from {{ ref('int_meeting_cause') }} l
)

select
    md5(a.event_meeting_id::text || '|' || a.cause_id) as meeting_cause_link_id,
    a.event_meeting_id,
    a.cause_id,
    a.cause_name        as cause_label,
    a.icon              as cause_icon,
    a.popularity_rank,
    m.state_code,
    m.state,
    m.city,
    m.jurisdiction_name,
    m.meeting_date,
    m.video_id,
    (mt.event_meeting_id is not null) as has_transcript
from cause_links a
join meeting m
    on m.event_meeting_id = a.event_meeting_id
left join meeting_transcript mt
    on mt.event_meeting_id = a.event_meeting_id
