-- =============================================================================
-- GA YouTube rows vs download_audio_to_drive.py filter stack
-- (0) Funnel: total GA bronze rows vs would_download_now (see why ~99% look "dropped")
-- Mirrors: --states GA --bronze-channels-only --government-channel-types-only
--          --meetings-only --exclude-news --years-back 5 --not-yet-downloaded
-- (skip_flagged_channels = true when bronze + gov flags are on)
--
-- Usage (recommended — loads .env and picks DB URL like other repo scripts):
--   ./packages/scrapers/src/scrapers/youtube/run_audit_ga_youtube_download_filters.sh
--
-- Manual (must pass a full Postgres URL; empty DATABASE_URL makes psql use OS user on local socket):
--   psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f packages/scrapers/src/scrapers/youtube/audit_ga_youtube_download_filters.sql
--
-- Change state / years / allow_null_upload_date in params CTE below (last mirrors
--   download_audio_to_drive.py --allow-null-upload-date with --years-back).
-- =============================================================================

DROP TABLE IF EXISTS _yt_audit_f;
CREATE TEMP TABLE _yt_audit_f AS
WITH params AS (
  SELECT
    'GA'::text AS state_code,
    5::int AS years_back,
    false::boolean AS allow_null_upload_date
),
base AS (
  SELECT
    y.id,
    y.video_id,
    y.title,
    y.meeting_type,
    y.jurisdiction_name,
    y.state_code,
    y.channel_id,
    y.channel_type AS y_channel_type,
    y.video_url,
    y.event_date,
    y.published_at,
    (y.event_date IS NULL AND y.published_at IS NULL) AS both_dates_missing,
    y.audio_downloaded_at,
    c.channel_id AS joined_channel_id,
    c.channel_title AS c_channel_title,
    c.channel_type AS c_channel_type,
    c.flagged_as_junk,
    COALESCE(y.event_date, (y.published_at AT TIME ZONE 'UTC')::date) AS effective_date
  FROM bronze.bronze_event_youtube y
  CROSS JOIN params p
  LEFT JOIN bronze.bronze_events_channels c ON c.channel_id = y.channel_id
  WHERE y.state_code = p.state_code
    AND y.video_url IS NOT NULL
),
f AS (
  SELECT
    b.*,
    (b.joined_channel_id IS NULL) AS miss_bronze_channel_row,
    (b.flagged_as_junk IS TRUE) AS is_flagged_junk,
    (COALESCE(b.c_channel_type, b.y_channel_type, '') NOT IN ('municipal', 'county', 'state', 'school'))
      AS not_government_channel_type,
    NOT (
      NULLIF(BTRIM(COALESCE(b.meeting_type, '')), '') IS NOT NULL
      OR b.title ILIKE '%council%'
      OR b.title ILIKE '%commission%'
      OR b.title ILIKE '%committee%'
      OR b.title ILIKE '%board of%'
      OR b.title ILIKE '%school board%'
      OR b.title ILIKE '%trustees%'
      OR b.title ILIKE '%supervisors%'
      OR b.title ILIKE '%town hall%'
      OR b.title ILIKE '%public hearing%'
      OR b.title ILIKE '%hearing%'
      OR b.title ILIKE '%work session%'
      OR b.title ILIKE '%workshop%'
      OR b.title ILIKE '%planning and zoning%'
      OR b.title ILIKE '%zoning board%'
      OR b.title ILIKE '%board meeting%'
      OR b.title ILIKE '%town meeting%'
      OR b.title ILIKE '%city council%'
      OR b.title ILIKE '%county board%'
      OR b.title ILIKE '%selectboard%'
      OR b.title ILIKE '%select board%'
      OR b.title ILIKE '%agenda%'
      OR b.title ILIKE '%gavel%'
      OR b.title ILIKE '%minutes%'
    ) AS fails_meetings_heuristic,
    (
      b.title ILIKE '%breaking news%'
      OR b.title ILIKE '%top stories%'
      OR b.title ILIKE '%morning news%'
      OR b.title ILIKE '%evening news%'
      OR b.title ILIKE '%nightcast%'
      OR b.title ILIKE '%weather %'
      OR b.title ILIKE '%sports center%'
    ) AS matches_news_title,
    (
      COALESCE(b.c_channel_title, '') ILIKE '%WAVY%'
      OR COALESCE(b.c_channel_title, '') ILIKE '% CNN%'
      OR COALESCE(b.c_channel_title, '') ILIKE 'CNN %'
      OR COALESCE(b.c_channel_title, '') ILIKE '%Fox News%'
      OR COALESCE(b.c_channel_title, '') ILIKE '%MSNBC%'
      OR COALESCE(b.c_channel_title, '') ILIKE '%NBC %'
      OR COALESCE(b.c_channel_title, '') ILIKE '%ABC News%'
      OR COALESCE(b.c_channel_title, '') ILIKE '%CBS News%'
      OR COALESCE(b.c_channel_title, '') ILIKE '% Nexstar%'
    ) AS matches_news_channel,
    (b.effective_date IS NULL) AS missing_effective_date,
    (
      NOT b.both_dates_missing
      AND NOT (
        b.effective_date >= (CURRENT_DATE - make_interval(years => (SELECT years_back FROM params)))
      )
    ) AS outside_years_back,
    (b.audio_downloaded_at IS NOT NULL) AS already_downloaded,
    (
      b.joined_channel_id IS NOT NULL
      AND NOT COALESCE(b.flagged_as_junk, FALSE)
      AND COALESCE(b.c_channel_type, b.y_channel_type, '') IN ('municipal', 'county', 'state', 'school')
      AND (
        NULLIF(BTRIM(COALESCE(b.meeting_type, '')), '') IS NOT NULL
        OR b.title ILIKE '%council%'
        OR b.title ILIKE '%commission%'
        OR b.title ILIKE '%committee%'
        OR b.title ILIKE '%board of%'
        OR b.title ILIKE '%school board%'
        OR b.title ILIKE '%trustees%'
        OR b.title ILIKE '%supervisors%'
        OR b.title ILIKE '%town hall%'
        OR b.title ILIKE '%public hearing%'
        OR b.title ILIKE '%hearing%'
        OR b.title ILIKE '%work session%'
        OR b.title ILIKE '%workshop%'
        OR b.title ILIKE '%planning and zoning%'
        OR b.title ILIKE '%zoning board%'
        OR b.title ILIKE '%board meeting%'
        OR b.title ILIKE '%town meeting%'
        OR b.title ILIKE '%city council%'
        OR b.title ILIKE '%county board%'
        OR b.title ILIKE '%selectboard%'
        OR b.title ILIKE '%select board%'
        OR b.title ILIKE '%agenda%'
        OR b.title ILIKE '%gavel%'
        OR b.title ILIKE '%minutes%'
      )
      AND NOT (
        b.title ILIKE '%breaking news%'
        OR b.title ILIKE '%top stories%'
        OR b.title ILIKE '%morning news%'
        OR b.title ILIKE '%evening news%'
        OR b.title ILIKE '%nightcast%'
        OR b.title ILIKE '%weather %'
        OR b.title ILIKE '%sports center%'
      )
      AND NOT (
        COALESCE(b.c_channel_title, '') ILIKE '%WAVY%'
        OR COALESCE(b.c_channel_title, '') ILIKE '% CNN%'
        OR COALESCE(b.c_channel_title, '') ILIKE 'CNN %'
        OR COALESCE(b.c_channel_title, '') ILIKE '%Fox News%'
        OR COALESCE(b.c_channel_title, '') ILIKE '%MSNBC%'
        OR COALESCE(b.c_channel_title, '') ILIKE '%NBC %'
        OR COALESCE(b.c_channel_title, '') ILIKE '%ABC News%'
        OR COALESCE(b.c_channel_title, '') ILIKE '%CBS News%'
        OR COALESCE(b.c_channel_title, '') ILIKE '% Nexstar%'
      )
      AND (
        (b.effective_date IS NOT NULL AND b.effective_date >= (CURRENT_DATE - make_interval(years => (SELECT years_back FROM params))))
        OR (
          (SELECT allow_null_upload_date FROM params)
          AND b.both_dates_missing
        )
      )
      AND b.audio_downloaded_at IS NULL
    ) AS would_download_now
  FROM base b
)
SELECT
  f.*,
  ARRAY_REMOVE(
    ARRAY[
      CASE WHEN f.miss_bronze_channel_row THEN 'no_row_in_bronze_events_channels' END,
      CASE WHEN f.is_flagged_junk THEN 'flagged_as_junk' END,
      CASE WHEN f.not_government_channel_type THEN 'channel_type_not_municipal_county_state_school' END,
      CASE WHEN f.fails_meetings_heuristic THEN 'fails_meetings_title_heuristic' END,
      CASE WHEN f.matches_news_title THEN 'matches_news_title_pattern' END,
      CASE WHEN f.matches_news_channel THEN 'matches_news_channel_pattern' END,
      CASE WHEN f.missing_effective_date THEN 'no_event_date_and_no_published_date' END,
      CASE WHEN f.outside_years_back THEN 'outside_years_back_window' END,
      CASE WHEN f.already_downloaded THEN 'already_downloaded' END
    ],
    NULL
  ) AS exclusion_tags
FROM f;

-- (0) "99% dropped" is usually not DELETEs from bronze: rows remain; the downloader stack
--     applies meetings/years/channel/news filters so few rows match would_download_now.
--     Rows with NULL event_date AND NULL published_at get would_download_now = NULL unless
--     params.allow_null_upload_date is true (mirrors download_audio_to_drive --allow-null-upload-date).
\echo '========== (0) Downloader funnel (same flags as default GA audit stack) =========='

SELECT
    COUNT(*)::bigint AS n_ga_rows_with_video_url,
    COUNT(*) FILTER (WHERE would_download_now)::bigint AS n_eligible_download_now,
    ROUND(100.0 * COUNT(*) FILTER (WHERE would_download_now) / NULLIF(COUNT(*), 0), 2) AS pct_eligible,
    COUNT(*) FILTER (WHERE both_dates_missing)::bigint AS n_both_event_and_published_at_null
FROM _yt_audit_f;

\echo ''
\echo 'Primary reason (first failing gate; eligible bucket first; avoids SQL NOT NULL tri-state):'

SELECT
    x.primary_reason,
    COUNT(*)::bigint AS n_videos
FROM (
    SELECT
        CASE
            WHEN would_download_now IS TRUE THEN '0_eligible'
            WHEN miss_bronze_channel_row THEN '1_no_bronze_events_channels_row'
            WHEN is_flagged_junk THEN '2_flagged_as_junk'
            WHEN not_government_channel_type THEN '3_channel_type_not_municipal_county_state_school'
            WHEN already_downloaded THEN '9_already_downloaded'
            WHEN missing_effective_date THEN '7_missing_effective_date'
            WHEN outside_years_back THEN '8_outside_years_back_window'
            WHEN fails_meetings_heuristic THEN '4_fails_meetings_title_heuristic'
            WHEN matches_news_title THEN '5_news_title_pattern'
            WHEN matches_news_channel THEN '6_news_channel_pattern'
            ELSE '99_other'
        END AS primary_reason
    FROM _yt_audit_f
) x
GROUP BY x.primary_reason
ORDER BY x.primary_reason;

-- (A) Sample excluded rows (alias exclusion_tags is a real column on temp table)
SELECT
  video_id,
  LEFT(title, 100) AS title,
  jurisdiction_name,
  channel_id,
  c_channel_title,
  COALESCE(c_channel_type, y_channel_type, '') AS resolved_channel_type,
  effective_date,
  audio_downloaded_at,
  exclusion_tags
FROM _yt_audit_f
WHERE NOT would_download_now
ORDER BY
  miss_bronze_channel_row DESC,
  not_government_channel_type DESC,
  fails_meetings_heuristic DESC,
  cardinality(exclusion_tags) DESC,
  jurisdiction_name NULLS LAST,
  effective_date DESC NULLS LAST
LIMIT 500;

-- (B) Count rows per exclusion tag (one video can hit several tags)
SELECT tag, COUNT(*) AS video_rows
FROM _yt_audit_f
CROSS JOIN LATERAL unnest(
  ARRAY[
    CASE WHEN miss_bronze_channel_row THEN 'no_row_in_bronze_events_channels' END,
    CASE WHEN is_flagged_junk THEN 'flagged_as_junk' END,
    CASE WHEN not_government_channel_type THEN 'channel_type_not_government' END,
    CASE WHEN fails_meetings_heuristic THEN 'fails_meetings_heuristic' END,
    CASE WHEN matches_news_title THEN 'news_title' END,
    CASE WHEN matches_news_channel THEN 'news_channel' END,
    CASE WHEN missing_effective_date THEN 'missing_effective_date' END,
    CASE WHEN outside_years_back THEN 'outside_years_back' END,
    CASE WHEN already_downloaded THEN 'already_downloaded' END
  ]
) AS t(tag)
WHERE NOT would_download_now
  AND tag IS NOT NULL
GROUP BY tag
ORDER BY video_rows DESC;

-- (C) GA channels with YouTube rows but zero eligible downloads right now
SELECT
  channel_id,
  MAX(c_channel_title) AS channel_title,
  MAX(jurisdiction_name) AS jurisdiction_name,
  MAX(COALESCE(c_channel_type, y_channel_type, '')) AS resolved_channel_type,
  COUNT(*) FILTER (WHERE would_download_now) AS eligible_videos,
  COUNT(*) AS total_ga_videos
FROM _yt_audit_f
GROUP BY channel_id
HAVING COUNT(*) FILTER (WHERE would_download_now) = 0
ORDER BY total_ga_videos DESC, MAX(jurisdiction_name) NULLS LAST
LIMIT 300;
