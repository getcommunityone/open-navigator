-- Migration 113: default bronze.bronze_event_youtube.loaded_at to now()
--
-- Neither YouTube loader (scrapers.youtube.load_youtube_events_to_postgres,
-- ingestion.youtube.events) set loaded_at, and the column had no default, so new
-- rows got NULL: on 2026-11-16, 159,724 of 213,906 rows had no loaded_at, and its
-- newest value was 2026-06-07 while 8,494 rows were written in two days. Both
-- loaders now set it on insert; this default covers any other writer.
--
-- Existing NULLs are left NULL: their first-load time is unknown, and last_updated
-- is a later time, not the load time. Freshness checks use last_updated.
--
-- Idempotent. Undo: ALTER TABLE bronze.bronze_event_youtube ALTER COLUMN loaded_at DROP DEFAULT;

ALTER TABLE bronze.bronze_event_youtube ALTER COLUMN loaded_at SET DEFAULT now();
