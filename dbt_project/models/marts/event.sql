{{
  config(
    materialized='table',
    tags=['marts', 'events', 'production', 'cdp-compatible'],
    unique_key='event_id',
    indexes=[
      {'columns': ['event_date'], 'type': 'btree'},
      {'columns': ['event_datetime'], 'type': 'btree'},
      {'columns': ['state_code', 'state'], 'type': 'btree'},
      {'columns': ['jurisdiction_name', 'state_code'], 'type': 'btree'},
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['body_name'], 'type': 'btree'},
      {'columns': ['channel_id'], 'type': 'btree'},
      {'columns': ['video_url'], 'unique': True},
      {'columns': ['source'], 'type': 'btree'}
    ]
  )
}}

/*
Production event table - API-ready meeting events

CDP-Compatible: Follows Council Data Project (CDP) backend schema
See: https://councildataproject.org/cdp-backend/database_models.html

This model:
- Unions CDP events with LocalView meetings, deduplicated by video_url
  (LocalView rows are added only when their YouTube video is not already
  present from a CDP/other source — CDP wins on conflict)
- Deduplicates within each source by video_url (keeps most recent)
- Applies quality filters
- Provides clean, consistent data for API consumption
- Maps to CDP Event and Session models

Used by: api/routes/search_postgres.py, frontend event search

MDM consolidated event: this is the single golden-record event surface in the
public schema. Per-source feeds (CDP, LocalView) live in staging/intermediate and
are unioned + deduped here. The source-occurrence crosswalk back to each
contributing row is mdm_bridge_event_source (keyed on match_key).

Data Flow:
  bronze_events_cdp -> stg_bronze_events_cdp        ┐
                                                    ├─> event (this model)
  int_events_localview_enriched (jurisdiction_id) ──┘  (anti-joined on video_url)
*/

WITH cdp_deduplicated AS (
    SELECT
        *,
        -- Rank by loaded_at to keep most recent version
        ROW_NUMBER() OVER (
            PARTITION BY
                CASE
                    WHEN video_url IS NOT NULL THEN video_url
                    ELSE CONCAT(datasource_id, '_', source)
                END
            ORDER BY loaded_at DESC, bronze_event_id DESC
        ) AS row_num
    FROM {{ ref('stg_bronze_events_cdp') }}
),

-- CDP events mapped to the shared event column set.
cdp_events AS (
    SELECT
        -- Natural dedup key, exposed for mdm_bridge_event_source to join on.
        CASE
            WHEN video_url IS NOT NULL THEN video_url
            ELSE CONCAT(datasource_id, '_', source)
        END                      AS match_key,
        title                    AS event_title,
        description              AS event_description,
        event_date,
        event_time,
        event_datetime,
        body_name,
        body_description,
        jurisdiction_id,
        channel_id,
        jurisdiction_name,
        jurisdiction_type,
        state_code,
        state,
        city,
        location,
        location_description,
        meeting_type,
        status,
        agenda_url,
        minutes_url,
        video_url,
        session_content_hash,
        view_count,
        duration_minutes,
        like_count,
        language,
        channel_type,
        channel_url,
        source,
        datasource_id,
        external_source_id
    FROM cdp_deduplicated
    WHERE
        row_num = 1
        AND NOT missing_title
        AND NOT missing_date
),

-- LocalView meetings (already keyed to a canonical jurisdiction_id) mapped to
-- the same column set. Added only when the YouTube video is not already in the
-- CDP set, so CDP remains authoritative on overlap.
localview_events AS (
    SELECT
        -- video_url is always present here (filtered below), so it is the key.
        lv.video_url                     AS match_key,
        lv.event_title,
        lv.event_description,
        lv.event_date,
        NULL::TIME                       AS event_time,
        NULL::TIMESTAMP                  AS event_datetime,
        lv.meeting_type                  AS body_name,
        NULL::TEXT                       AS body_description,
        lv.jurisdiction_id,
        lv.channel_id,
        COALESCE(lv.jurisdiction_name, lv.source_place_name) AS jurisdiction_name,
        lv.jurisdiction_type,
        lv.state_code,
        lv.state,
        lv.source_place_name             AS city,
        NULL::TEXT                       AS location,
        NULL::TEXT                       AS location_description,
        lv.meeting_type,
        NULL::TEXT                       AS status,
        NULL::TEXT                       AS agenda_url,
        NULL::TEXT                       AS minutes_url,
        lv.video_url,
        NULL::TEXT                       AS session_content_hash,
        lv.view_count::BIGINT            AS view_count,
        lv.duration_minutes::DOUBLE PRECISION AS duration_minutes,
        lv.like_count::BIGINT            AS like_count,
        NULL::TEXT                       AS language,
        lv.channel_type,
        NULL::TEXT                       AS channel_url,
        'localview'::TEXT                AS source,
        lv.datasource_id,
        NULL::TEXT                       AS external_source_id
    FROM {{ ref('int_events_localview_enriched') }} lv
    WHERE lv.video_url IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM cdp_events c WHERE c.video_url = lv.video_url
      )
),

combined AS (
    SELECT * FROM cdp_events
    UNION ALL
    SELECT * FROM localview_events
)

SELECT
    -- Surrogate key over the unified set
    ROW_NUMBER() OVER (ORDER BY event_date DESC NULLS LAST, video_url) AS event_id,

    -- Event basics (CDP-compatible)
    event_title,
    event_description,
    event_date,
    event_time,
    event_datetime,

    -- Meeting Body (CDP concept)
    body_name,
    body_description,

    -- Organization/Jurisdiction
    jurisdiction_id,
    channel_id,
    jurisdiction_name,
    jurisdiction_type,
    state_code,
    state,
    city,

    -- Meeting details
    location,
    location_description,
    meeting_type,
    status,

    -- Documents/links (CDP-compatible)
    agenda_url,
    minutes_url,
    video_url,
    session_content_hash,

    -- YouTube video metrics
    view_count,
    duration_minutes,
    like_count,
    language,
    channel_type,
    channel_url,

    -- Data source tracking (CDP-compatible)
    source,
    datasource_id,
    external_source_id,
    CURRENT_TIMESTAMP AS last_updated

FROM combined
ORDER BY event_date DESC NULLS LAST, event_id
