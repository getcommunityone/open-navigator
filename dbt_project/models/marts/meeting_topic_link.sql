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

  * 'civicsearch_topic' (PRIMARY): meeting transcript full-text-matched a
    CivicSearch topic's keyword set (see int_meeting_topic_civicsearch).
    link_id = topic_id as text; link_label = topic name.
  * 'canonical_theme' (FALLBACK): the meeting's AI primary_theme normalized to
    one of the ~18 canonical COFOG themes via normalize_coarse_theme(). Joined to
    the meeting via c1_event_id. link_id = theme slug; link_label = canonical
    theme label. '__unthemed__' is dropped (no useful browse facet).

GRAIN: one row per (event_meeting_id, link_type, link_id).
PK   : meeting_topic_link_id = md5(event_meeting_id|link_type|link_id).
FK   : event_meeting_id -> event_meeting (enforced).

NOTE: causes are intentionally NOT modeled — no meeting<->cause linkage exists in
the warehouse. The frontend shows an empty state for causes.
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

-- link_type = 'civicsearch_topic' (PRIMARY, full-text)
civicsearch_links as (
    select
        l.event_meeting_id,
        'civicsearch_topic'::text as link_type,
        l.topic_id::text          as link_id,
        l.topic_name              as link_label
    from {{ ref('int_meeting_topic_civicsearch') }} l
),

-- link_type = 'canonical_theme' (FALLBACK, AI primary_theme)
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
        canonical_theme as link_label
    from theme_norm
    where canonical_theme <> '__unthemed__'
),

all_links as (
    select * from civicsearch_links
    union all
    select * from theme_links
)

select
    md5(a.event_meeting_id::text || '|' || a.link_type || '|' || a.link_id) as meeting_topic_link_id,
    a.event_meeting_id,
    a.link_type,
    a.link_id,
    a.link_label,
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
