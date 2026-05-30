-- Rename core public search / social tables (shorter singular names).
-- Apply: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/018_rename_public_core_tables.sql
--
-- events_search     → event
-- contacts_officials → contact_official
-- contacts_search   → contact
-- causes            → cause
-- stats_aggregates  → state_aggregate

BEGIN;

ALTER TABLE IF EXISTS public.events_search RENAME TO event;
ALTER TABLE IF EXISTS public.contacts_officials RENAME TO contact_official;
ALTER TABLE IF EXISTS public.contacts_search RENAME TO contact;
ALTER TABLE IF EXISTS public.causes RENAME TO cause;
ALTER TABLE IF EXISTS public.stats_aggregates RENAME TO state_aggregate;

-- Views that referenced old table names
DROP VIEW IF EXISTS public.events_recent;
CREATE VIEW public.events_recent AS
SELECT
    id,
    title,
    description,
    event_date,
    jurisdiction_name,
    state,
    city,
    status,
    agenda_url
FROM public.event
WHERE event_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY event_date DESC;

-- Sync bookkeeping (migrate.py record_sync keys)
UPDATE public.last_sync SET table_name = 'event' WHERE table_name = 'events_search';
UPDATE public.last_sync SET table_name = 'contact' WHERE table_name = 'contacts_search';
UPDATE public.last_sync SET table_name = 'state_aggregate' WHERE table_name = 'stats_aggregates';

COMMIT;
