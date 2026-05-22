-- Rename NTEE reference table to cause_ntee.
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/023_rename_reference_ntee_codes_to_cause_ntee.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/023_rename_reference_ntee_codes_to_cause_ntee.sql
--
-- reference_ntee_codes → cause_ntee (legacy)
-- causes_ntee          → cause_ntee (current)

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'causes_ntee'
    ) THEN
        ALTER TABLE public.causes_ntee RENAME TO cause_ntee;
    ELSIF EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'reference_ntee_codes'
    ) THEN
        ALTER TABLE public.reference_ntee_codes RENAME TO cause_ntee;
    END IF;
END $$;

COMMIT;
