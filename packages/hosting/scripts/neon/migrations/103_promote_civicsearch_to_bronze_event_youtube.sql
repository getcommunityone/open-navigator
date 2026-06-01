-- Migration 103: promote CivicSearch-only meetings into bronze_event_youtube
-- Date: 2026-06-01
-- Target: DEV warehouse (localhost:5433 / NEON_DATABASE_URL_DEV)
--
-- WHY
-- ---
-- CivicSearch meetings ARE YouTube videos (vid_id == the YouTube video_id), but
-- ~48.8k of the ~53.1k CivicSearch meetings were never captured by the
-- LocalView/YouTube ingest, so they exist only in bronze.bronze_events_civicsearch
-- (+ _schools) and not in bronze.bronze_event_youtube. This lands those missing
-- videos as YouTube event rows so they join the unified event spine
-- (int_events_union) like any other YouTube meeting. Tagged datasource =
-- 'civicsearch' for provenance.
--
-- SCOPE / FIDELITY
-- ----------------
-- CivicSearch only carries vid_id, title, meeting_date, location, youtube_url
-- (+ topic snippets handled elsewhere). All YouTube-catalog-only fields (channel,
-- view_count, duration, description, published_at, audio/policy tracking, ...)
-- are unknown here and left NULL/default. state_code is parsed from the trailing
-- 2-letter token of `location` ("Milford, MA" -> "MA") when present; otherwise NULL.
-- This is a metadata stub, NOT a transcript (see the separate transcript decision).
--
-- SAFETY
-- ------
-- Inserts only vid_ids NOT already in bronze_event_youtube (anti-join on
-- video_id), and ON CONFLICT (video_url) DO NOTHING guards the table's existing
-- unique-video_url constraint. Idempotent: re-running is a no-op. Both CivicSearch
-- portals (cities + schools) are unioned and deduped to one row per vid_id.

BEGIN;

INSERT INTO bronze.bronze_event_youtube (
    video_id, event_date, title, location, video_url,
    state_code, datasource, datasource_id,
    transcript_download_attempts, loaded_at, last_updated
)
WITH cs AS (
    -- one row per vid_id across both CivicSearch portals; prefer the row with a
    -- non-null title/date (arbitrary but deterministic via DISTINCT ON ordering).
    SELECT DISTINCT ON (vid_id)
        vid_id, title, meeting_date, location, youtube_url
    FROM (
        SELECT vid_id, title, meeting_date, location, youtube_url
        FROM bronze.bronze_events_civicsearch
        UNION ALL
        SELECT vid_id, title, meeting_date, location, youtube_url
        FROM bronze.bronze_events_civicsearch_schools
    ) u
    WHERE vid_id IS NOT NULL AND btrim(vid_id) <> ''
    ORDER BY vid_id, (title IS NULL), (meeting_date IS NULL)
)
SELECT
    cs.vid_id,
    cs.meeting_date,
    cs.title,
    cs.location,
    COALESCE(cs.youtube_url, 'https://www.youtube.com/watch?v=' || cs.vid_id),
    -- trailing 2-letter state token from "City, ST" / "County, ST"
    CASE
        WHEN cs.location ~ ',\s*[A-Z]{2}\s*$'
        THEN upper(regexp_replace(cs.location, '^.*,\s*([A-Z]{2})\s*$', '\1'))
    END AS state_code,
    'civicsearch'  AS datasource,
    cs.vid_id      AS datasource_id,
    0              AS transcript_download_attempts,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM cs
WHERE NOT EXISTS (
    SELECT 1 FROM bronze.bronze_event_youtube y WHERE y.video_id = cs.vid_id
)
ON CONFLICT (video_url) DO NOTHING;

COMMIT;
