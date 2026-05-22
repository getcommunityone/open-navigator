-- Rename nonprofits_search (alternate legacy name) → organization_nonprofit.
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/025_rename_nonprofits_search_to_organization_nonprofit.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/025_rename_nonprofits_search_to_organization_nonprofit.sql
--
-- nonprofits_search → organization_nonprofit
-- (022 handles organizations_nonprofit_search → organization_nonprofit)

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'nonprofits_search'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'organization_nonprofit'
    ) THEN
        ALTER TABLE public.nonprofits_search RENAME TO organization_nonprofit;
    END IF;
END $$;

UPDATE public.log_last_sync
SET table_name = 'organization_nonprofit'
WHERE table_name IN ('nonprofits_search', 'organizations_nonprofit_search');

COMMIT;
