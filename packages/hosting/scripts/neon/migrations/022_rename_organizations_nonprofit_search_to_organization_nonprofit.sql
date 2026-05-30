-- Rename nonprofit search table (singular organization_nonprofit).
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/022_rename_organizations_nonprofit_search_to_organization_nonprofit.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/022_rename_organizations_nonprofit_search_to_organization_nonprofit.sql
--
-- organizations_nonprofit_search → organization_nonprofit
-- nonprofits_search → organization_nonprofit (see 025 if only that name exists)

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'organizations_nonprofit_search'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'organization_nonprofit'
    ) THEN
        ALTER TABLE public.organizations_nonprofit_search RENAME TO organization_nonprofit;
    END IF;
END $$;

UPDATE public.log_last_sync
SET table_name = 'organization_nonprofit'
WHERE table_name IN ('organizations_nonprofit_search', 'nonprofits_search');

COMMIT;
