-- Rename the policy-map reporting table to use the rpt_ reporting prefix.
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/090_rename_bill_map_aggregate_to_rpt.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/090_rename_bill_map_aggregate_to_rpt.sql
--
-- bill_map_aggregate → rpt_bill_map_aggregate

BEGIN;

ALTER TABLE IF EXISTS public.bill_map_aggregate RENAME TO rpt_bill_map_aggregate;

UPDATE public.log_last_sync
SET table_name = 'rpt_bill_map_aggregate'
WHERE table_name = 'bill_map_aggregate';

COMMIT;
