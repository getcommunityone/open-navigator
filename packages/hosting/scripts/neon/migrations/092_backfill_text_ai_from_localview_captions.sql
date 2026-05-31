-- Migration 092: promote existing LocalView captions into bronze_events_text_ai
-- Date: 2026-05-31
-- Target: DEV warehouse (localhost:5433 / NEON_DATABASE_URL_DEV)
--
-- WHY
-- ---
-- The YouTube transcript backfill (scrapers.youtube.backfill_transcripts) picks
-- work from intermediate.int_events_union anti-joined to bronze_events_text_ai on
-- video_id (`t.id IS NULL` = "no transcript landed yet"). LocalView meetings are
-- in int_events_union (video_id = datasource_id), but only ~2.4k of them have a
-- text_ai row -- so ~100k+ LocalView videos whose captions ALREADY sit in
-- bronze_events_localview.caption_text(_clean) fall through that anti-join and get
-- re-downloaded from YouTube on every run. This lands those captions directly so
-- the downloader skips them, and so they flow through stg_bronze_events_text_ai ->
-- events_text_search like any other transcript. Tagged transcript_source =
-- 'localview' for provenance.
--
-- FORMAT (why we DON'T build the segments JSONB here)
-- ---------------------------------------------------
-- caption_text is plain text with inline second-resolution markers, NOT WebVTT:
--   "{00:00:01} pledge of allegiance {00:00:05} to the flag ..."
-- An earlier version of this migration parsed those markers into the
-- [{text,start,duration}] segments JSONB the YouTube path writes. At ~1,194
-- markers/transcript x ~153k transcripts that regexp_matches(... 'g') WITH
-- ORDINALITY explodes to ~183M cue rows, and the jsonb_agg(... ORDER BY ord)
-- spilled hundreds of GB to temp (work_mem=4MB) -- 40+ min and still going.
-- Not worth it. Instead we keep the inline-timer caption VERBATIM in a new
-- caption_text_timed column and leave segments NULL; the analyze step parses
-- either shape (YouTube segments JSONB or this inline-timer text). raw_text is the
-- marker-free plain text for search.
--
-- SAFETY
-- ------
-- ON CONFLICT (video_id) DO NOTHING: never clobbers an existing YouTube/Gemini
-- transcript (the ~2.4k already present stay untouched, segments intact). Fully
-- idempotent. Set-based, no cue explosion -- runs in seconds.

-- New column: the original LocalView inline-timer caption, stored as-is.
ALTER TABLE bronze.bronze_events_text_ai
    ADD COLUMN IF NOT EXISTS caption_text_timed text;

COMMENT ON COLUMN bronze.bronze_events_text_ai.caption_text_timed IS
    'LocalView-style inline-timer caption text ("{HH:MM:SS} words ..."), stored verbatim as a lightweight alternative to the segments JSONB. The analyze step handles both shapes.';

INSERT INTO bronze.bronze_events_text_ai
    (event_id, video_id, raw_text, caption_text_timed, segments, language,
     is_auto_generated, transcript_source, has_transcript, transcript_quality)
WITH lv AS (
    SELECT
        datasource_id AS video_id,
        caption_text,
        caption_text_clean
    FROM bronze.bronze_events_localview
    WHERE datasource_id IS NOT NULL
      AND btrim(datasource_id) <> ''
      AND COALESCE(caption_text, '') NOT IN ('', '<No caption available>')
)
SELECT
    u.event_id,                          -- canonical event_id from the mart (NULL if unmatched)
    lv.video_id,
    -- marker-free plain text for search
    NULLIF(
        btrim(regexp_replace(
            regexp_replace(lv.caption_text_clean, '\{\d{2}:\d{2}:\d{2}\}', '', 'g'),
            '\s+', ' ', 'g'
        )),
        ''
    )           AS raw_text,
    lv.caption_text  AS caption_text_timed,  -- VERBATIM inline-timer format ({HH:MM:SS} ...)
    NULL::jsonb      AS segments,            -- intentionally skipped; analyze reads caption_text_timed
    'en'        AS language,
    TRUE        AS is_auto_generated,     -- LocalView captions are YouTube auto-captions
    'localview' AS transcript_source,
    TRUE        AS has_transcript,
    'medium'    AS transcript_quality
FROM lv
LEFT JOIN intermediate.int_events_union u  ON u.video_id = lv.video_id
ON CONFLICT (video_id) DO NOTHING;
