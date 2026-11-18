{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Company-hosted data center community meetings (#532): town halls, open houses,
    information sessions, community and public meetings that a data center company holds
    about its project. Grain: one row per event, deduplicated across the articles and
    announcements that report it (data_center_community_event_source).

    Hosted by a company (host_type 'company'), never labelled a government meeting.
    Built only from what the items' own text says (int_data_center_news_item__match):

      status 'confirmed'    the items name the host company and a tracked project. Articles
                            about one event share (host, project, kind, event date); an
                            article that gives no date joins a dated event of the same host,
                            project and kind reported within 30 days, else it groups by the
                            month it was published.
      status 'unconfirmed'  an item says "data center" and a meeting word but the host or
                            the project couldn't be matched. One row per item, kept for
                            review; the API does not show it as an event.

    event_date is set only when an article states it (event_date_basis). recording_url is a
    video link an article itself carries; searched recordings are candidates for review in
    data_center_community_event_recording, never attached here.
*/

with keyed as (
    select * from {{ ref('int_data_center_community_event__item') }}
),

events as (
    select
        event_key,
        min(status)                                                              as status,
        (array_agg(master_org_id order by published_on nulls last, news_item_id))[1]  as master_org_id,
        (array_agg(project_id order by published_on nulls last, news_item_id))[1]     as project_id,
        (array_agg(jurisdiction_id order by published_on nulls last, news_item_id))[1] as jurisdiction_id,
        (array_agg(state_code order by published_on nulls last, news_item_id))[1]     as state_code,
        (array_agg(city order by published_on nulls last, news_item_id))[1]           as city,
        (array_agg(event_kind order by published_on nulls last, news_item_id))[1]     as event_kind,
        min(event_date)                                                          as event_date,
        (array_agg(event_date_basis order by (event_date is null), event_date_basis, news_item_id))[1]
                                                                                 as event_date_basis,
        (array_agg(recording_url order by (recording_url is null), published_on, news_item_id))[1]
                                                                                 as recording_url,
        (array_agg(title order by published_on nulls last, news_item_id))[1]          as title,
        min(published_on)                                                        as first_reported_on,
        count(*)                                                                 as source_count
    from keyed
    group by event_key
),

candidates as (
    select community_event_id, count(*) as n
    from {{ ref('int_data_center_community_event__recording') }}
    group by 1
)

select
    md5(e.event_key)::text                                    as community_event_id,
    e.status::text                                            as status,
    'company'::text                                           as host_type,
    e.master_org_id::text                                     as master_org_id,
    c.company_name::text                                      as host_name,
    e.project_id::text                                        as project_id,
    p.project_name::text                                      as project_name,
    e.jurisdiction_id::text                                   as jurisdiction_id,
    e.city::text                                              as city,
    e.state_code::text                                        as state_code,
    case when e.state_code is not null then {{ state_code_to_name('e.state_code') }} end::text as state,
    e.event_kind::text                                        as event_kind,
    e.event_date::date                                        as event_date,
    (case when e.event_date is not null then e.event_date_basis end)::text as event_date_basis,
    e.recording_url::text                                     as recording_url,
    coalesce(rc.n, 0)::int                                    as recording_candidate_count,
    e.title::text                                             as title,
    e.first_reported_on::date                                 as first_reported_on,
    e.source_count::int                                       as source_count
from events as e
left join {{ ref('mdm_organization_data_center') }} as c on c.master_org_id = e.master_org_id
left join {{ ref('data_center_project') }} as p on p.project_id = e.project_id
left join candidates as rc on rc.community_event_id = md5(e.event_key)
