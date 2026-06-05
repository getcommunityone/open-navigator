-- Migration: split the stats rollup's single "contacts" metric into two
-- distinct people metrics on ``public.jurisdiction_state_aggregate``:
--
--   * ``persons_count``  — everyone in the person index (``public.mdm_person``),
--     the count behind the hero "Persons" search tab.
--   * ``leaders_count``  — elected + government officials
--     (``public.contact_official``) PLUS nonprofit board members
--     (``public.mdm_bridge_person_organization`` where the person is an officer,
--     director/trustee, key employee, or institutional trustee). The count
--     behind the hero "Leaders" search tab.
--
-- The old ``contacts_count`` column (meeting-contacts via events, effectively
-- unpopulated — 0 everywhere in the serving table) is RENAMED to
-- ``persons_count`` so existing rows/grants/indexes survive, then
-- ``leaders_count`` is added alongside it.
--
-- The two leader sources live in different ID namespaces and cannot be deduped
-- across each other, so ``leaders_count`` is the SUM of the two source counts.
--
-- Column values are (re)populated by
-- ``dbt_project/scripts/backfill_persons_leaders_counts.py`` (local serving DB,
-- where the bronze sources the dbt mart needs are absent) and by the dbt mart
-- ``jurisdiction_state_aggregate`` in the full warehouse pipeline.
--
-- Idempotent: safe to re-run.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'jurisdiction_state_aggregate'
          AND column_name = 'contacts_count'
    ) THEN
        ALTER TABLE public.jurisdiction_state_aggregate
            RENAME COLUMN contacts_count TO persons_count;
    END IF;
END
$$;

ALTER TABLE public.jurisdiction_state_aggregate
    ADD COLUMN IF NOT EXISTS persons_count INTEGER DEFAULT 0;

ALTER TABLE public.jurisdiction_state_aggregate
    ADD COLUMN IF NOT EXISTS leaders_count INTEGER DEFAULT 0;
