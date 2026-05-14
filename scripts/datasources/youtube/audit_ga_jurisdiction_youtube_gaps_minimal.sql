-- =============================================================================
-- GA gap audit (minimal DB): jurisdictions_search + bronze only.
-- Use full audit_ga_jurisdiction_youtube_gaps.sql when jurisdictions_details_search exists.
-- =============================================================================
\pset pager off

\echo '========== 1) SCALE: jurisdictions_search (GA) =========='
SELECT js.type, COUNT(*) AS n
FROM jurisdictions_search js
WHERE (
    upper(trim(COALESCE(to_jsonb(js)->>'state_code', ''))) = 'GA'
    OR upper(trim(COALESCE(to_jsonb(js)->>'state', ''))) IN ('GA', 'GEORGIA')
  )
  AND js.type IN ('city', 'county', 'school_district', 'town', 'village')
GROUP BY js.type
ORDER BY n DESC;

\echo ''
\echo '========== 2) SCALE: bronze_events_youtube (GA) =========='
SELECT
  COUNT(DISTINCT jurisdiction_name) AS distinct_jurisdiction_names,
  COUNT(DISTINCT channel_id) AS distinct_channels,
  COUNT(*) AS video_rows
FROM bronze.bronze_events_youtube
WHERE state_code = 'GA';

\echo ''
\echo '========== 3) Bronze: distinct jurisdiction_name (your ga/* folders) =========='
SELECT
  jurisdiction_name,
  COUNT(DISTINCT channel_id) AS channels,
  COUNT(*) AS videos
FROM bronze.bronze_events_youtube
WHERE state_code = 'GA'
GROUP BY jurisdiction_name
ORDER BY videos DESC, jurisdiction_name;
