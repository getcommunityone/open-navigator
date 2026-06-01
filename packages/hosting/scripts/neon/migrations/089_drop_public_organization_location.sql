-- Migration: drop public.organization_location (retired serving table)
--
-- The ~571k HIFLD-style location rows (schools, cities, parks, sheriffs,
-- churches, police, hospitals) are now consolidated into the MDM golden org
-- table public.mdm_organization. They enter the MDM pool upstream via the dbt
-- model stg_locations__org (source bronze.bronze_locations), so the public
-- serving table organization_location is redundant and is retired here.
--
-- Org data is now served from public.mdm_organization (PK master_org_id), with
-- parent_jurisdiction_id rolling each org up to its governing jurisdiction.
--
-- NOTE: public.organization (the integer-keyed social/followable entity used by
-- the social-follows feature in api/routes/social.py) is intentionally NOT
-- dropped here — it is app-owned and orthogonal to org *data* serving.
--
-- Apply (dev only — never prod):
--   ./scripts/deployment/neon/psql_resolved.sh -v ON_ERROR_STOP=1 \
--     -f packages/hosting/scripts/neon/migrations/089_drop_public_organization_location.sql

BEGIN;

DROP TABLE IF EXISTS public.organization_location CASCADE;

-- Clean up sync bookkeeping for the retired table, if a last_sync table exists.
DO $$
BEGIN
    IF to_regclass('public.last_sync') IS NOT NULL THEN
        DELETE FROM public.last_sync WHERE table_name = 'organization_location';
    END IF;
END $$;

COMMIT;
