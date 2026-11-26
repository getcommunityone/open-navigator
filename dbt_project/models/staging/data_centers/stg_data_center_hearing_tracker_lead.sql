{{ config(materialized='view', tags=['staging', 'data_centers']) }}

/*
    Data center hearing leads from the CC BY 4.0 trackers (#956), from
    bronze_data_center_hearing_tracker_lead (python -m ingestion.data_centers.load_hearing_tracker_leads).
    Grain: one row per tracker record that names a data center meeting and a local place.

    A tracker record is a LEAD: it only says where to look. It becomes a hearing the site shows
    only when the government's own page confirms it (data_center_hearing). Nothing here is served.

      datacenterfights  data.json `meetings`, except `source_type = 'user-added'` (anyone can add
                        those). The place is read from the body's own words ("Hazle Township
                        Board of Supervisors" -> Hazle Township, "Denton City Council" -> Denton
                        City, "City of Denton Planning Commission" -> Denton). A record whose body
                        names no county, parish, borough, township, city, town or village (a
                        state commission, "Voters") is left out: we don't guess its place.
      sitingradar       the upcoming CSV, data center sector only. The place is its
                        `jurisdiction` ("Village of Chesaning" -> Chesaning), with census_geoid.
    Only each tracker's latest file counts: a record it has since dropped is no longer a lead.

    source_kind is 'official' only when the cited URL's host is a government host: .gov, a
    locality .us name (ci.monticello.mn.us, co.x.va.us: a 2-letter state before .us), or a
    government's own subdomain of an agenda platform (x.legistar.com, x.api.civicclerk.com,
    x.granicus.com, x.boarddocs.com, x.primegov.com, x.iqm2.com, x.novusagenda.com,
    x.civicweb.net; never a www. vendor page). A bare .us, .com or .org name is never official, however it reads
    (cityofx.com can be registered by anyone), and neither is a URL with user info (x.gov@host).
    Only official URLs are fetched and checked. Anything else (news, a notice registry, a city
    site on .com) is 'tracker': a lead with no official page yet.
    The bronze table is created by the loader, or empty by the on-run-start macro
    ensure_data_center_hearing_tables, so the served marts still build without it.
*/

{%- set official_host_rx = "^([a-z0-9-]+\\.)+(gov|[a-z]{2}\\.us)$|^(?!www\\.)([a-z0-9-]+\\.)+(legistar|civicclerk|granicus|boarddocs|primegov|iqm2|novusagenda)\\.com$|^(?!www\\.)([a-z0-9-]+\\.)+civicweb\\.net$" %}
{%- set place_rx = "^(.+?) (County|Parish|Borough|Township|City|Village|Town)\\M" %}
{%- set body_words = "(?:Board|Council|Commission|Commissioners|Plan|Planning|Zoning|Assembly|Committee|Supervisors|Trustees|Selectboard|Aldermen|Mayor|Public|Hearing|Meeting|Special|Regular)" %}

with raw as (
    -- each tracker's latest file only
    select r.*
    from {{ source('bronze', 'bronze_data_center_hearing_tracker_lead') }} as r
    where r.fetched_at = (
        select max(l.fetched_at) from {{ source('bronze', 'bronze_data_center_hearing_tracker_lead') }} as l
        where l.tracker = r.tracker
    )
),

dcf as (
    select
        tracker,
        record_id,
        attribution,
        fetched_at,
        case when record->>'date' ~ '^\d{4}-\d{2}-\d{2}$' then (record->>'date')::date end   as meeting_date,
        upper(btrim(record->>'state'))                                                      as state_code,
        nullif(btrim(record->>'body'), '')                                                  as body_name,
        nullif(btrim(record->>'topic'), '')                                                 as topic,
        nullif(btrim(record->>'source'), '')                                                as source_url,
        null::text                                                                          as census_geoid,
        -- the place, from the body's own words; null when it names none. "City of X …" stops
        -- at the first body word; otherwise the name keeps its type word ("Kansas City").
        coalesce(
            nullif(regexp_replace(regexp_replace(
                (regexp_match(btrim(record->>'body'), '^(?:City|Town|Village) of (.+)$'))[1],
                '\s*[(,].*$', ''), '\s+{{ body_words }}\M.*$', '', 'i'), ''),
            (select m[1] || ' ' || m[2]
             from (select regexp_match(btrim(record->>'body'), '{{ place_rx }}') as m) as x
             where m[1] !~ '^(Board|Council|Commission|Committee) of\M')
        )                                                                                   as jurisdiction_name
    from raw
    where tracker = 'datacenterfights'
      and coalesce(record->>'source_type', '') <> 'user-added'
),

sr as (
    select
        tracker,
        record_id,
        attribution,
        fetched_at,
        case when record->>'event_date' ~ '^\d{4}-\d{2}-\d{2}$' then (record->>'event_date')::date end as meeting_date,
        upper(btrim(record->>'state'))                                                      as state_code,
        nullif(btrim(record->>'body'), '')                                                  as body_name,
        nullif(btrim(record->>'summary'), '')                                               as topic,
        nullif(btrim(record->>'source_url'), '')                                            as source_url,
        nullif(btrim(record->>'census_geoid'), '')                                          as census_geoid,
        nullif(regexp_replace(btrim(record->>'jurisdiction'), '^(City|Town|Village|Borough) of ', ''), '') as jurisdiction_name
    from raw
    where tracker = 'sitingradar'
      and coalesce(record->>'sectors', '') ~ '(^|\|)data_center(\||$)'
),

unioned as (
    select * from dcf
    union all
    select * from sr
)

select
    (case tracker when 'datacenterfights' then 'dcf-' else 'sr-' end || record_id)::text   as lead_id,
    tracker::text                                                                           as tracker,
    record_id::text                                                                         as record_id,
    meeting_date::date                                                                      as meeting_date,
    btrim(jurisdiction_name)::text                                                          as jurisdiction_name,
    state_code::text                                                                        as state_code,
    body_name::text                                                                         as body_name,
    topic::text                                                                             as topic,
    (case when is_official then 'official' else 'tracker' end)::text                       as source_kind,
    (case when is_official then 'Government page cited by ' || attribution
          else attribution end)::text                                                       as source_name,
    source_url::text                                                                        as source_url,
    census_geoid::text                                                                      as census_geoid,
    attribution::text                                                                       as attribution,
    fetched_at::timestamptz                                                                 as fetched_at
from (
    select
        u.*,
        coalesce(
            authority !~ '@'
            and lower(regexp_replace(authority, ':\d+$', '')) ~ '{{ official_host_rx }}',
            false
        ) as is_official
    from (select *, substring(source_url from '^https?://([^/?#]*)') as authority from unioned) as u
) as classified
where meeting_date is not null
  and state_code ~ '^[A-Z]{2}$'
  and nullif(btrim(jurisdiction_name), '') is not null
