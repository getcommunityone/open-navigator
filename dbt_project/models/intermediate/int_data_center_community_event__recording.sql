{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    Recording candidates found for company-hosted data center meetings (#532), from
    bronze_data_center_event_recording_candidate
    (python -m ingestion.data_centers.recording_candidates). Grain: one row per
    (community_event_id, video_url). Candidates for review only: none is attached to an
    event. Empty until the search has run (it needs the VPN guard to pass).
*/

{%- set src = source('bronze', 'bronze_data_center_event_recording_candidate') -%}
{%- set src_exists = execute and adapter.get_relation(
        database=src.database, schema=src.schema, identifier=src.identifier) is not none %}

{%- if src_exists %}
select distinct on (community_event_id, video_url)
    md5(community_event_id || '|' || video_url)::text  as recording_candidate_id,
    community_event_id::text                           as community_event_id,
    video_url::text                                    as video_url,
    title::text                                        as title,
    channel::text                                      as channel,
    published_on::date                                 as published_on,
    query::text                                        as query,
    match_reason::text                                 as match_reason,
    searched_at::timestamptz                           as searched_at
from {{ src }}
order by community_event_id, video_url, searched_at desc
{%- else %}
select
    null::text as recording_candidate_id, null::text as community_event_id, null::text as video_url,
    null::text as title, null::text as channel, null::date as published_on, null::text as query,
    null::text as match_reason, null::timestamptz as searched_at
where false
{%- endif %}
