{{
  config(
    materialized='table',
    tags=['intermediate', 'youtube', 'events', 'jurisdictions'],
    indexes=[
      {'columns': ['video_id'], 'unique': True},
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['resolution_confidence'], 'type': 'btree'},
      {'columns': ['resolution_method'], 'type': 'btree'}
    ]
  )
}}

/*
Intermediate: resolved jurisdiction geography for channel-discovered YouTube
videos whose `bronze.bronze_event_youtube` row landed with a NULL/blank
`jurisdiction_id` (datasource = 'youtube').

Declarative replacement for the in-place UPDATE in
packages/scrapers/src/scrapers/youtube/backfill_youtube_jurisdiction_from_channels.py.
Rather than mutating bronze, the resolution is derived here as a SELECT and
exposed at one-row-per-video grain. Bronze stays raw.

Resolution, in DESCENDING trust (COALESCE-style precedence 0 -> 1 -> 2):

  0. localview_enriched (confidence=high) — int_events_localview_enriched carries a
     geoid-resolved canonical jurisdiction_id per video_url. A materialized geoid
     match, no guessing. Resolves ~all of today's blank set.
  1. scraped (confidence=high) — bronze_jurisdictions_{counties,municipalities}_scraped
     carry a 1:1 youtube_channel_id -> jurisdiction_id (priority-states campaign).
     Unambiguous by construction.
  2. catalog (confidence high/medium/low) — bronze_events_channels.jurisdictions
     (JSONB array). Each entry is canonicalized to an int_jurisdictions id (legacy
     `<type>_<geoid>` forms reconciled via trailing geoid), then deduped by geoid:
       - one distinct geoid                         -> high  (catalog_single)
       - parent county/state + exactly one local    -> medium (catalog_county_town)
       - several distinct local jurisdictions (PEG)  -> low   (catalog_multi),
         deterministic pick: most specific type, then lowest geoid.

Name / state_code / state / canonical type come from int_jurisdictions
(authoritative); the catalog JSONB entry is the fallback when a jurisdiction_id is
absent there. Only blank datasource='youtube' rows are emitted, so this mirrors the
idempotent backfill target set.

Grain: one row per video_id (bronze_event_youtube row).
*/

WITH

-- Canonical jurisdiction reference (authoritative name / state / type).
juris AS (
    SELECT
        jurisdiction_id,
        geoid,
        name,
        state_code,
        state,
        jurisdiction_type
    FROM {{ ref('int_jurisdictions') }}
    WHERE jurisdiction_id IS NOT NULL
),

-- Type specificity for breaking a genuine multi-jurisdiction tie (most specific
-- first — a regional channel is most usefully attributed to the municipality).
-- Mirrors _TYPE_SPECIFICITY in the Python source.
type_specificity AS (
    SELECT * FROM (VALUES
        ('municipality', 0),
        ('township', 1),
        ('school_district', 2),
        ('county', 3),
        ('state', 4)
    ) AS t(jurisdiction_type, specificity)
),

-- The blank target set: channel-discovered youtube rows with no jurisdiction_id.
targets AS (
    SELECT
        video_id,
        NULLIF(TRIM(channel_id), '') AS channel_id
    FROM {{ source('bronze', 'bronze_event_youtube') }}
    WHERE datasource = 'youtube'
      AND (jurisdiction_id IS NULL OR jurisdiction_id = '')
      AND video_id IS NOT NULL AND video_id <> ''
),

-- ── Source 0: LocalView resolved model (video-grain, highest trust) ──────────
localview AS (
    SELECT
        regexp_replace(video_url, '^.*[=/]', '') AS video_id,
        jurisdiction_id
    FROM {{ ref('int_events_localview_enriched') }}
    WHERE jurisdiction_id IS NOT NULL AND jurisdiction_id <> ''
      AND video_url IS NOT NULL AND video_url <> ''
),

-- One jurisdiction_id per video (collapse any duplicate video_url forms).
localview_by_video AS (
    SELECT video_id, MIN(jurisdiction_id) AS jurisdiction_id
    FROM localview
    GROUP BY video_id
),

-- ── Source 1: scraped 1:1 channel -> jurisdiction map (channel-grain) ────────
scraped_raw AS (
    SELECT NULLIF(TRIM(youtube_channel_id), '') AS channel_id,
           NULLIF(TRIM(jurisdiction_id), '')    AS jurisdiction_id
    FROM {{ source('bronze', 'bronze_jurisdictions_counties_scraped') }}
    WHERE NULLIF(TRIM(youtube_channel_id), '') IS NOT NULL
      AND NULLIF(TRIM(jurisdiction_id), '') IS NOT NULL
    UNION ALL
    SELECT NULLIF(TRIM(youtube_channel_id), '') AS channel_id,
           NULLIF(TRIM(jurisdiction_id), '')    AS jurisdiction_id
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities_scraped') }}
    WHERE NULLIF(TRIM(youtube_channel_id), '') IS NOT NULL
      AND NULLIF(TRIM(jurisdiction_id), '') IS NOT NULL
),

-- 1:1 by construction; if a channel ever maps to two jurisdictions, pick
-- deterministically (lowest id) so the model is stable.
scraped_map AS (
    SELECT DISTINCT ON (channel_id) channel_id, jurisdiction_id
    FROM scraped_raw
    ORDER BY channel_id, jurisdiction_id
),

-- ── Source 2: channel catalog JSONB array (channel-grain) ────────────────────
-- Only resolve catalog for channels that appear on a blank target and were not
-- already covered by the scraped map (keeps the explode cheap).
catalog_channels AS (
    SELECT DISTINCT t.channel_id
    FROM targets t
    LEFT JOIN scraped_map s ON s.channel_id = t.channel_id
    WHERE t.channel_id IS NOT NULL
      AND s.channel_id IS NULL
),

catalog_entries AS (
    SELECT
        cc.channel_id,
        NULLIF(TRIM(e->>'jurisdiction_id'), '') AS raw_jid,
        e AS entry
    FROM {{ source('bronze', 'bronze_events_channels') }} cc
    JOIN catalog_channels k ON k.channel_id = cc.channel_id
    CROSS JOIN LATERAL jsonb_array_elements(cc.jurisdictions) e
    WHERE cc.jurisdictions IS NOT NULL
      AND cc.jurisdictions::text NOT IN ('', '[]', 'null', '{}')
      AND NULLIF(TRIM(e->>'jurisdiction_id'), '') IS NOT NULL
),

-- Canonicalize each catalog entry to an int_jurisdictions id. Direct id match
-- wins; otherwise reconcile the legacy `<type>_<geoid>` form by trailing geoid.
-- When a geoid backs several canonical ids (rare), the most specific type wins
-- (DISTINCT ON over the specificity rank), mirroring _to_canonical().
catalog_canon AS (
    SELECT DISTINCT ON (ce.channel_id, ce.raw_jid)
        ce.channel_id,
        ce.raw_jid,
        ce.entry,
        j.jurisdiction_id   AS canon_id,
        j.geoid             AS canon_geoid,
        j.jurisdiction_type AS canon_type
    FROM catalog_entries ce
    JOIN juris j
        ON j.jurisdiction_id = ce.raw_jid
        OR j.geoid = (regexp_match(ce.raw_jid, '_([0-9]+)$'))[1]
    LEFT JOIN type_specificity ts ON ts.jurisdiction_type = j.jurisdiction_type
    ORDER BY ce.channel_id, ce.raw_jid, COALESCE(ts.specificity, 99), j.jurisdiction_id
),

-- Distinct canonical jurisdictions per channel (one row per canon_id), keeping
-- the first catalog entry for JSONB fallback.
catalog_distinct AS (
    SELECT DISTINCT ON (channel_id, canon_id)
        channel_id,
        canon_id,
        canon_geoid,
        canon_type,
        entry
    FROM catalog_canon
    ORDER BY channel_id, canon_id
),

-- Per-channel shape: distinct geoids, distinct LOCAL geoids (non county/state),
-- and the deterministic low-confidence pick.
catalog_agg AS (
    SELECT
        channel_id,
        COUNT(DISTINCT canon_geoid)                                       AS distinct_geoids,
        COUNT(DISTINCT canon_geoid) FILTER (
            WHERE canon_type NOT IN ('county', 'state')
        )                                                                 AS distinct_local_geoids
    FROM catalog_distinct
    GROUP BY channel_id
),

-- Rank rows within each channel so we can pick the single resolved jurisdiction
-- for each confidence tier without a self-join.
catalog_ranked AS (
    SELECT
        cd.channel_id,
        cd.canon_id,
        cd.canon_geoid,
        cd.canon_type,
        cd.entry,
        ca.distinct_geoids,
        ca.distinct_local_geoids,
        -- Prefer local jurisdictions, then most specific type, then lowest geoid.
        ROW_NUMBER() OVER (
            PARTITION BY cd.channel_id
            ORDER BY
                CASE WHEN cd.canon_type IN ('county', 'state') THEN 1 ELSE 0 END,
                COALESCE(ts.specificity, 99),
                cd.canon_geoid
        ) AS pick_rank
    FROM catalog_distinct cd
    JOIN catalog_agg ca ON ca.channel_id = cd.channel_id
    LEFT JOIN type_specificity ts ON ts.jurisdiction_type = cd.canon_type
),

-- One resolved row per channel from the catalog, with confidence + method.
catalog_resolved AS (
    SELECT
        channel_id,
        canon_id AS jurisdiction_id,
        entry,
        CASE
            WHEN distinct_geoids = 1                THEN 'high'
            WHEN distinct_local_geoids = 1          THEN 'medium'
            ELSE 'low'
        END AS resolution_confidence,
        CASE
            WHEN distinct_geoids = 1                THEN 'catalog_single'
            WHEN distinct_local_geoids = 1          THEN 'catalog_county_town'
            ELSE 'catalog_multi'
        END AS resolution_method
    FROM catalog_ranked
    WHERE pick_rank = 1
),

-- ── Combine sources 0 -> 1 -> 2 in trust order ──────────────────────────────
resolved AS (
    SELECT
        t.video_id,
        t.channel_id,
        COALESCE(lv.jurisdiction_id, sc.jurisdiction_id, cat.jurisdiction_id) AS jurisdiction_id,
        CASE
            WHEN lv.jurisdiction_id IS NOT NULL THEN 'high'
            WHEN sc.jurisdiction_id IS NOT NULL THEN 'high'
            ELSE cat.resolution_confidence
        END AS resolution_confidence,
        CASE
            WHEN lv.jurisdiction_id IS NOT NULL THEN 'localview_enriched'
            WHEN sc.jurisdiction_id IS NOT NULL THEN 'scraped'
            ELSE cat.resolution_method
        END AS resolution_method,
        cat.entry AS catalog_entry
    FROM targets t
    LEFT JOIN localview_by_video lv ON lv.video_id = t.video_id
    LEFT JOIN scraped_map sc        ON sc.channel_id = t.channel_id
    LEFT JOIN catalog_resolved cat  ON cat.channel_id = t.channel_id
)

SELECT
    r.video_id,
    r.channel_id,
    r.jurisdiction_id,
    -- Authoritative name / type / state from int_jurisdictions; fall back to the
    -- catalog JSONB entry when the id is absent there (mirrors _build_resolution).
    COALESCE(j.name,             r.catalog_entry->>'jurisdiction_name') AS jurisdiction_name,
    COALESCE(j.jurisdiction_type, r.catalog_entry->>'jurisdiction_type') AS jurisdiction_type,
    COALESCE(j.state_code,       r.catalog_entry->>'state_code')        AS state_code,
    COALESCE(j.state,            r.catalog_entry->>'state')             AS state,
    r.resolution_confidence,
    r.resolution_method,
    CURRENT_TIMESTAMP AS transformed_at
FROM resolved r
LEFT JOIN juris j ON j.jurisdiction_id = r.jurisdiction_id
WHERE r.jurisdiction_id IS NOT NULL
