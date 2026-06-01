-- Retire the integer-keyed followable `cause` entity in favour of the dbt tag
-- taxonomy. Causes are now followed by their text tag_id (e.g. 'ntee|E20',
-- 'everyorg|climate') via social_follows.target_uid -- the same text keyspace
-- organizations use (see migration 093, api/models.py SocialFollow,
-- api/routes/social.py).
--
-- This migration:
--   1. backfills existing cause follows onto the tag taxonomy where a code maps
--      (cause.slug -> tag.source_code), switching target_id -> target_uid;
--   2. drops cause follows that cannot be mapped (no tag counterpart);
--   3. drops the legacy public.cause table and its identity sequence.
--
-- The social_follows text keyspace (target_uid + the two partial unique indexes)
-- already exists from migration 093, so no schema evolution is needed here.
--
-- Dev only: psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f packages/hosting/scripts/neon/migrations/099_migrate_cause_follows_to_tag.sql

BEGIN;

-- ----- Step 1: backfill cause follows onto the tag taxonomy ---------------------
-- The legacy cause table carries no vocabulary, so match its slug against the
-- tag source_code. Prefer the everyorg vocabulary (curated, slug-shaped codes)
-- over ntee. Re-key from the integer target_id to the text target_uid.
DO $$
BEGIN
    IF to_regclass('public.cause') IS NOT NULL THEN
        UPDATE public.social_follows f
        SET target_uid = t.tag_id, target_id = NULL
        FROM public.cause c
        JOIN LATERAL (
            SELECT tag_id
            FROM public.tag
            WHERE lower(source_code) = lower(c.slug)
            ORDER BY (vocabulary = 'everyorg') DESC
            LIMIT 1
        ) t ON true
        WHERE f.target_type = 'cause'
          AND f.target_uid IS NULL
          AND f.target_id = c.id;
    END IF;
END $$;

-- Anything still keyed by integer target_id had no tag counterpart. Relabel the
-- successfully mapped rows to the new target_type, then drop the unmappable.
UPDATE public.social_follows
SET target_type = 'tag'
WHERE target_type = 'cause' AND target_uid IS NOT NULL;

DELETE FROM public.social_follows
WHERE target_type = 'cause';

-- ----- Step 2: retire the legacy followable entity -----------------------------
DROP TABLE IF EXISTS public.cause CASCADE;
DROP SEQUENCE IF EXISTS public.causes_id_seq CASCADE;

COMMIT;
