{{ config(
    materialized='table',
    tags=['marts', 'events', 'mdm'],
    indexes=[
      {'columns': ['event_id'], 'type': 'btree'},
      {'columns': ['source_system'], 'type': 'btree'}
    ]
) }}

/*
MDM crosswalk: one row per source event occurrence -> master event.

    event.event_id  <->  (source_system, source_pk)

Captures every contributing source row, including LocalView videos that the
`event` mart drops as duplicates of a CDP row (CDP wins on a video_url collision).
Those dropped LocalView rows share the same match_key as the surviving CDP row,
so they resolve to the same master event_id here — surfacing the consolidation
that the deduped `event` table otherwise hides.

The join to `event` is on match_key (1:1 with event_id). Occurrences that never
became a master event (CDP rows missing a title/date) are excluded by mirroring
the `event` mart's quality filters, so every bridge row has a valid event_id.
*/

WITH cdp AS (
    SELECT
        'cdp'::TEXT          AS source_system,
        datasource_id::TEXT  AS source_pk,
        CASE
            WHEN video_url IS NOT NULL THEN video_url
            ELSE CONCAT(datasource_id, '_', source)
        END::TEXT            AS match_key,
        video_url::TEXT      AS video_url,
        loaded_at
    FROM {{ ref('stg_bronze_events_cdp') }}
    WHERE NOT missing_title
      AND NOT missing_date
),

localview AS (
    SELECT
        'localview'::TEXT    AS source_system,
        datasource_id::TEXT  AS source_pk,
        video_url::TEXT      AS match_key,   -- video_url is always present here
        video_url::TEXT      AS video_url,
        loaded_at
    FROM {{ ref('int_events_localview_enriched') }}
    WHERE video_url IS NOT NULL
),

occurrences AS (
    SELECT * FROM cdp
    UNION ALL
    SELECT * FROM localview
),

-- One row per real source occurrence (latest load wins on a repeated source_pk).
deduped AS (
    SELECT DISTINCT ON (source_system, source_pk)
        source_system,
        source_pk,
        match_key,
        video_url
    FROM occurrences
    ORDER BY source_system, source_pk, loaded_at DESC NULLS LAST
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['o.source_system', 'o.source_pk']) }} AS event_source_id,
    e.event_id,
    o.source_system,
    o.source_pk,
    o.match_key,
    o.video_url
FROM deduped o
JOIN {{ ref('event') }} e
    ON e.match_key = o.match_key
