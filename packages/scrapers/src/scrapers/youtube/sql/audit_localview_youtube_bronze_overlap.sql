-- =============================================================================
-- LocalView bronze vs YouTube bronze — counts and overlap (same YouTube video_id)
--
-- These tables are different pipelines:
--   bronze.bronze_events_localview — LocalView scrape (datasource_id = YouTube video id when video_url is YT).
--   bronze.bronze_events_youtube   — YouTube API / loader rows (video_id).
--
-- A gap between totals is normal: not every LocalView meeting is re-ingested into
-- bronze_events_youtube, and YouTube bronze may include videos never in LocalView.
--
-- Why overlap row-count can be ~1%: LocalView is a wide catalog (many meetings / many
-- places). bronze_events_youtube only has rows you actually pulled via the YouTube loader
-- for configured channels. Fix = ingest more videos (same video_id) into bronze_events_youtube,
-- or accept overlap as a coverage metric until bulk backfill exists.
--
-- Requires: psql -v one_state=GA
-- =============================================================================

\pset pager off

\echo '========== Totals (optionally filter LocalView to one state) =========='

SELECT
    (SELECT COUNT(*)::bigint FROM bronze.bronze_events_youtube) AS n_youtube_all_states,
    (SELECT COUNT(*)::bigint FROM bronze.bronze_events_youtube y WHERE y.state_code = trim(upper(:'one_state'))) AS n_youtube_this_state,
    (SELECT COUNT(*)::bigint FROM bronze.bronze_events_localview) AS n_localview_all,
    (SELECT COUNT(*)::bigint
     FROM bronze.bronze_events_localview lv
     WHERE lv.datasource = 'localview'
       AND lv.state_code = trim(upper(:'one_state'))) AS n_localview_this_state;

\echo ''
\echo '========== Distinct YouTube video ids (explains overlap ceiling) =========='

SELECT
    trim(upper(:'one_state')) AS state_code,
    (
        SELECT COUNT(DISTINCT BTRIM(lv.datasource_id))
        FROM bronze.bronze_events_localview lv
        WHERE lv.datasource = 'localview'
          AND lv.state_code = trim(upper(:'one_state'))
          AND BTRIM(COALESCE(lv.datasource_id, '')) <> ''
    )::bigint AS distinct_lv_datasource_ids,
    (
        SELECT COUNT(DISTINCT BTRIM(y.video_id))
        FROM bronze.bronze_events_youtube y
        WHERE y.state_code = trim(upper(:'one_state'))
          AND BTRIM(COALESCE(y.video_id, '')) <> ''
    )::bigint AS distinct_yt_video_ids,
    (
        SELECT COUNT(DISTINCT BTRIM(lv.datasource_id))
        FROM bronze.bronze_events_localview lv
        WHERE lv.datasource = 'localview'
          AND lv.state_code = trim(upper(:'one_state'))
          AND BTRIM(COALESCE(lv.datasource_id, '')) <> ''
          AND EXISTS (
              SELECT 1
              FROM bronze.bronze_events_youtube y
              WHERE BTRIM(y.video_id) = BTRIM(lv.datasource_id)
          )
    )::bigint AS distinct_ids_in_both_tables;

\echo ''
\echo '========== Overlap: LocalView rows (BTRIM join on video id) =========='

SELECT
    trim(upper(:'one_state')) AS state_code,
    COUNT(*)::bigint AS localview_rows_this_state,
    COUNT(*) FILTER (WHERE y.video_id IS NOT NULL)::bigint AS lv_rows_with_matching_youtube_row,
    COUNT(*) FILTER (WHERE y.video_id IS NULL)::bigint AS lv_rows_no_youtube_row
FROM bronze.bronze_events_localview lv
LEFT JOIN bronze.bronze_events_youtube y ON BTRIM(y.video_id) = BTRIM(lv.datasource_id)
WHERE lv.datasource = 'localview'
  AND lv.state_code = trim(upper(:'one_state'));

\echo ''
\echo '========== Reverse: YouTube rows in state with no LocalView row on same video_id =========='

SELECT
    COUNT(*)::bigint AS youtube_rows_state,
    COUNT(*) FILTER (WHERE lv.datasource_id IS NULL)::bigint AS yt_no_localview_match
FROM bronze.bronze_events_youtube y
LEFT JOIN bronze.bronze_events_localview lv
    ON BTRIM(lv.datasource_id) = BTRIM(y.video_id) AND lv.datasource = 'localview'
WHERE y.state_code = trim(upper(:'one_state'));

\echo ''
\echo '========== LocalView rows: video_url has watch?v= but id not in bronze_events_youtube (sample) =========='

SELECT
    BTRIM(lv.datasource_id) AS datasource_id,
    LEFT(lv.video_url, 80) AS video_url_prefix,
    COUNT(*)::bigint AS n_lv_rows
FROM bronze.bronze_events_localview lv
WHERE lv.datasource = 'localview'
  AND lv.state_code = trim(upper(:'one_state'))
  AND lv.video_url IS NOT NULL
  AND lv.video_url ILIKE '%watch?v=%'
  AND NOT EXISTS (
      SELECT 1
      FROM bronze.bronze_events_youtube y
      WHERE BTRIM(y.video_id) = BTRIM(lv.datasource_id)
  )
GROUP BY BTRIM(lv.datasource_id), LEFT(lv.video_url, 80)
ORDER BY n_lv_rows DESC, datasource_id
LIMIT 15;

\echo ''
\echo '========== Downloader stack (GA): run audit_ga_youtube_download_filters.sql for exclusion_tags =========='
