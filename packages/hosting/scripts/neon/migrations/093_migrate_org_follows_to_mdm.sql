-- Fold the integer-keyed followable `organization` entity into the MDM golden
-- record. Organizations are now followed by their text master_org_id via
-- social_follows.target_uid (see api/models.py SocialFollow, api/routes/social.py).
--
-- This migration:
--   1. evolves social_follows to carry a text target key (target_uid) alongside
--      the integer target_id, with per-keyspace partial unique indexes;
--   2. backfills existing organization follows: organization.id -> master_org_id
--      via EIN, then name+city;
--   3. drops org follows that could not be mapped (the org has no MDM match);
--   4. drops the legacy public.organization table.
--
-- Dev only: psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/093_migrate_org_follows_to_mdm.sql

BEGIN;

-- ----- Step 1: evolve social_follows -------------------------------------------
ALTER TABLE public.social_follows ADD COLUMN IF NOT EXISTS target_uid VARCHAR;
ALTER TABLE public.social_follows ALTER COLUMN target_id DROP NOT NULL;

-- Replace the old all-purpose unique constraint with two partial uniques so the
-- integer keyspace (user/official/cause) and the text keyspace (organization)
-- are each enforced independently.
ALTER TABLE public.social_follows DROP CONSTRAINT IF EXISTS unique_social_follow;

CREATE UNIQUE INDEX IF NOT EXISTS uq_social_follow_intid
    ON public.social_follows (follower_id, target_type, target_id)
    WHERE target_uid IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_social_follow_uid
    ON public.social_follows (follower_id, target_type, target_uid)
    WHERE target_uid IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_social_follows_target_uid
    ON public.social_follows (target_uid);

-- ----- Step 2: backfill organization follows -----------------------------------
-- Map by EIN first (most reliable), then by normalized name + city.
DO $$
BEGIN
    IF to_regclass('public.organization') IS NOT NULL THEN

        -- 2a. EIN match
        UPDATE public.social_follows f
        SET target_uid = m.master_org_id, target_id = NULL
        FROM public.organization o
        JOIN public.mdm_organization m ON m.ein = o.ein
        WHERE f.target_type = 'organization'
          AND f.target_uid IS NULL
          AND f.target_id = o.id
          AND o.ein IS NOT NULL;

        -- 2b. name + city fallback for the remainder
        UPDATE public.social_follows f
        SET target_uid = m.master_org_id, target_id = NULL
        FROM public.organization o
        JOIN public.mdm_organization m
            ON lower(m.org_name) = lower(o.name)
           AND lower(coalesce(m.city_norm, '')) = lower(coalesce(o.city, ''))
        WHERE f.target_type = 'organization'
          AND f.target_uid IS NULL
          AND f.target_id = o.id;

    END IF;
END $$;

-- ----- Step 3: drop unmappable organization follows ----------------------------
-- Any org follow still keyed by integer target_id has no MDM counterpart.
DELETE FROM public.social_follows
WHERE target_type = 'organization' AND target_uid IS NULL;

-- ----- Step 4: retire the legacy followable entity -----------------------------
DROP TABLE IF EXISTS public.organization CASCADE;

COMMIT;
