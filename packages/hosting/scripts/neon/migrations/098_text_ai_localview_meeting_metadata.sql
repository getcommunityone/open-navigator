-- Migration 098: add LocalView meeting/video metadata columns to
-- bronze_events_text_ai and backfill them from bronze_events_localview.
-- Date: 2026-05-31
-- Target: DEV warehouse (localhost:5433 / NEON_DATABASE_URL_DEV)
--
-- WHY
-- ---
-- Migration 092 landed LocalView CAPTIONS into bronze_events_text_ai (raw_text /
-- caption_text_timed) keyed by video_id (= LocalView datasource_id), but carried
-- none of the meeting/video context that sits next to those captions in
-- bronze_events_localview. The AI text-extraction + downstream search/marts need
-- that context inline on the transcript row (so a consumer of text_ai never has
-- to re-join LocalView): the meeting (event_date, meeting_type, title, place_govt,
-- video_url) and the YouTube video/channel facts (vid_* stats, channel_*).
--
-- This adds those 18 columns and backfills them from LocalView by
-- video_id = datasource_id. channel_id / channel_url do NOT exist on
-- bronze_events_localview, so they are sourced from bronze_events_channels by
-- channel_title (deduped 1-per-title; ~790/970 distinct LocalView channel titles
-- resolve, the rest stay NULL).
--
-- SAFETY
-- ------
-- * ADD COLUMN IF NOT EXISTS + COALESCE-only UPDATE => idempotent and
--   non-clobbering: a value already present on the row (e.g. a YouTube-sourced
--   transcript that also matches a LocalView video) is never overwritten.
-- * The UPDATE never touches video_id, so the BEFORE UPDATE OF video_id geo
--   trigger (sync_text_ai_geo_from_youtube) does not fire.
--
-- PERFORMANCE (why we drop + rebuild the full-text GIN index)
-- ----------------------------------------------------------
-- This UPDATE adds only unindexed columns (raw_text / video_id are untouched),
-- but the table is at fillfactor 100 so the row versions are non-HOT. A non-HOT
-- update re-inserts EVERY index entry for the row -- including the row's whole
-- transcript tsvector into idx_bronze_events_text_search_gin. At ~110k rows of
-- full-transcript tsvectors that incremental GIN maintenance is hundreds of
-- millions of entry inserts and runs for ~an hour (CPU-bound, "word is too long
-- to be indexed" notices). Since the GIN content does not actually change, we
-- DROP it, run the backfill (now just heap + cheap btree maintenance), then bulk
-- CREATE INDEX -- the sorted bulk GIN build is dramatically faster than per-row
-- inserts. Full-text search on this table is briefly unavailable during the
-- rebuild (acceptable for a deploy-time migration).
-- * The sentinel WHERE guard (title/event_date/video_url all NULL) makes the
--   backfill a near-no-op on idempotent re-runs.

-- ---------------------------------------------------------------------------
-- Columns (types mirror bronze_events_localview; channel_id/url mirror
-- bronze_events_channels)
-- ---------------------------------------------------------------------------
ALTER TABLE bronze.bronze_events_text_ai
    ADD COLUMN IF NOT EXISTS event_date       date,
    ADD COLUMN IF NOT EXISTS meeting_type     varchar(255),
    ADD COLUMN IF NOT EXISTS title            varchar(500),
    ADD COLUMN IF NOT EXISTS video_url        text,
    ADD COLUMN IF NOT EXISTS place_govt       varchar(255),
    ADD COLUMN IF NOT EXISTS channel_title    varchar(500),
    ADD COLUMN IF NOT EXISTS vid_title        varchar(500),
    ADD COLUMN IF NOT EXISTS vid_desc         text,
    ADD COLUMN IF NOT EXISTS vid_length_min   double precision,
    ADD COLUMN IF NOT EXISTS vid_upload_date  timestamp,
    ADD COLUMN IF NOT EXISTS vid_livestreamed boolean,
    ADD COLUMN IF NOT EXISTS vid_views        double precision,
    ADD COLUMN IF NOT EXISTS vid_likes        double precision,
    ADD COLUMN IF NOT EXISTS vid_dislikes     double precision,
    ADD COLUMN IF NOT EXISTS vid_comments     double precision,
    ADD COLUMN IF NOT EXISTS channel_type     varchar(100),
    ADD COLUMN IF NOT EXISTS channel_id       varchar(64),
    ADD COLUMN IF NOT EXISTS channel_url      text;

-- ---------------------------------------------------------------------------
-- Backfill from LocalView (video_id = datasource_id); channel_id/url from the
-- channel registry by channel_title.
--
-- Drop the full-text GIN index first so the bulk UPDATE does not pay per-row
-- incremental GIN maintenance (see PERFORMANCE note above); rebuilt below.
-- ---------------------------------------------------------------------------
DROP INDEX IF EXISTS bronze.idx_bronze_events_text_search_gin;

WITH ch AS (
    -- one channel_id/url per title (12 titles are duplicated in the registry):
    -- prefer verified, then the most-populated / most-recently-updated row.
    SELECT DISTINCT ON (channel_title)
        channel_title,
        channel_id,
        channel_url
    FROM bronze.bronze_events_channels
    WHERE channel_title IS NOT NULL
      AND btrim(channel_title) <> ''
    ORDER BY channel_title,
             is_verified DESC NULLS LAST,
             video_count DESC NULLS LAST,
             last_updated DESC NULLS LAST
)
UPDATE bronze.bronze_events_text_ai t
SET event_date       = COALESCE(t.event_date,       lv.event_date),
    meeting_type     = COALESCE(t.meeting_type,     lv.meeting_type),
    title            = COALESCE(t.title,            lv.title),
    video_url        = COALESCE(t.video_url,        lv.video_url),
    place_govt       = COALESCE(t.place_govt,       lv.place_govt),
    channel_title    = COALESCE(t.channel_title,    lv.channel_title),
    vid_title        = COALESCE(t.vid_title,        lv.vid_title),
    vid_desc         = COALESCE(t.vid_desc,         lv.vid_desc),
    vid_length_min   = COALESCE(t.vid_length_min,   lv.vid_length_min),
    vid_upload_date  = COALESCE(t.vid_upload_date,  lv.vid_upload_date),
    vid_livestreamed = COALESCE(t.vid_livestreamed, lv.vid_livestreamed),
    vid_views        = COALESCE(t.vid_views,        lv.vid_views),
    vid_likes        = COALESCE(t.vid_likes,        lv.vid_likes),
    vid_dislikes     = COALESCE(t.vid_dislikes,     lv.vid_dislikes),
    vid_comments     = COALESCE(t.vid_comments,     lv.vid_comments),
    channel_type     = COALESCE(t.channel_type,     lv.channel_type),
    channel_id       = COALESCE(t.channel_id,       ch.channel_id),
    channel_url      = COALESCE(t.channel_url,      ch.channel_url),
    last_updated     = CURRENT_TIMESTAMP
FROM bronze.bronze_events_localview lv
LEFT JOIN ch ON ch.channel_title = lv.channel_title
WHERE lv.datasource_id IS NOT NULL
  AND lv.datasource_id = t.video_id
  -- sentinel: only rows with no LocalView meeting context yet (keeps an
  -- idempotent re-run a near-no-op instead of rewriting every matched row).
  AND t.title IS NULL
  AND t.event_date IS NULL
  AND t.video_url IS NULL;

-- ---------------------------------------------------------------------------
-- Rebuild the full-text GIN index (fast sorted bulk build).
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_bronze_events_text_search_gin
    ON bronze.bronze_events_text_ai USING GIN (to_tsvector('english', COALESCE(raw_text, '')));

-- ---------------------------------------------------------------------------
-- Column documentation
-- ---------------------------------------------------------------------------
COMMENT ON COLUMN bronze.bronze_events_text_ai.event_date       IS 'Meeting date (from bronze_events_localview.event_date).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.meeting_type     IS 'Meeting type/body (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.title            IS 'Meeting title (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.video_url        IS 'Source video URL (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.place_govt       IS 'Governing place name (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.channel_title    IS 'YouTube channel title (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.vid_title        IS 'YouTube video title (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.vid_desc         IS 'YouTube video description (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.vid_length_min   IS 'Video length in minutes (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.vid_upload_date  IS 'Video upload timestamp (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.vid_livestreamed IS 'Whether the video was livestreamed (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.vid_views        IS 'Video view count (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.vid_likes        IS 'Video like count (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.vid_dislikes     IS 'Video dislike count (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.vid_comments     IS 'Video comment count (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.channel_type     IS 'Channel type/classification (from LocalView).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.channel_id       IS 'YouTube channel id (from bronze_events_channels by channel_title).';
COMMENT ON COLUMN bronze.bronze_events_text_ai.channel_url      IS 'YouTube channel URL (from bronze_events_channels by channel_title).';
