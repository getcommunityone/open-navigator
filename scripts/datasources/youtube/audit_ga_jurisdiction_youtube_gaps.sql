-- =============================================================================
-- GA: find "missing" cities / counties / school districts vs YouTube pipeline
--
-- Your disk layout (e.g. data/cache/youtube_audio/ga/*) mirrors **bronze rows
-- that were actually downloaded**, not every Census place. "Missing" usually
-- means one of:
--   A) Place not in `jurisdiction` (gold parquet never scraped it)
--   B) In details but `youtube_channel_count` = 0 (discovery found no channel URL)
--   C) Details has `youtube_channels` JSON but `bronze_events_channels` missing row
--      (load_youtube_channels_bronze not run / failed for that channel_id)
--   D) Bronze has channel but no / few `bronze_events_youtube` rows
--      (load_youtube_events_to_postgres not run / filters / API limits)
--   E) Name mismatch: `jurisdiction.name` ≠ `jurisdiction.jurisdiction_name`
--      (join below is exact trimmed lower match — tune for school district spelling)
--
-- Run:
--   ./scripts/datasources/youtube/run_audit_ga_jurisdiction_youtube_gaps.sh
-- =============================================================================

\pset pager off

-- jurisdiction: tolerate legacy tables without state_code (use to_jsonb row).
\echo '========== 1) SCALE: jurisdiction (Census / app universe) =========='
SELECT js.type, COUNT(*) AS n
FROM jurisdiction js
WHERE (
    upper(trim(COALESCE(to_jsonb(js)->>'state_code', ''))) = 'GA'
    OR upper(trim(COALESCE(to_jsonb(js)->>'state', ''))) IN ('GA', 'GEORGIA')
  )
  AND js.type IN ('city', 'county', 'school_district', 'town', 'village')
GROUP BY js.type
ORDER BY n DESC;

\echo ''
\echo '========== 2) SCALE: jurisdiction (gold / discovery universe) =========='
SELECT
  COUNT(*) AS total_ga_rows,
  COUNT(*) FILTER (WHERE COALESCE(youtube_channel_count, 0) > 0) AS rows_with_youtube_count_gt_0,
  COUNT(*) FILTER (
    WHERE COALESCE(youtube_channel_count, 0) > 0
      AND youtube_channels IS NOT NULL
      AND jsonb_typeof(youtube_channels) = 'array'
      AND jsonb_array_length(youtube_channels) > 0
  ) AS rows_with_nonempty_youtube_json
FROM jurisdiction
WHERE state_code = 'GA';

\echo ''
\echo '========== 3) SCALE: bronze (what the downloader / folders are built from) =========='
SELECT
  COUNT(DISTINCT jurisdiction_name) AS distinct_jurisdiction_names,
  COUNT(DISTINCT channel_id) AS distinct_channels,
  COUNT(*) AS video_rows
FROM bronze.bronze_events_youtube
WHERE state_code = 'GA';

\echo ''
\echo '========== 4) DETAILS: GA rows with no discovered YouTube (reason B) — top by population =========='
SELECT
  jurisdiction_id,
  jurisdiction_name,
  jurisdiction_type,
  population,
  youtube_channel_count,
  youtube_channels
FROM jurisdiction
WHERE state_code = 'GA'
  AND (
    COALESCE(youtube_channel_count, 0) = 0
    OR youtube_channels IS NULL
    OR (jsonb_typeof(youtube_channels) = 'array' AND jsonb_array_length(youtube_channels) = 0)
  )
ORDER BY population DESC NULLS LAST
LIMIT 150;

\echo ''
\echo '========== 5) DETAILS has channel JSON but missing bronze_events_channels row (reason C) =========='
WITH d AS (
  SELECT
    jd.jurisdiction_id,
    jd.name,
    jd.jurisdiction_type,
    NULLIF(btrim(ch->>'channel_id'), '') AS channel_id,
    ch->>'channel_url' AS channel_url,
    ch->>'channel_title' AS channel_title
  FROM jurisdiction jd
  CROSS JOIN LATERAL jsonb_array_elements(
    CASE
      WHEN jd.youtube_channels IS NULL THEN '[]'::jsonb
      WHEN jsonb_typeof(jd.youtube_channels) = 'array' THEN jd.youtube_channels
      ELSE '[]'::jsonb
    END
  ) AS ch
  WHERE jd.state_code = 'GA'
    AND COALESCE(jd.youtube_channel_count, 0) > 0
)
SELECT d.*
FROM d
LEFT JOIN bronze.bronze_events_channels c ON c.channel_id = d.channel_id
WHERE d.channel_id IS NOT NULL
  AND c.channel_id IS NULL
ORDER BY d.jurisdiction_name
LIMIT 150;

\echo ''
\echo '========== 6) jurisdiction with NO details row (exact name match; GA details only) (reason A/E) =========='
SELECT js.id, js.name, js.type, js.county, js.geoid, js.population
FROM jurisdiction js
LEFT JOIN jurisdiction jd
  ON jd.state_code = 'GA'
 AND lower(btrim(jd.name)) = lower(btrim(js.name))
WHERE (
    upper(trim(COALESCE(to_jsonb(js)->>'state_code', ''))) = 'GA'
    OR upper(trim(COALESCE(to_jsonb(js)->>'state', ''))) IN ('GA', 'GEORGIA')
  )
  AND js.type IN ('city', 'county', 'school_district')
  AND jd.jurisdiction_id IS NULL
ORDER BY js.type, js.population DESC NULLS LAST
LIMIT 200;

\echo ''
\echo '========== 7) Bronze: distinct jurisdiction_name (matches your ga/* folder labels) =========='
SELECT
  jurisdiction_name,
  COUNT(DISTINCT channel_id) AS channels,
  COUNT(*) AS videos
FROM bronze.bronze_events_youtube
WHERE state_code = 'GA'
GROUP BY jurisdiction_name
ORDER BY videos DESC, jurisdiction_name;
