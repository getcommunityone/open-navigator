{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'civic', 'meeting-browse', 'topic'],
        contract={'enforced': true}
    )
}}

/*
public.meeting_topic_link — meeting <-> topic linkages for the meeting-level
browse feature. TWO link types in one mart, distinguished by link_type:

  * 'civicsearch_topic' (PRIMARY): decision-primary + transcript-fallback.
      - DECISION leg (link_source='decision'): the meeting's DECISIONS
        (int_decision_topic, joined via c1_event_id) keyword-matched a CivicSearch
        topic's multi-word phrase set. DISTINCT per (meeting, topic).
      - TRANSCRIPT leg (link_source='transcript'): ONLY for meetings whose
        c1_event_id produced ZERO decision-derived topic rows — falls back to the
        existing transcript full-text matches (int_meeting_topic_civicsearch).
    A meeting is in EXACTLY ONE of these legs for the civicsearch_topic link_type,
    keeping the PK unique across the union.
  * 'canonical_theme' (FALLBACK): the meeting's AI primary_theme normalized to one
    of the ~18 canonical COFOG themes via normalize_coarse_theme(), joined via
    c1_event_id. These rows are AI-theme-derived (NOT keyword), so they are
    stamped link_source='decision' to record that they came from the meeting's
    decision/event analysis (the c1_event_id roll-up), keeping link_source's two
    values ('decision'|'transcript') logically consistent: 'transcript' is
    reserved for transcript-keyword fallback rows only. '__unthemed__' is dropped.

GRAIN: one row per (event_meeting_id, link_type, link_id).
PK   : meeting_topic_link_id = md5(event_meeting_id|link_type|link_id).
FK   : event_meeting_id -> event_meeting (enforced).

link_source is honest: 'transcript' only ever marks transcript-keyword fallback
rows; everything decision/event-derived is 'decision'.
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

-- has_transcript flag per meeting (reused for passthrough).
meeting_transcript as (
    select distinct m.event_meeting_id
    from meeting m
    join {{ ref('event_documents') }} d
        on d.video_id = m.video_id
       and d.document_type = 'transcript'
    where m.video_id is not null
),

-- link_type = 'civicsearch_topic' — DECISION leg (PRIMARY).
decision_topic as (
    select distinct
        m.event_meeting_id,
        'civicsearch_topic'::text as link_type,
        dt.topic_id::text         as link_id,
        dt.topic_name             as link_label,
        'decision'::text          as link_source
    from meeting m
    join {{ ref('int_decision_topic') }} dt
        on dt.c1_event_id = m.c1_event_id
    where m.c1_event_id is not null
),

-- Meetings that already have at least one decision-derived civicsearch topic;
-- excluded from the transcript fallback so each meeting lands in one leg.
meetings_with_decision_topic as (
    select distinct event_meeting_id from decision_topic
),

-- link_type = 'civicsearch_topic' — TRANSCRIPT fallback leg, ONLY for meetings
-- with zero decision-derived topic rows.
transcript_topic as (
    select
        l.event_meeting_id,
        'civicsearch_topic'::text as link_type,
        l.topic_id::text          as link_id,
        l.topic_name              as link_label,
        'transcript'::text        as link_source
    from {{ ref('int_meeting_topic_civicsearch') }} l
    where l.event_meeting_id not in (
        select event_meeting_id from meetings_with_decision_topic
    )
),

-- link_type = 'canonical_theme' (FALLBACK, AI primary_theme via c1_event_id).
theme_norm as (
    select distinct
        m.event_meeting_id,
        {{ normalize_coarse_theme('t.primary_theme') }} as canonical_theme
    from meeting m
    join {{ ref('event_topic') }} t
        on t.c1_event_id = m.c1_event_id
    where t.primary_theme is not null
      and trim(t.primary_theme) <> ''
),

theme_links as (
    select
        event_meeting_id,
        'canonical_theme'::text as link_type,
        -- slug: lowercase label, non-alphanumeric -> single underscore
        trim(both '_' from regexp_replace(lower(canonical_theme), '[^a-z0-9]+', '_', 'g')) as link_id,
        canonical_theme as link_label,
        'decision'::text as link_source
    from theme_norm
    where canonical_theme <> '__unthemed__'
),

all_links as (
    select * from decision_topic
    union all
    select * from transcript_topic
    union all
    select * from theme_links
)

select
    md5(a.event_meeting_id::text || '|' || a.link_type || '|' || a.link_id) as meeting_topic_link_id,
    a.event_meeting_id,
    a.link_type,
    a.link_id,
    a.link_label,
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
