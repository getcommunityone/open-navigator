-- Rename additional public tables (singular names).
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/019_rename_public_entity_tables.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/019_rename_public_entity_tables.sql
--
-- jurisdictions_search    → jurisdiction
-- bills_map_aggregates  → bill_map_aggregate
-- organizations         → organization
-- organizations_locations → organization_location
-- users                   → user

BEGIN;

ALTER TABLE IF EXISTS public.jurisdictions_search RENAME TO jurisdiction;
ALTER TABLE IF EXISTS public.bills_map_aggregates RENAME TO bill_map_aggregate;
ALTER TABLE IF EXISTS public.organizations RENAME TO organization;
ALTER TABLE IF EXISTS public.organizations_locations RENAME TO organization_location;
ALTER TABLE IF EXISTS public.users RENAME TO "user";

UPDATE public.last_sync SET table_name = 'jurisdiction' WHERE table_name = 'jurisdictions_search';
UPDATE public.last_sync SET table_name = 'bill_map_aggregate' WHERE table_name = 'bills_map_aggregates';

COMMIT;
