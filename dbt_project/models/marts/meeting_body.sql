{{ config(
    materialized='table',
    on_schema_change='fail',
    contract={'enforced': true},
    tags=['marts', 'bodies', 'api'],
    indexes=[
      {'columns': ['meeting_body_id'], 'unique': True},
      {'columns': ['governing_body_id', 'meeting_date'], 'type': 'btree'},
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['video_id'], 'type': 'btree'}
    ]
) }}

/*
    meeting_body (#1442): which body held each meeting. Grain: one row per meeting we matched to a body
    (int_meeting_body__matched). PK meeting_body_id = md5(source | source_key).
    FKs: governing_body_id -> governing_body, jurisdiction_id -> jurisdictions, platform_meeting_id ->
    platform_meeting (platform rows), event_meeting_id -> event_meeting (when the meeting has an AI extraction).
    video_id is the YouTube id (no FK: the YouTube table is a view keyed by an integer id).
*/

select
    md5(m.source || '|' || m.source_key)::text                 as meeting_body_id,
    md5(m.jurisdiction_id || '|' || m.body_key)::text          as governing_body_id,
    m.jurisdiction_id::text                                     as jurisdiction_id,
    m.source::text                                              as source,
    m.video_id::text                                            as video_id,
    m.platform_meeting_id::text                                 as platform_meeting_id,
    em.event_meeting_id::integer                                as event_meeting_id,
    m.meeting_title::text                                       as meeting_title,
    m.meeting_date::date                                        as meeting_date,
    m.video_url::text                                           as video_url,
    m.matched_on::text                                          as matched_on,
    m.pattern_id::text                                          as pattern_id
from {{ ref('int_meeting_body__matched') }} as m
-- Keep the FK honest: only event_meeting ids that exist.
left join {{ ref('event_meeting') }} as em on em.event_meeting_id = m.event_meeting_id
-- governing_body is built from the same rows; the join documents the dependency for the DAG and the FK.
join {{ ref('governing_body') }} as g on g.governing_body_id = md5(m.jurisdiction_id || '|' || m.body_key)
