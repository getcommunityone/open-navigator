-- Migration: bronze.bronze_ballotpedia_measures — ballot measures scraped from
-- Ballotpedia.org (state-wide and jurisdiction-specific pages). Schema is aligned
-- with NIST SP 1500-100 BallotMeasureContest fields consumed by
-- ``dbt_project/models/bronze/bronze_ballot_measures_nist.sql``.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/057_create_bronze_ballotpedia_measures.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_ballotpedia_measures (
    id                  BIGSERIAL PRIMARY KEY,
    scrape_batch_id     UUID NOT NULL,

    -- Stable source key (typically ocd-ballotmeasure/UUID derived from title + jurisdiction).
    measure_id          TEXT NOT NULL,

    -- NIST GpUnit linkage — ocd-division/country:us/...
    ocd_division_id     TEXT,

    -- Denormalized geography for cheap filtering.
    state_code          CHAR(2),
    jurisdiction_id     TEXT,
    jurisdiction_name   TEXT,
    jurisdiction_type   TEXT,

    -- NIST BallotMeasureContest fields.
    election_date       DATE,
    election_year       VARCHAR(4),
    measure_number      TEXT,
    measure_title       TEXT NOT NULL,
    full_text           TEXT,
    summary_text        TEXT,
    measure_type        TEXT,
    subject_areas       TEXT,

    -- NIST BallotMeasureSelectionResults (sparse at bronze).
    yes_votes           BIGINT,
    no_votes            BIGINT,
    passed              BOOLEAN,

    -- Provenance.
    source_url          TEXT,
    measure_page_url    TEXT,

    -- Full scraped measure dict — authoritative for fields not denormalized above.
    raw_row             JSONB NOT NULL DEFAULT '{}'::JSONB,
    source_json_path    TEXT,

    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bbp_meas_ocd
    ON bronze.bronze_ballotpedia_measures (ocd_division_id);
CREATE INDEX IF NOT EXISTS idx_bbp_meas_state
    ON bronze.bronze_ballotpedia_measures (state_code);
CREATE INDEX IF NOT EXISTS idx_bbp_meas_jurisdiction
    ON bronze.bronze_ballotpedia_measures (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bbp_meas_date
    ON bronze.bronze_ballotpedia_measures (election_date);
CREATE INDEX IF NOT EXISTS idx_bbp_meas_year
    ON bronze.bronze_ballotpedia_measures (election_year);
CREATE INDEX IF NOT EXISTS idx_bbp_meas_batch
    ON bronze.bronze_ballotpedia_measures (scrape_batch_id);
CREATE INDEX IF NOT EXISTS idx_bbp_meas_measure_id
    ON bronze.bronze_ballotpedia_measures (measure_id);

COMMENT ON TABLE bronze.bronze_ballotpedia_measures IS
    'Ballot measures scraped from Ballotpedia.org (state and local jurisdiction pages). '
    'NIST-aligned denormalized columns plus raw_row JSONB. Best-effort; treat as bronze.';

COMMENT ON COLUMN bronze.bronze_ballotpedia_measures.measure_id IS
    'Stable source record id — consumed by bronze_ballot_measures_nist as source_record_id.';
COMMENT ON COLUMN bronze.bronze_ballotpedia_measures.ocd_division_id IS
    'OCD Division ID (GpUnit ExternalIdentifier) for joining to jurisdictions.';
COMMENT ON COLUMN bronze.bronze_ballotpedia_measures.election_year IS
    'Calendar year label as VARCHAR(4), e.g. ''2024''.';
COMMENT ON COLUMN bronze.bronze_ballotpedia_measures.raw_row IS
    'Full scraped measure payload keyed by scraper field names.';

COMMIT;
