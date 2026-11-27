{{
  config(
    materialized='table',
    tags=['marts', 'organization', 'upcoming', 'serving'],
    indexes=[{'columns': ['master_org_id', 'event_date'], 'type': 'btree'}]
  )
}}

/*
    Mart: organization_event (#1347) — upcoming events nonprofits publish on their own public websites (schema.org
    Event markup or an iCal feed), read politely by ingestion.org_events.crawl. Grain: one row per event.

    PK  organization_event_id = the bronze event_key (md5 of EIN | event URL | start date | title).
    FK  master_org_id -> mdm_organization.

    Nothing is inferred: the title, date, time and place are the site's own. event_time is set only when the source
    gives a time. Rows are kept from the build date on; the API shows only event_date >= today.
    Options, costs and terms: web_docs/docs/development/organization-events.md.
*/

select
    e.event_key::text                                                   as organization_event_id,
    n.master_org_id::text                                               as master_org_id,
    e.ein::text                                                         as ein,
    o.org_name::text                                                    as org_name,
    e.title::text                                                       as title,
    e.start_date::date                                                  as event_date,
    (case when e.start_at is not null then to_char(e.start_at, 'FMHH12:MI AM') end)::text as event_time,
    e.location::text                                                    as location,
    coalesce(e.event_url, e.source_page_url)::text                      as event_url,
    e.source_page_url::text                                             as source_page_url,
    e.source_format::text                                               as source_format,
    o.state_code::text                                                  as state_code,
    ({{ state_code_to_name('o.state_code') }})::text                    as state,
    nullif(trim(o.city_norm), '')::text                                 as city,
    e.fetched_at::timestamptz                                           as fetched_at,
    now()::timestamptz                                                  as built_at
from {{ ref('stg_org_events__event') }} as e
inner join {{ ref('mdm_organization_nonprofit') }} as n on n.ein = e.ein
inner join {{ ref('mdm_organization') }} as o on o.master_org_id = n.master_org_id
where e.start_date >= current_date
  and o.state_code is not null
