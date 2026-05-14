-- Rows in bronze_events_youtube missing both calendar event_date and published_at.
-- Dates normally come from YouTube (Data API publishedAt or yt-dlp upload_date / timestamp).
-- Pure SQL cannot call YouTube; use backfill_bronze_youtube_publish_dates.py or re-run
-- load_youtube_events_to_postgres.py after fixing ON CONFLICT to merge dates.
--
-- psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/datasources/youtube/sql/preview_bronze_youtube_blank_publish_dates.sql

\pset pager off

SELECT
    COUNT(*)::bigint AS n_rows_both_dates_blank
FROM bronze.bronze_events_youtube y
WHERE y.video_url IS NOT NULL
  AND y.event_date IS NULL
  AND y.published_at IS NULL;

SELECT
    y.state_code,
    COUNT(*)::bigint AS n_blank
FROM bronze.bronze_events_youtube y
WHERE y.video_url IS NOT NULL
  AND y.event_date IS NULL
  AND y.published_at IS NULL
GROUP BY y.state_code
ORDER BY n_blank DESC NULLS LAST, y.state_code
LIMIT 30;

SELECT y.video_id, y.state_code, y.jurisdiction_name, LEFT(y.title, 72) AS title_prefix
FROM bronze.bronze_events_youtube y
WHERE y.video_url IS NOT NULL
  AND y.event_date IS NULL
  AND y.published_at IS NULL
ORDER BY y.state_code NULLS LAST, y.jurisdiction_name NULLS LAST, y.video_id
LIMIT 40;
