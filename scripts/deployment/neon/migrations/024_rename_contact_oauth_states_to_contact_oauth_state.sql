-- Rename OAuth CSRF state table (singular).
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/024_rename_contact_oauth_states_to_contact_oauth_state.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/024_rename_contact_oauth_states_to_contact_oauth_state.sql
--
-- contact_oauth_states → contact_oauth_state

BEGIN;

ALTER TABLE IF EXISTS public.contact_oauth_states RENAME TO contact_oauth_state;

COMMIT;
