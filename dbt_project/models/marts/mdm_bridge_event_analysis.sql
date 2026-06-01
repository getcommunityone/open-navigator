{{ config(
    materialized='table',
    tags=['marts', 'events', 'mdm', 'event-extraction'],
    indexes=[
      {'columns': ['event_id'], 'type': 'btree'},
      {'columns': ['event_meeting_id'], 'unique': True},
      {'columns': ['video_id'], 'type': 'btree'}
    ]
) }}

/*
MDM crosswalk: AI-extraction analysis <-> master golden-record event.

    event_meeting.event_meeting_id  <->  event.event_id

This is the missing link between the two event families:
  - `event_meeting` (+ its partitioned children) — entities the LLM extracted
    from analyzed meetings, keyed on the bronze analysis id and resolved to the
    canonical OCD event (civic_event) lineage.
  - `event` — the MDM golden record, a video_url-deduped union of CDP + LocalView.

The two never shared a key: `event`'s surrogate event_id is an unstable
ROW_NUMBER() reassigned on every rebuild, so nothing can hold a *persistent* FK
to it. Like mdm_bridge_event_source, this bridge is a table model rebuilt in the
same dbt run AFTER `event`, so its FK is recreated against the fresh event_id set
every time — the only rebuild-safe way to enforce the link in Postgres.

JOIN KEY: the YouTube video_id. `event_meeting` already carries video_id; for
`event` it is parsed out of video_url with the same logic as int_events_union.
video_id is unique in `event` (verified: 0 collisions), so each analysis resolves
to at most one master event. INNER join — only analyses that actually surfaced in
the golden record get a row (most analyses have no master event yet, by design).

Grain: one row per analysis that matched a master event. PK event_meeting_id,
FK event_meeting_id -> event_meeting, FK event_id -> event. No c1_* dependency.
*/

WITH event_videos AS (
    SELECT
        event_id,
        COALESCE(
            -- Primary: parse the video_id out of the YouTube URL.
            CASE
                WHEN video_url LIKE '%youtube.com%' OR video_url LIKE '%youtu.be%'
                THEN REGEXP_REPLACE(
                         REGEXP_REPLACE(video_url, '.*[?&]v=([^&]+).*', '\1'),
                         '.*youtu\.be/([^?]+).*', '\1')
            END,
            -- Fallback: sources whose datasource_id IS the video_id.
            CASE
                WHEN source IN ('youtube', 'localview')
                THEN NULLIF(TRIM(datasource_id), '')
            END
        ) AS video_id
    FROM {{ ref('event') }}
    WHERE video_url IS NOT NULL
),

-- video_id is already unique in `event`; DISTINCT ON guards against future drift.
event_by_video AS (
    SELECT DISTINCT ON (video_id)
        video_id,
        event_id
    FROM event_videos
    WHERE video_id IS NOT NULL
    ORDER BY video_id, event_id
),

meetings AS (
    SELECT
        event_meeting_id,
        NULLIF(TRIM(video_id), '') AS video_id
    FROM {{ ref('event_meeting') }}
    WHERE NULLIF(TRIM(video_id), '') IS NOT NULL
)

SELECT
    m.event_meeting_id::INTEGER AS event_meeting_id,
    e.event_id::BIGINT          AS event_id,
    m.video_id::TEXT            AS video_id
FROM meetings m
JOIN event_by_video e ON e.video_id = m.video_id
