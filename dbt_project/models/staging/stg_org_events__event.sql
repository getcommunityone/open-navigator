{{ config(materialized='view') }}

/*
    Staging: upcoming events nonprofits publish on their own websites (#1347). One row per event_key. Only what the
    page states: a title and a start date are required; the time is kept only when the source gives one.
*/

select
    event_key,
    nullif(trim(ein), '')                                   as ein,
    nullif(trim(title), '')                                 as title,
    start_at,
    start_date,
    end_at,
    nullif(trim(location), '')                              as location,
    nullif(trim(event_url), '')                             as event_url,
    source_page_url,
    source_format,
    fetched_at
from {{ source('bronze', 'bronze_organization_event') }}
where nullif(trim(title), '') is not null
  and start_date is not null
