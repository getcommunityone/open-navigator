-- Migration: rename legacy Ballotpedia bronze tables to current naming.
--
--   bronze_ballotpedia_external_links  → bronze_websites_ballotpedia
--   bronze_ballotpedia_measures        → bronze_ballot_measures_ballotpedia
--
-- Idempotent: only renames when the old name exists and the new name does not.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/058_rename_ballotpedia_bronze_tables.sql

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'bronze' AND table_name = 'bronze_ballotpedia_external_links'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'bronze' AND table_name = 'bronze_websites_ballotpedia'
    ) THEN
        ALTER TABLE bronze.bronze_ballotpedia_external_links
            RENAME TO bronze_websites_ballotpedia;
    END IF;
END $$;

ALTER INDEX IF EXISTS bronze.idx_bronze_bp_links_source_page
    RENAME TO idx_bbwb_source_page;
ALTER INDEX IF EXISTS bronze.idx_bronze_bp_links_target_host
    RENAME TO idx_bbwb_target_host;
ALTER INDEX IF EXISTS bronze.idx_bronze_bp_links_state
    RENAME TO idx_bbwb_state;
ALTER INDEX IF EXISTS bronze.idx_bronze_bp_links_jurisdiction
    RENAME TO idx_bbwb_jurisdiction;
ALTER INDEX IF EXISTS bronze.idx_bronze_bp_links_batch
    RENAME TO idx_bbwb_batch;
ALTER INDEX IF EXISTS bronze.idx_bronze_bp_links_target_kind
    RENAME TO idx_bbwb_target_kind;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'bronze' AND table_name = 'bronze_ballotpedia_measures'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'bronze' AND table_name = 'bronze_ballot_measures_ballotpedia'
    ) THEN
        ALTER TABLE bronze.bronze_ballotpedia_measures
            RENAME TO bronze_ballot_measures_ballotpedia;
    END IF;
END $$;

ALTER INDEX IF EXISTS bronze.idx_bbp_meas_ocd
    RENAME TO idx_bbmb_ocd;
ALTER INDEX IF EXISTS bronze.idx_bbp_meas_state
    RENAME TO idx_bbmb_state;
ALTER INDEX IF EXISTS bronze.idx_bbp_meas_jurisdiction
    RENAME TO idx_bbmb_jurisdiction;
ALTER INDEX IF EXISTS bronze.idx_bbp_meas_date
    RENAME TO idx_bbmb_date;
ALTER INDEX IF EXISTS bronze.idx_bbp_meas_year
    RENAME TO idx_bbmb_year;
ALTER INDEX IF EXISTS bronze.idx_bbp_meas_batch
    RENAME TO idx_bbmb_batch;
ALTER INDEX IF EXISTS bronze.idx_bbp_meas_measure_id
    RENAME TO idx_bbmb_measure_id;

COMMIT;
