{{ config(materialized='view', tags=['staging', 'data_centers']) }}

/*
    Data center hearing leads from the CC BY 4.0 trackers (#956), from
    bronze_data_center_hearing_tracker_lead (python -m ingestion.data_centers.load_hearing_tracker_leads).
    Grain: one row per tracker record that names a data center meeting and a local place.

    A tracker record is a LEAD: it only says where to look. It becomes a hearing the site shows
    only when the government's own page confirms it (data_center_hearing). Nothing here is served.

      datacenterfights  data.json `meetings`. The place is read from the body's own words
                        ("Hazle Township Board of Supervisors" -> Hazle Township, "Denton City
                        Council" -> Denton, "Town of Cromwell" -> Cromwell). A record whose body
                        names no county, parish, borough, township, city, town or village (a
                        state commission, "Voters") is left out: we don't guess its place.
      sitingradar       the upcoming CSV, data center sector only. The place is its
                        `jurisdiction` ("Village of Chesaning" -> Chesaning), with census_geoid.

    source_kind is 'official' only when the record's cited URL is on a government host (.gov,
    .us, a cityof… / townof… / countyof… site, or an agenda platform such as Legistar or
    CivicClerk); only those are fetched and checked. Anything else (news, a notice registry)
    is 'tracker': a lead with no official page yet.
    The bronze table is created by the loader; run it once before the first dbt build.
*/

{%- set official_host_rx = "(\\.gov$|\\.us$|\\.gov\\.[a-z]{2}$|(^|\\.)(cityof|townof|villageof|countyof|townshipof)[a-z0-9-]+\\.(com|org|net)$|(^|\\.)(legistar|civicclerk|granicus|municode|boarddocs|primegov|iqm2|novusagenda|civicplus|civicweb|ecode360)\\.(com|net)$)" %}
{%- set place_rx = "^(.+?) (County|Parish|Borough|Township|City|Village|Town)\\M" %}

with raw as (
    select * from {{ source('bronze', 'bronze_data_center_hearing_tracker_lead') }}
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
        -- the place, from the body's own words; null when it names none
        coalesce(
            (regexp_match(btrim(record->>'body'), '^(?:City|Town|Village) of ([^(,]+?)\s*(?:\(|,|$)'))[1],
            (select case when m[2] in ('County', 'Parish', 'Borough', 'Township') then m[1] || ' ' || m[2] else m[1] end
             from (select regexp_match(btrim(record->>'body'), '{{ place_rx }}') as m) as x)
        )                                                                                   as jurisdiction_name
    from raw
    where tracker = 'datacenterfights'
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
    (case when lower(substring(source_url from '^https?://([^/:?#]+)')) ~ '{{ official_host_rx }}'
          then 'official' else 'tracker' end)::text                                         as source_kind,
    (case when lower(substring(source_url from '^https?://([^/:?#]+)')) ~ '{{ official_host_rx }}'
          then 'Government page cited by ' || attribution
          else attribution end)::text                                                       as source_name,
    source_url::text                                                                        as source_url,
    census_geoid::text                                                                      as census_geoid,
    attribution::text                                                                       as attribution,
    fetched_at::timestamptz                                                                 as fetched_at
from unioned
where meeting_date is not null
  and state_code ~ '^[A-Z]{2}$'
  and nullif(btrim(jurisdiction_name), '') is not null
