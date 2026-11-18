{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Possible recordings of company-hosted data center meetings (#532): videos a YouTube
    search (through the VPN guard) found for an event with a date and a place. Grain: one
    row per (community_event_id, video_url). review_status is always 'candidate': a
    candidate is shown for review, never as the event's recording.
*/

select
    r.recording_candidate_id,
    r.community_event_id,
    r.video_url,
    r.title,
    r.channel,
    r.published_on,
    r.query,
    r.match_reason,
    'candidate'::text as review_status,
    r.searched_at
from {{ ref('int_data_center_community_event__recording') }} as r
inner join {{ ref('data_center_community_event') }} as e on e.community_event_id = r.community_event_id
