-- Migration: bronze.bronze_tpc_government_finance — Tax Policy Center / Urban
-- Institute republication of the Census Bureau Annual Survey of State and
-- Local Government Finances + Census of Governments, 1977 onward.
--
-- TPC reconciles ~50 years of survey-variable drift (Census has renamed and
-- merged item codes multiple times) and ships the unified data as wide CSVs
-- — one row per government-year, ~300 finance variables per row. We land
-- the data verbatim into `raw_record` JSONB with a small set of hot keys
-- hoisted for indexing; staging models normalize the wide variable space
-- without re-loading bronze.
--
-- Canonical bulk file: a Google Drive ZIP, file id
-- ``1FtZQR34S69D2DnOeM_agRTeIVwojbaAK`` by default. Catalog pages:
--   https://state-local-finance-data.taxpolicycenter.org/
--   https://datacatalog.urban.org/
--   https://my.willamette.edu/site/mba/public-datasets
--
-- Loaded by:
--   python -m ingestion.tpc.finance --fetch    (download + load all gov types)
--   scripts/datasources/tpc/load_tpc_finance.py (thin shim — same flags)
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -v ON_ERROR_STOP=1 \
--     -f scripts/deployment/neon/migrations/078_create_bronze_tpc_government_finance.sql
--
-- AFTER applying: load data, then build the bronze dbt model:
--   python -m ingestion.tpc.finance --fetch
--   ./scripts/dbt.sh run --select bronze_tpc_government_finance

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_tpc_government_finance (
    id_code        VARCHAR(64)   NOT NULL,
    name           TEXT,
    -- Numeric Census state FIPS (e.g. '06' for California).
    state_fips     CHAR(2),
    -- 2-letter postal code, back-filled from state_fips when only FIPS is
    -- present in the source CSV. Indexed for cross-source joins.
    state_code     CHAR(2),
    -- One of: 'state', 'county', 'city', 'school_district',
    -- 'special_district', or 'other'. Part of the PK because id_code is
    -- not guaranteed unique across government types.
    gov_type       VARCHAR(32)   NOT NULL,
    fiscal_year    INTEGER       NOT NULL,
    population     BIGINT,
    raw_record     JSONB         NOT NULL,
    source_file    TEXT          NOT NULL,
    loaded_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    last_updated   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (gov_type, id_code, fiscal_year)
);

CREATE INDEX IF NOT EXISTS idx_btpc_state_gov
    ON bronze.bronze_tpc_government_finance (state_fips, gov_type);

CREATE INDEX IF NOT EXISTS idx_btpc_year
    ON bronze.bronze_tpc_government_finance (fiscal_year);

CREATE INDEX IF NOT EXISTS idx_btpc_state_code
    ON bronze.bronze_tpc_government_finance (state_code)
    WHERE state_code IS NOT NULL;

COMMENT ON TABLE bronze.bronze_tpc_government_finance IS
    'TPC / Urban Institute republication of Census Bureau Annual Survey of State and Local Government Finances + Census of Governments, 1977+. One row per (gov_type, id_code, fiscal_year). ~300 finance variables per row carried verbatim in raw_record JSONB.';

COMMIT;
