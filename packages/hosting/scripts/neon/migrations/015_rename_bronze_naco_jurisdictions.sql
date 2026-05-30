-- One-time rename: legacy NACo tables → bronze_jurisdictions_*_naco indexes idx_bjcnc_* / idx_bjcno_*.
-- Skips cleanly if legacy names are absent. If new names already exist, index renames may no-op row count 0.

BEGIN;

ALTER TABLE IF EXISTS bronze.bronze_naco_counties RENAME TO bronze_jurisdictions_counties_naco;
ALTER TABLE IF EXISTS bronze.bronze_naco_officials RENAME TO bronze_jurisdictions_officials_naco;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'bronze' AND indexname = 'idx_bnc_state') THEN
        EXECUTE 'ALTER INDEX bronze.idx_bnc_state RENAME TO idx_bjcnc_state';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'bronze' AND indexname = 'idx_bnc_fips') THEN
        EXECUTE 'ALTER INDEX bronze.idx_bnc_fips RENAME TO idx_bjcnc_fips';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'bronze' AND indexname = 'idx_bno_state') THEN
        EXECUTE 'ALTER INDEX bronze.idx_bno_state RENAME TO idx_bjcno_state';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'bronze' AND indexname = 'idx_bno_fips') THEN
        EXECUTE 'ALTER INDEX bronze.idx_bno_fips RENAME TO idx_bjcno_fips';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'bronze' AND indexname = 'idx_bno_county') THEN
        EXECUTE 'ALTER INDEX bronze.idx_bno_county RENAME TO idx_bjcno_county';
    END IF;
END $$;

COMMIT;
