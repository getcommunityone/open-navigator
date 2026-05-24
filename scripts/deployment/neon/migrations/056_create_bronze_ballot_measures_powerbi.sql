-- Migration: bronze.bronze_ballot_measures_powerbi — ballot measures scraped
-- from a public Power BI dashboard (see CITATIONS.md "Power BI Ballot Measures
-- Dashboard"). The dashboard reports a headline KPI of ~9,670 measures.
--
-- Schema is wide-and-shallow to match the bronze pattern used by
-- ``bronze.bronze_elections_scraped``: a handful of denormalized columns
-- for cheap filtering and a ``raw_row`` JSONB carrying the full CSV row
-- for downstream models to explode.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/056_create_bronze_ballot_measures_powerbi.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_ballot_measures_powerbi (
    id                  BIGSERIAL PRIMARY KEY,
    scrape_batch_id     UUID NOT NULL,

    -- Best-effort denormalized columns. NULL when the source column is absent
    -- or unmappable; the authoritative copy lives in ``raw_row``.
    measure_id          TEXT,
    measure_title       TEXT,
    measure_summary     TEXT,
    measure_type        TEXT,           -- referendum, initiative, charter_amendment, bond, …
    state_code          CHAR(2),
    state               TEXT,
    jurisdiction_name   TEXT,
    election_date       DATE,
    election_year       INTEGER,
    outcome             TEXT,           -- passed, failed, withdrawn, pending
    yes_count           BIGINT,
    no_count            BIGINT,
    yes_percent         DOUBLE PRECISION,
    source_url          TEXT,

    -- Full CSV row, keyed by source column header. Authoritative for fields
    -- not pulled into the denormalized columns above.
    raw_row             JSONB NOT NULL DEFAULT '{}'::JSONB,

    source_csv_path     TEXT,
    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bbmp_state
    ON bronze.bronze_ballot_measures_powerbi (state_code);
CREATE INDEX IF NOT EXISTS idx_bbmp_year
    ON bronze.bronze_ballot_measures_powerbi (election_year);
CREATE INDEX IF NOT EXISTS idx_bbmp_date
    ON bronze.bronze_ballot_measures_powerbi (election_date);
CREATE INDEX IF NOT EXISTS idx_bbmp_batch
    ON bronze.bronze_ballot_measures_powerbi (scrape_batch_id);
CREATE INDEX IF NOT EXISTS idx_bbmp_outcome
    ON bronze.bronze_ballot_measures_powerbi (outcome);

COMMENT ON TABLE bronze.bronze_ballot_measures_powerbi IS
    'Ballot measures scraped from a public Power BI dashboard. See CITATIONS.md. '
    'One row per ballot measure as published by the dashboard. Best-effort; '
    'treat as bronze.';

COMMENT ON COLUMN bronze.bronze_ballot_measures_powerbi.raw_row IS
    'Original CSV row keyed by source column header — authoritative for fields '
    'not pulled into denormalized columns.';
COMMENT ON COLUMN bronze.bronze_ballot_measures_powerbi.scrape_batch_id IS
    'UUID grouping all rows from a single scrape run.';

COMMIT;
