{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    Data center news items that describe a company-hosted meeting, each with the key of the
    event it reports (#532). Grain: one row per item (status confirmed or unconfirmed).
    community_event_id = md5(event_key). See data_center_community_event for how articles
    are grouped into one event.
*/

with items as (
    select * from {{ ref('int_data_center_news_item__match') }}
    where status in ('confirmed', 'unconfirmed')
),

dated as (
    select master_org_id, project_id, event_kind, event_date, min(published_on) as first_published_on
    from items
    where status = 'confirmed' and event_date is not null
    group by 1, 2, 3, 4
),

keyed as (
    select
        i.*,
        case
            when i.status = 'unconfirmed' then 'unconfirmed|' || i.news_item_id
            else concat_ws('|', 'confirmed', i.master_org_id, i.project_id, i.event_kind,
                coalesce(
                    i.event_date::text,
                    (select d.event_date::text from dated as d
                     where d.master_org_id = i.master_org_id and d.project_id = i.project_id
                       and d.event_kind = i.event_kind
                       and abs(d.first_published_on - i.published_on) <= 30
                     order by abs(d.first_published_on - i.published_on), d.event_date
                     limit 1),
                    'month:' || to_char(i.published_on, 'YYYY-MM')
                ))
        end as event_key
    from items as i
)

select k.*, md5(k.event_key)::text as community_event_id
from keyed as k
