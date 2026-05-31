{{
  config(
    materialized='table',
    tags=['marts', 'events', 'localview'],
    indexes=[
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['state_code'], 'type': 'btree'},
      {'columns': ['event_date'], 'type': 'btree'},
      {'columns': ['channel_id'], 'type': 'btree'},
      {'columns': ['datasource_id'], 'unique': True}
    ]
  )
}}

/*
Mart: LocalView meeting events, API-ready, keyed to a canonical jurisdiction_id.

Surfaces the event-grain jurisdiction resolution from int_events_localview into
the public (marts) schema. Each row is one LocalView meeting video; events whose
place did not resolve to a GEOID keep jurisdiction_id (and the resolved_* fields)
NULL but are still emitted.

Data flow:
  bronze_events_localview
    -> int_events_localview            (event-grain jurisdiction_id resolution)
    -> int_jurisdictions               (canonical jurisdiction name/type)
    -> localview_events  (this model)

Grain: one row per LocalView event (datasource_id = YouTube video id).
*/

WITH events AS (
    SELECT
        event_id,
        datasource_id,
        video_url,
        event_date,
        title,
        meeting_type,
        channel_id,
        -- Raw LocalView place as scraped
        jurisdiction_name AS source_place_name,
        state_code,
        state,
        -- Resolved geography (from int_events_localview)
        jurisdiction_id,
        jurisdiction_geoid,
        jurisdiction_match_type,
        loaded_at
    FROM {{ ref('int_events_localview') }}
    WHERE datasource = 'localview'
      -- Drop a handful of corrupt source rows (place name "NaN", no state)
      AND state_code IS NOT NULL
      AND jurisdiction_name IS NOT NULL
      AND jurisdiction_name <> 'NaN'
)

SELECT
    e.event_id,
    'localview'::TEXT          AS source,
    e.datasource_id,
    e.video_url,
    e.event_date,
    e.title                    AS event_title,
    e.meeting_type,
    e.channel_id,

    -- Canonical jurisdiction (resolved). Falls back to the scraped place name
    -- when no GEOID matched so the column is never blank for display.
    e.jurisdiction_id,
    j.name                     AS jurisdiction_name,
    j.jurisdiction_type        AS jurisdiction_type,
    e.jurisdiction_geoid,
    e.jurisdiction_match_type,

    -- Source-of-record place + state (always present)
    e.source_place_name,
    e.state_code,
    e.state,

    e.loaded_at
FROM events e
LEFT JOIN {{ ref('int_jurisdictions') }} j
    ON j.jurisdiction_id = e.jurisdiction_id
