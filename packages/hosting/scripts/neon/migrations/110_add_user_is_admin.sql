-- Add an is_admin flag to the operational user table.
-- Gates the new Admin area (Lighthouse report + Batch jobs) — the menu link and
-- the /admin route are only exposed when /api/auth/me reports is_admin = true.
-- The "user" table is an ORM/operational table that always lives in `public`
-- (see api/database.py); it is NOT a dbt mart.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS + a guarded UPDATE for the maintainer.
-- Defaults to false so existing accounts stay non-admin.
--
-- Apply: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--   -f packages/hosting/scripts/neon/migrations/110_add_user_is_admin.sql

BEGIN;

ALTER TABLE public."user"
    ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN public."user".is_admin IS
    'Operator/admin flag. When true the account sees the Admin area '
    '(Lighthouse report + batch jobs) via the profile menu and /admin route.';

-- Bootstrap the maintainer accounts as admin so the area is reachable post-migration.
-- Both are the same maintainer (personal + CommunityOne work email).
-- Safe no-op for any address that does not exist in this database.
UPDATE public."user" SET is_admin = TRUE
WHERE email IN ('johncbowyer@gmail.com', 'johnbowyer@communityone.com');

COMMIT;
