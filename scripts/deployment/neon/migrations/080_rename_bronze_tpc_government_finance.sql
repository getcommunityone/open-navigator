-- Migration: rename bronze.bronze_tpc_government_finance ->
-- bronze.bronze_jurisdiction_tpc.
--
-- The table holds TPC / Urban Institute republished Census government-finance
-- observations, one row per (gov_type, id_code, fiscal_year). It was created
-- under the data-source-centric name `bronze_tpc_government_finance` in
-- migration 078; we standardize on the jurisdiction-centric naming
-- (`bronze_jurisdiction_*`) used across the bronze layer.
--
-- Idempotent: the rename is guarded so re-applying (or applying after a fresh
-- DB already has the new name, e.g. via the self-healing ingestion DDL) is a
-- no-op rather than an error. Indexes keep their existing `idx_btpc_*` names —
-- Postgres carries them to the renamed relation unchanged.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -v ON_ERROR_STOP=1 \
--     -f scripts/deployment/neon/migrations/080_rename_bronze_tpc_government_finance.sql

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'bronze'
          AND tablename = 'bronze_tpc_government_finance'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'bronze'
          AND tablename = 'bronze_jurisdiction_tpc'
    ) THEN
        ALTER TABLE bronze.bronze_tpc_government_finance
            RENAME TO bronze_jurisdiction_tpc;
    END IF;
END $$;

COMMENT ON TABLE bronze.bronze_jurisdiction_tpc IS
    'TPC / Urban Institute republication of Census Bureau Annual Survey of State and Local Government Finances + Census of Governments, 1977+. One row per (gov_type, id_code, fiscal_year). ~300 finance variables per row carried verbatim in raw_record JSONB.';

COMMIT;
