-- Rename public stats aggregate table (jurisdiction scope).
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/027_rename_state_aggregate_to_jurisdiction_state_aggregate.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/027_rename_state_aggregate_to_jurisdiction_state_aggregate.sql
--
-- state_aggregate → jurisdiction_state_aggregate

BEGIN;

ALTER TABLE IF EXISTS public.state_aggregate RENAME TO jurisdiction_state_aggregate;

UPDATE public.log_last_sync
SET table_name = 'jurisdiction_state_aggregate'
WHERE table_name = 'state_aggregate';

COMMIT;
