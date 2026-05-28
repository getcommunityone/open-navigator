-- Migration: bronze.bronze_bls_cpi — widen `year` from INTEGER to VARCHAR(4).
--
-- Years are identifiers, not quantities (we never do arithmetic on them), so
-- carry them as a fixed-width string consistent with the rest of the bronze
-- layer. `year` participates in the PK (series_id, year, period) and the
-- idx_bronze_bls_cpi_series_year index; ALTER COLUMN ... TYPE rewrites the
-- table and rebuilds both automatically, so no PK/index DDL is needed here.
--
-- Idempotent: guarded on the current column type, so re-applying (or applying
-- against a fresh DB already created as VARCHAR(4) by migration 077 / the
-- self-healing ingestion DDL) is a no-op rather than a needless table rewrite.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -v ON_ERROR_STOP=1 \
--     -f scripts/deployment/neon/migrations/081_alter_bronze_bls_cpi_year_varchar.sql

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = 'bronze_bls_cpi'
          AND column_name = 'year'
          AND data_type <> 'character varying'
    ) THEN
        ALTER TABLE bronze.bronze_bls_cpi
            ALTER COLUMN year TYPE VARCHAR(4) USING year::VARCHAR(4);
    END IF;
END $$;

COMMIT;
