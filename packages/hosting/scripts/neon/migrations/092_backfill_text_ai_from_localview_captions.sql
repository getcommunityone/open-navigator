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
-- text_ai row -- so ~150k LocalView videos whose captions ALREADY sit in
-- bronze_events_localview.caption_text(_clean) fall through that anti-join and get
-- re-downloaded from YouTube on every run. This lands those captions directly so
-- the downloader skips them, and so they flow through stg_bronze_events_text_ai ->
-- events_text_search like any other transcript. Tagged transcript_source =
-- 'localview' for provenance.
--
-- FORMAT
-- ------
-- caption_text is plain text with inline second-resolution markers, NOT WebVTT:
--   "{00:00:01} pledge of allegiance {00:00:05} to the flag ..."
-- The sentinel "<No caption available>" means no captions -> excluded.
-- segments are derived from the {HH:MM:SS} markers (start-only; duration = next
-- marker's start - this marker's start), matching the [{text,start,duration}]
-- shape the YouTube path writes. raw_text uses caption_text_clean with any stray
-- {HH:MM:SS} markers stripped defensively (no-op if clean is already marker-free).
--
-- SAFETY
-- ------
-- ON CONFLICT (video_id) DO NOTHING: never clobbers an existing YouTube/Gemini
-- transcript (the ~2.4k already present stay untouched). Fully idempotent --
-- re-running is a no-op. Heavy one-shot regex pass over ~150k rows; expect it to
-- take a couple of minutes.

INSERT INTO bronze.bronze_events_text_ai
    (event_id, video_id, raw_text, segments, language,
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
),
cues AS (
    SELECT
        lv.video_id,
        m.ord,
        (m.cap[1]::int * 3600 + m.cap[2]::int * 60 + m.cap[3]::int)::numeric AS start_s,
        btrim(regexp_replace(m.cap[4], '\s+', ' ', 'g')) AS seg_text
    FROM lv,
    LATERAL regexp_matches(
        lv.caption_text,
        '\{(\d{2}):(\d{2}):(\d{2})\}\s*([^{]*)',
        'g'
    ) WITH ORDINALITY AS m(cap, ord)
),
-- duration must be computed in its own pass: a window function (lead) cannot be
-- nested inside an aggregate (jsonb_agg) in the same SELECT.
cues_dur AS (
    SELECT
        video_id,
        ord,
        start_s,
        seg_text,
        lead(start_s) OVER (PARTITION BY video_id ORDER BY ord) - start_s AS duration
    FROM cues
),
seg AS (
    SELECT
        video_id,
        jsonb_agg(
            jsonb_build_object(
                'text', seg_text,
                'start', start_s,
                'duration', duration
            ) ORDER BY ord
        ) FILTER (WHERE seg_text <> '') AS segments
    FROM cues_dur
    GROUP BY video_id
)
SELECT
    u.event_id,                          -- canonical event_id from the mart (NULL if unmatched)
    lv.video_id,
    NULLIF(
        btrim(regexp_replace(
            regexp_replace(lv.caption_text_clean, '\{\d{2}:\d{2}:\d{2}\}', '', 'g'),
            '\s+', ' ', 'g'
        )),
        ''
    ) AS raw_text,
    seg.segments,
    'en'        AS language,
    TRUE        AS is_auto_generated,     -- LocalView captions are YouTube auto-captions
    'localview' AS transcript_source,
    TRUE        AS has_transcript,
    'medium'    AS transcript_quality
FROM lv
LEFT JOIN seg                              ON seg.video_id = lv.video_id
LEFT JOIN intermediate.int_events_union u  ON u.video_id   = lv.video_id
ON CONFLICT (video_id) DO NOTHING;
