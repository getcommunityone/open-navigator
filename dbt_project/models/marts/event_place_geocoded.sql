{{
    config(
        materialized='view',
        tags=['marts', 'event-extraction', 'ai', 'geocode']
    )
}}

/*
public.event_place_geocoded — event_place enriched with cached geocodes.

WHY a downstream view (not an in-place change to event_place):
  event_place is native range-partitioned and APPEND-only, so an in-place COALESCE
  would only apply to rows at insert time and would NOT pick up geocodes that land
  in the cache later. bronze.place_geocode_cache is filled asynchronously (a smoke
  run today, a full nationwide backfill later), so the enrichment must re-resolve
  on every read. A view over event_place LEFT JOINed to the cache does exactly
  that with zero storage churn and preserves event_place as the raw extract.

KEY: joins on the cache's geocode_key, which is defined as
  lower(collapse-whitespace(coalesce(normalized_address, geocode_query, raw_text)))
  — reproduced verbatim here so the join matches the cache loader's key.

COALESCE precedence: existing event_place.latitude/longitude WIN; the cache only
fills gaps (and only where cache.geocode_status = 'ok'). geocode_source records
where the surfaced coordinate came from ('extract' | the cache's geocode_source |
NULL when still ungeocoded).
*/

with ep as (
    select
        *,
        lower(regexp_replace(
            trim(coalesce(normalized_address, geocode_query, raw_text)),
            '\s+', ' ', 'g'
        )) as geocode_key
    from {{ ref('event_place') }}
),

cache as (
    select
        geocode_key,
        latitude       as cache_latitude,
        longitude      as cache_longitude,
        geocode_source as cache_geocode_source
    from {{ source('bronze', 'place_geocode_cache') }}
    where geocode_status = 'ok'
)

select
    ep.event_place_id,
    ep.extraction_key,
    ep.analysis_id,
    ep.legacy_event_id,
    ep.c1_event_id,

    ep.state_code,
    ep.state,
    ep.jurisdiction_name,
    ep.jurisdiction_type,
    ep.city,

    ep.place_id,
    ep.raw_text,
    ep.normalized_address,
    ep.place_type,
    ep.street_address,
    ep.place_city,
    ep.place_state_code,
    ep.geocode_query,

    -- existing coordinates win; cache only fills the gaps
    coalesce(ep.latitude,  c.cache_latitude)  as latitude,
    coalesce(ep.longitude, c.cache_longitude) as longitude,

    -- provenance of the surfaced coordinate
    case
        when ep.latitude is not null and ep.longitude is not null then 'extract'
        when c.cache_latitude is not null and c.cache_longitude is not null
            then coalesce(c.cache_geocode_source, 'geocode_cache')
        else null
    end                                       as geocode_source,

    ep.geocode_status,
    ep.linked_decision_ids,
    ep.linked_item_ids,
    ep.mention_count,

    ep.source_ai_model,
    ep.extracted_at
from ep
left join cache c on c.geocode_key = ep.geocode_key
