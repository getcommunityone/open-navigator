-- Retire the legacy nonprofit serving table; org data is now served from the
-- MDM golden record (public.mdm_organization) + the nonprofit detail satellite
-- (public.mdm_organization_nonprofit), both synced from dbt marts. This follows
-- migration 089, which already retired public.organization_location and
-- declared mdm_organization the canonical org serving table.
--
-- Dev only: psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/092_consolidate_org_serving_into_mdm.sql
--
-- NOTE: public.organization (the integer-keyed followable social entity used by
-- social.py) is NOT touched here — see migration 093 for that fold.

BEGIN;

DROP TABLE IF EXISTS public.organization_nonprofit CASCADE;

-- Clean up sync bookkeeping for the retired table, if present.
DO $$
BEGIN
    IF to_regclass('public.log_last_sync') IS NOT NULL THEN
        DELETE FROM public.log_last_sync WHERE table_name = 'organization_nonprofit';
    END IF;
END $$;

COMMIT;
