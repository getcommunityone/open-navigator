-- Rename core columns on public.event.
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/028_rename_event_columns.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/028_rename_event_columns.sql
--
-- id          → event_id
-- title       → event_title
-- description → event_description

BEGIN;

DROP VIEW IF EXISTS public.events_recent;

ALTER TABLE public.event RENAME COLUMN id TO event_id;
ALTER TABLE public.event RENAME COLUMN title TO event_title;
ALTER TABLE public.event RENAME COLUMN description TO event_description;

DROP INDEX IF EXISTS public.idx_events_title_search;
CREATE INDEX idx_events_event_title_search ON public.event
    USING GIN (to_tsvector('english', event_title));

CREATE VIEW public.events_recent AS
SELECT
    event_id,
    event_title,
    event_description,
    event_date,
    jurisdiction_name,
    state,
    city,
    status,
    agenda_url
FROM public.event
WHERE event_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY event_date DESC;

COMMIT;
