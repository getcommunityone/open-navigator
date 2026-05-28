-- Migration: bronze.bronze_census_finance_variables — Census Bureau
-- ``timeseries/govsstatefin`` variables codebook (the dictionary for the
-- State and Local Government Finance survey that TPC re-publishes in
-- bronze.bronze_tpc_government_finance).
--
-- One row per (dataset, variable_code). raw_record JSONB carries the
-- variable's metadata blob verbatim so downstream joins can recover any
-- field the codebook gains later (Census occasionally adds new keys like
-- 'datetime', 'is-weight', etc.).
--
-- Loaded by:
--   python -m ingestion.census.govsstatefin_variables          (fetch + load)
--   scripts/datasources/census/download_census_finance_variables.py
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -v ON_ERROR_STOP=1 \
--     -f scripts/deployment/neon/migrations/079_create_bronze_census_finance_variables.sql
--
-- AFTER applying: load + build the bronze dbt model:
--   python -m ingestion.census.govsstatefin_variables
--   ./scripts/dbt.sh run --select bronze_census_finance_variables

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_census_finance_variables (
    -- Census dataset id (e.g. 'govsstatefin'). Part of the PK so the table
    -- can hold codebooks for sibling Census endpoints later
    -- (govsemploy, govsbe, etc.) without a schema change.
    dataset         VARCHAR(64)   NOT NULL,
    variable_code   VARCHAR(64)   NOT NULL,
    label           TEXT,
    concept         TEXT,
    predicate_type  VARCHAR(32),
    -- `group` is reserved-ish in SQL; rename to var_group to keep queries
    -- quote-free.
    var_group       VARCHAR(64),
    -- `limit` is a SQL reserved word; rename for the same reason.
    var_limit       INTEGER,
    attributes      TEXT,
    required        BOOLEAN,
    source_url      VARCHAR(500)  NOT NULL,
    snapshot_at     TIMESTAMPTZ   NOT NULL,
    raw_record      JSONB         NOT NULL,
    loaded_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    last_updated    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dataset, variable_code)
);

CREATE INDEX IF NOT EXISTS idx_bcfv_concept
    ON bronze.bronze_census_finance_variables (concept)
    WHERE concept IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bcfv_group
    ON bronze.bronze_census_finance_variables (var_group)
    WHERE var_group IS NOT NULL;

COMMENT ON TABLE bronze.bronze_census_finance_variables IS
    'Census Bureau timeseries/govsstatefin variables codebook (dataset/variable_code → label/concept/predicate_type/group). The dictionary for the State and Local Government Finance survey that TPC re-publishes in bronze.bronze_tpc_government_finance. Source: api.census.gov/data/timeseries/govsstatefin/variables.json.';

COMMIT;
