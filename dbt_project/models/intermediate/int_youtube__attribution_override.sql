{{
  config(
    materialized='table',
    tags=['intermediate', 'youtube', 'events', 'jurisdictions'],
    indexes=[
      {'columns': ['video_id'], 'unique': True},
      {'columns': ['channel_id'], 'type': 'btree'}
    ]
  )
}}

/*
Intermediate: hand-reviewed jurisdiction attribution for YouTube videos on channels
that discovery filed under the wrong government (#514, #515).

Expands the youtube_channel_attribution_override seed over every
bronze.bronze_event_youtube video on a listed channel. A per-video seed row wins
over the channel-wide row (video_id empty). An empty jurisdiction_id means "not
attributable to any government" and is emitted as a NULL jurisdiction with the
seed's state, so the video is served without a guessed place.

Read by event_youtube_with_jurisdiction (this attribution wins over the resolved
model and over bronze) and by the repair_youtube_channel_attribution run-operation,
which writes it back to bronze, the channel catalogs, civic_event and the
append-only event_* marts.

Grain: one row per video_id on an overridden channel.
*/

with

overrides as (
    select
        nullif(trim(channel_id), '')       as channel_id,
        nullif(trim(video_id), '')         as video_id,
        nullif(trim(jurisdiction_id), '')  as jurisdiction_id,
        upper(nullif(trim(state_code), '')) as state_code,
        nullif(trim(issue), '')            as issue,
        evidence
    from {{ ref('youtube_channel_attribution_override') }}
),

channel_default as (
    select * from overrides where video_id is null
),

video_override as (
    select * from overrides where video_id is not null
),

videos as (
    select
        b.video_id,
        nullif(trim(b.channel_id), '') as channel_id
    from {{ source('bronze', 'bronze_event_youtube') }} b
    where nullif(trim(b.channel_id), '') in (select channel_id from overrides)
       or b.video_id in (select video_id from video_override)
),

picked as (
    select
        v.video_id,
        coalesce(vo.channel_id, v.channel_id)           as channel_id,
        case when vo.video_id is not null then vo.jurisdiction_id
             else cd.jurisdiction_id end                as jurisdiction_id,
        coalesce(vo.state_code, cd.state_code)          as seed_state_code,
        case when vo.video_id is not null then 'video' else 'channel' end
                                                        as override_level,
        coalesce(vo.issue, cd.issue)                    as issue,
        coalesce(vo.evidence, cd.evidence)              as evidence
    from videos v
    left join video_override vo on vo.video_id = v.video_id
    left join channel_default cd on cd.channel_id = v.channel_id
    where vo.video_id is not null or cd.channel_id is not null
),

juris as (
    select jurisdiction_id, name, jurisdiction_type, state_code, state
    from {{ ref('int_jurisdictions') }}
    where jurisdiction_id is not null
),

-- Full state name for unattributed rows (jurisdiction_id NULL): the state row of
-- int_jurisdictions carries both state_code and state.
states as (
    select distinct on (state_code) state_code, state
    from {{ ref('int_jurisdictions') }}
    where state_code is not null and state is not null
    order by state_code, state
)

select
    p.video_id,
    p.channel_id,
    p.jurisdiction_id,
    j.name                                       as jurisdiction_name,
    j.jurisdiction_type,
    coalesce(j.state_code, p.seed_state_code)    as state_code,
    coalesce(j.state, s.state)                   as state,
    -- city is the municipality's own name; NULL for counties and unattributed rows.
    case when j.jurisdiction_type = 'municipality' then j.name end as city,
    p.override_level,
    p.issue,
    p.evidence
from picked p
left join juris j on j.jurisdiction_id = p.jurisdiction_id
left join states s on s.state_code = p.seed_state_code
