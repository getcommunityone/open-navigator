-- Rename public sync log tables (log_ prefix).
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/020_rename_public_log_sync_tables.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/020_rename_public_log_sync_tables.sql
--
-- last_sync      → log_last_sync
-- neon_sync_log  → log_neon_sync

BEGIN;

ALTER TABLE IF EXISTS public.last_sync RENAME TO log_last_sync;
ALTER TABLE IF EXISTS public.neon_sync_log RENAME TO log_neon_sync;

COMMIT;
