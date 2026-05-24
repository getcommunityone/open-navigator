-- Migration: bronze.bronze_ballot_measures_powerbi — election_year as VARCHAR(4),
-- plus jurisdiction_id and ocd_id from intermediate.int_jurisdictions (state rows).
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/059_alter_bronze_ballot_measures_powerbi_jurisdiction.sql

BEGIN;

ALTER TABLE bronze.bronze_ballot_measures_powerbi
    ADD COLUMN IF NOT EXISTS jurisdiction_id TEXT,
    ADD COLUMN IF NOT EXISTS ocd_id TEXT;

-- election_year may have been created as INTEGER in 056; normalize to calendar label.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = 'bronze_ballot_measures_powerbi'
          AND column_name = 'election_year'
          AND data_type <> 'character varying'
    ) THEN
        ALTER TABLE bronze.bronze_ballot_measures_powerbi
            ALTER COLUMN election_year TYPE VARCHAR(4)
            USING CASE
                WHEN election_year IS NULL THEN NULL
                ELSE LPAD(TRIM(CAST(election_year AS TEXT)), 4, '0')
            END;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_bbmp_jurisdiction
    ON bronze.bronze_ballot_measures_powerbi (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bbmp_ocd_id
    ON bronze.bronze_ballot_measures_powerbi (ocd_id);

COMMENT ON COLUMN bronze.bronze_ballot_measures_powerbi.election_year IS
    'Calendar year label as VARCHAR(4), e.g. ''2024''.';
COMMENT ON COLUMN bronze.bronze_ballot_measures_powerbi.jurisdiction_id IS
    'State-level int_jurisdictions.jurisdiction_id (jurisdiction_type = state).';
COMMENT ON COLUMN bronze.bronze_ballot_measures_powerbi.ocd_id IS
    'OCD division id for the state (ocd-division/country:us/state:xx) or Open States id when present on int.';

COMMIT;
