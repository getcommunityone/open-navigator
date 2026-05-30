-- Rename league bronze directory columns: state_usps → state_code, state_name → state.
--
--   psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/031_rename_league_state_columns.sql

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = 'bronze_jurisdictions_municipalities_league'
          AND column_name = 'state_usps'
    ) THEN
        ALTER TABLE bronze.bronze_jurisdictions_municipalities_league
            RENAME COLUMN state_usps TO state_code;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = 'bronze_jurisdictions_municipalities_league'
          AND column_name = 'state_name'
    ) THEN
        ALTER TABLE bronze.bronze_jurisdictions_municipalities_league
            RENAME COLUMN state_name TO state;
    END IF;
END$$;
