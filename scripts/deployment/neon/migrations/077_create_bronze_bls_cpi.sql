-- Migration: bronze.bronze_bls_cpi — Bureau of Labor Statistics CPI series
--
-- Stores monthly + annual-average CPI observations from the BLS Public Data
-- API. Primary use is the frontend inflation toggle on dollar charts: one
-- national series (default CUUR0000SA0, CPI-U NSA, all items, U.S. city avg)
-- applied uniformly to every geography, so cross-place "real dollar"
-- comparisons stay coherent. Loaded by:
--   scripts/datasources/bls/load_bls_cpi.py
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -v ON_ERROR_STOP=1 \
--     -f scripts/deployment/neon/migrations/077_create_bronze_bls_cpi.sql
--
-- AFTER applying: run dbt to build the bronze passthrough + staging view:
--   ./scripts/dbt.sh run --select bronze_bls_cpi stg_bls__cpi_annual

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_bls_cpi (
    series_id    VARCHAR(32)   NOT NULL,
    year         INTEGER       NOT NULL,
    -- BLS period codes: M01..M12 = months, M13 = annual average (returned
    -- only when the request sets annualaverage=true). Quarterly / semi-annual
    -- series use Q01..Q04 / S01..S02 — VARCHAR(8) accommodates them too.
    period       VARCHAR(8)    NOT NULL,
    period_name  TEXT,
    value        NUMERIC(10,3) NOT NULL,
    footnotes    TEXT,
    loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (series_id, year, period)
);

CREATE INDEX IF NOT EXISTS idx_bronze_bls_cpi_series_year
    ON bronze.bronze_bls_cpi (series_id, year);

COMMENT ON TABLE bronze.bronze_bls_cpi IS
    'BLS Consumer Price Index observations (monthly + annual average). One national series applied uniformly to all geographies by the frontend real-dollar toggle. Default series: CUUR0000SA0 (CPI-U NSA all items U.S. city avg). Source: api.bls.gov/publicAPI/v2.';

COMMIT;
