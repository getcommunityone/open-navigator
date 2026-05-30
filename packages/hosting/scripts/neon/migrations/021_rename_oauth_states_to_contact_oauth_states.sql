-- Rename OAuth CSRF state table (contact auth scope).
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/021_rename_oauth_states_to_contact_oauth_states.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/021_rename_oauth_states_to_contact_oauth_states.sql
--
-- oauth_states → contact_oauth_states

BEGIN;

ALTER TABLE IF EXISTS public.oauth_states RENAME TO contact_oauth_states;

COMMIT;
