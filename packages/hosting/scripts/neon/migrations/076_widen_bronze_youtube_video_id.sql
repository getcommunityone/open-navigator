-- Migration: Widen video_id columns from VARCHAR(20) to VARCHAR(64)
-- Purpose: Accommodate non-standard YouTube identifiers (e.g. live/upcoming
--          broadcast IDs) that exceed the standard 11-char video ID and
--          overflow the existing VARCHAR(20) columns, causing inserts to fail
--          with "value too long for type character varying(20)".
-- Date: 2026-05-28
--
-- Usage:
--   ./scripts/deployment/neon/psql_resolved.sh -v ON_ERROR_STOP=1 \
--     -f scripts/deployment/neon/migrations/076_widen_bronze_youtube_video_id.sql
--
-- AFTER applying: run dbt to rebuild the dropped views:
--   ./scripts/dbt.sh run --select stg_youtube__event+ int_events_localview+

BEGIN;

-- Drop dbt views that reference bronze_events_youtube.video_id; ALTER TYPE
-- cannot proceed while views depend on the column. CASCADE picks up the
-- transitive dependent intermediate.int_events_channels_enriched. dbt will
-- recreate all three on the next `dbt run`.
DROP VIEW IF EXISTS staging.stg_youtube__event CASCADE;
DROP VIEW IF EXISTS intermediate.int_events_localview CASCADE;

DO $$
DECLARE
    -- Tables in bronze schema whose video_id column should be widened.
    target_tables TEXT[] := ARRAY[
        'bronze_events_youtube',
        'bronze_events_text_ai',
        'bronze_bills',
        'bronze_meeting_item_legislation',
        'bronze_policy_decisions',
        'bronze_events_analysis_ai'
    ];
    tbl TEXT;
    text_ai_trigger_exists BOOLEAN;
BEGIN
    -- Drop trigger on bronze_events_text_ai.video_id (if present); ALTER TYPE
    -- cannot proceed while a trigger references the column. Recreated below.
    SELECT EXISTS (
        SELECT 1 FROM pg_trigger t
        JOIN pg_class c ON t.tgrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = 'bronze'
          AND c.relname = 'bronze_events_text_ai'
          AND t.tgname = 'trg_sync_text_ai_geo_from_youtube'
          AND NOT t.tgisinternal
    ) INTO text_ai_trigger_exists;

    IF text_ai_trigger_exists THEN
        EXECUTE 'DROP TRIGGER trg_sync_text_ai_geo_from_youtube ON bronze.bronze_events_text_ai';
    END IF;

    FOREACH tbl IN ARRAY target_tables LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'bronze'
              AND table_name = tbl
              AND column_name = 'video_id'
        ) THEN
            EXECUTE format('ALTER TABLE bronze.%I ALTER COLUMN video_id TYPE VARCHAR(64)', tbl);
        END IF;
    END LOOP;

    IF text_ai_trigger_exists THEN
        EXECUTE $sql$
            CREATE TRIGGER trg_sync_text_ai_geo_from_youtube
                BEFORE INSERT OR UPDATE OF video_id ON bronze.bronze_events_text_ai
                FOR EACH ROW EXECUTE FUNCTION bronze.sync_text_ai_geo_from_youtube()
        $sql$;
    END IF;
END
$$;

COMMIT;
