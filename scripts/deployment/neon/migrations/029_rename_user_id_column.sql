-- Rename primary key on public."user".
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/029_rename_user_id_column.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/029_rename_user_id_column.sql
--
-- "user".id → user_id

BEGIN;

ALTER TABLE public."user" RENAME COLUMN id TO user_id;

COMMIT;
