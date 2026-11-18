{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    The articles and announcements that report each company-hosted data center meeting
    (#532). Grain: one row per (community_event_id, news item). Every event keeps every
    source: URL, title, publisher, date and the verbatim snippet the match was made on,
    with the meeting word in <mark>.
*/

select
    md5(i.community_event_id || '|' || i.news_item_id)::text    as community_event_source_id,
    i.community_event_id::text                                   as community_event_id,
    i.news_item_id::text                                         as news_item_id,
    i.source::text                                               as source,
    i.url::text                                                  as url,
    i.title::text                                                as title,
    i.publisher::text                                            as publisher,
    i.published_on::date                                         as published_on,
    i.event_kind::text                                           as matched_kind,
    regexp_replace(i.body,
        '\m(town hall|community meeting|open house|information session|public meeting)(s?)\M',
        '<mark>\1\2</mark>', 'gi')::text                         as evidence
from {{ ref('int_data_center_community_event__item') }} as i
inner join {{ ref('data_center_community_event') }} as e on e.community_event_id = i.community_event_id
