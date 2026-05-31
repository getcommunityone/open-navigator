-- Migration 087: Backfill geo on bronze.bronze_events_text_ai and stop the
-- sync trigger from clobbering caller-supplied geo for non-YouTube videos.
--
-- Background: bronze.bronze_events_text_ai already carries state_code, state,
-- jurisdiction_id, jurisdiction_name (added in earlier migrations), populated by
-- the BEFORE INSERT/UPDATE trigger sync_text_ai_geo_from_youtube(). That trigger
-- looks the geo up in bronze.bronze_events_youtube by video_id — but LocalView /
-- event-mart videos have NO youtube row, so:
--   1. their geo was left NULL, and
--   2. the trigger's `SELECT ... INTO NEW.*` actively OVERWROTE any caller-
--      supplied geo with NULL (no match → NULLs), so the transcript backfill
--      could never persist geo for those rows.
--
-- Fix (two parts):
--   A. Rewrite the trigger to only apply the YouTube-catalog geo when a matching
--      youtube row is FOUND, and to COALESCE rather than clobber — the YouTube
--      catalog stays canonical for youtube videos, but caller-supplied geo (now
--      written by scrapers.youtube.backfill_transcripts from the event mart)
--      survives for LocalView-only videos.
--   B. One-time backfill of the rows still NULL, from the public.event mart by
--      event_id (guarded so it is a no-op on a fresh DB before dbt has built the
--      mart). All currently-NULL rows resolve fully there.
--
-- After applying: rebuild dbt models that read bronze_events_text_ai
-- (stg_bronze_events_text_ai, events_text_search, int_events_union).

-- ---------------------------------------------------------------------------
-- Part A: non-clobbering geo sync trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bronze.sync_text_ai_geo_from_youtube()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    y_state_code        text;
    y_state             text;
    y_jurisdiction_id   text;
    y_jurisdiction_name text;
BEGIN
    IF NEW.video_id IS NOT NULL THEN
        SELECT y.state_code, y.state, y.jurisdiction_id, y.jurisdiction_name
          INTO y_state_code, y_state, y_jurisdiction_id, y_jurisdiction_name
        FROM bronze.bronze_events_youtube y
        WHERE y.video_id = NEW.video_id
        ORDER BY y.last_updated DESC NULLS LAST
        LIMIT 1;

        IF FOUND THEN
            -- YouTube catalog is canonical when present, but never replace a
            -- caller-supplied value with a NULL coming from the catalog.
            NEW.state_code        := COALESCE(y_state_code, NEW.state_code);
            NEW.state             := COALESCE(y_state, NEW.state);
            NEW.jurisdiction_id   := COALESCE(y_jurisdiction_id, NEW.jurisdiction_id);
            NEW.jurisdiction_name := COALESCE(y_jurisdiction_name, NEW.jurisdiction_name);
        END IF;
        -- No youtube row (e.g. LocalView): keep whatever the caller supplied.
    END IF;
    RETURN NEW;
END;
$function$;

-- ---------------------------------------------------------------------------
-- Part B: one-time backfill of rows still missing geo, from the event mart
-- ---------------------------------------------------------------------------
DO $backfill$
DECLARE
    n bigint;
BEGIN
    IF to_regclass('public.event') IS NULL THEN
        RAISE NOTICE 'public.event mart not present — skipping text_ai geo backfill (run dbt, then re-run this migration).';
        RETURN;
    END IF;

    UPDATE bronze.bronze_events_text_ai t
    SET state_code        = COALESCE(t.state_code, e.state_code),
        state             = COALESCE(t.state, e.state),
        jurisdiction_id   = COALESCE(t.jurisdiction_id, e.jurisdiction_id),
        jurisdiction_name = COALESCE(t.jurisdiction_name, e.jurisdiction_name)
    FROM public.event e
    WHERE e.event_id = t.event_id
      AND (
            t.state_code IS NULL
         OR t.state IS NULL
         OR t.jurisdiction_id IS NULL
         OR t.jurisdiction_name IS NULL
      );

    GET DIAGNOSTICS n = ROW_COUNT;
    RAISE NOTICE 'text_ai geo backfill: updated % row(s) from public.event', n;
END;
$backfill$;
