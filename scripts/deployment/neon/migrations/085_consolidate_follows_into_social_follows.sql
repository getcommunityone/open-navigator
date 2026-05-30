-- Migration: Consolidate the four follow tables into one polymorphic social_follows
-- Purpose: user_follows, contact_official_follows, organization_follows and
--          cause_follows were four near-identical (user -> entity) tables. Replace
--          them with a single social_follows(follower_id, target_type, target_id),
--          backfilling any existing rows, then drop the originals.
-- Date: 2026-05-30
--
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/085_consolidate_follows_into_social_follows.sql

BEGIN;

-- 1. New consolidated table -------------------------------------------------
CREATE TABLE IF NOT EXISTS social_follows (
    id          SERIAL PRIMARY KEY,
    follower_id INTEGER NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    target_type VARCHAR(32) NOT NULL CHECK (target_type IN ('user', 'official', 'organization', 'cause')),
    target_id   INTEGER NOT NULL,
    created_at  TIMESTAMP DEFAULT now(),
    CONSTRAINT unique_social_follow UNIQUE (follower_id, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_social_follows_follower ON social_follows (follower_id);
CREATE INDEX IF NOT EXISTS idx_social_follows_target   ON social_follows (target_type, target_id);

-- 2. Backfill from each legacy table (guarded — each may not exist) ----------
DO $$
BEGIN
    IF to_regclass('public.user_follows') IS NOT NULL THEN
        INSERT INTO social_follows (follower_id, target_type, target_id, created_at)
        SELECT follower_id, 'user', following_id, created_at FROM user_follows
        ON CONFLICT ON CONSTRAINT unique_social_follow DO NOTHING;
    END IF;

    IF to_regclass('public.contact_official_follows') IS NOT NULL THEN
        INSERT INTO social_follows (follower_id, target_type, target_id, created_at)
        SELECT user_id, 'official', official_id, created_at FROM contact_official_follows
        ON CONFLICT ON CONSTRAINT unique_social_follow DO NOTHING;
    END IF;

    IF to_regclass('public.organization_follows') IS NOT NULL THEN
        INSERT INTO social_follows (follower_id, target_type, target_id, created_at)
        SELECT user_id, 'organization', organization_id, created_at FROM organization_follows
        ON CONFLICT ON CONSTRAINT unique_social_follow DO NOTHING;
    END IF;

    IF to_regclass('public.cause_follows') IS NOT NULL THEN
        INSERT INTO social_follows (follower_id, target_type, target_id, created_at)
        SELECT user_id, 'cause', cause_id, created_at FROM cause_follows
        ON CONFLICT ON CONSTRAINT unique_social_follow DO NOTHING;
    END IF;
END $$;

-- 3. Drop the legacy tables -------------------------------------------------
DROP TABLE IF EXISTS user_follows;
DROP TABLE IF EXISTS contact_official_follows;
DROP TABLE IF EXISTS organization_follows;
DROP TABLE IF EXISTS cause_follows;

COMMIT;
