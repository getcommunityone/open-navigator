-- Migration: drop public.events_channels_search and public.contact_official.
--
-- ``events_channels_search`` (944 rows): every row is a subset of
-- ``intermediate.int_events_channels`` (1,444 rows). The only column that was uniquely
-- populated in ECS but not in the intermediate base table — ``is_government`` — was
-- backfilled into intermediate.int_events_channels in a prior step (944 UPDATEs). The
-- two callers (``packages/scrapers/src/scrapers/youtube/analyze_channels.py`` and
-- ``scripts/datasources/gemini/load_meeting_transcripts.py``) were repointed at
-- ``intermediate.int_events_channels_enriched`` (a VIEW that already exposes the
-- quality_score / activity_status / event_count etc. that ECS had).
--
-- ``contact_official`` (0 rows): never populated in this Neon DB. Code references all
-- point at a parquet **filename** (data/gold/states/<ST>/contact_official.parquet),
-- not the table. Dropping the empty table doesn't break those file accesses.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/052_drop_events_channels_search_and_contact_official.sql

BEGIN;

DROP TABLE IF EXISTS public.events_channels_search CASCADE;
DROP TABLE IF EXISTS public.contact_official CASCADE;

COMMIT;
