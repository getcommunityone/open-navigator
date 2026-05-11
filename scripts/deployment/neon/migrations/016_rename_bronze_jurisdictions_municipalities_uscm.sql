-- Rename USCM mayor bronze table → bronze_jurisdictions_municipalities_uscm.
-- Run once if `bronze_jurisdictions_municipalities_mayors` exists from an older loader.
-- Skips when the old table is missing or the new name already exists.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'bronze'
          AND tablename = 'bronze_jurisdictions_municipalities_mayors'
    )
    AND NOT EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'bronze'
          AND tablename = 'bronze_jurisdictions_municipalities_uscm'
    ) THEN
        EXECUTE 'ALTER TABLE bronze.bronze_jurisdictions_municipalities_mayors RENAME TO bronze_jurisdictions_municipalities_uscm';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'bronze' AND indexname = 'idx_bjmuni_mayors_state'
    )
    AND NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'bronze' AND indexname = 'idx_bjmuscm_state'
    ) THEN
        EXECUTE 'ALTER INDEX bronze.idx_bjmuni_mayors_state RENAME TO idx_bjmuscm_state';
    END IF;
END $$;

COMMIT;
