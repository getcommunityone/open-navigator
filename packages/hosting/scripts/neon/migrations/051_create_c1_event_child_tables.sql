-- Migration: create c1_* event child tables mirroring the OpenStates schema for
-- opencivicdata_eventagendaitem / _eventagendamedia / _eventdocument / _eventmedia /
-- _eventparticipant / _eventrelatedentity.
--
-- Column structure matches the OpenStates side 1:1 (same names, same types) so a
-- future cross-DB sync is a straight INSERT-SELECT. No communityone-only columns
-- are added in this migration — these tables are scaffolding for upcoming scraping
-- + parsing work; we'll add extension columns after we see what the parsers
-- actually produce.
--
-- Soft foreign keys: ``event_id`` columns point at ``c1_event.id`` (varchar). We do
-- NOT declare an actual FOREIGN KEY constraint because c1_event.id is currently NULL
-- for all 1,301 existing rows — the constraint would fail until that's backfilled.
-- The plain varchar + index is enough for joins; a real FK can be added later in a
-- separate migration once c1_event.id is populated.
--
-- The OpenStates UUID PKs become ``id UUID DEFAULT gen_random_uuid()`` so inserts
-- without an explicit id work.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/051_create_c1_event_child_tables.sql

BEGIN;

-- Required for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- =====================================================================
-- c1_eventagendaitem  (mirrors opencivicdata_eventagendaitem)
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.c1_eventagendaitem (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    description     TEXT NOT NULL,
    classification  TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    "order"         INTEGER NOT NULL,
    subjects        TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    notes           TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    event_id        VARCHAR(50) NOT NULL,   -- soft FK -> c1_event.id
    extras          JSONB NOT NULL DEFAULT '{}'::JSONB
);
CREATE INDEX IF NOT EXISTS ix_c1_eventagendaitem_event_id
    ON public.c1_eventagendaitem (event_id);
CREATE INDEX IF NOT EXISTS ix_c1_eventagendaitem_order
    ON public.c1_eventagendaitem (event_id, "order");
COMMENT ON TABLE  public.c1_eventagendaitem IS
    'Agenda items for a c1_event (mirrors openstates.opencivicdata_eventagendaitem).';
COMMENT ON COLUMN public.c1_eventagendaitem.event_id IS
    'Soft FK to c1_event.id (no constraint declared until c1_event.id is backfilled).';


-- =====================================================================
-- c1_eventagendamedia  (mirrors opencivicdata_eventagendamedia)
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.c1_eventagendamedia (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note            VARCHAR(300) NOT NULL,
    date            VARCHAR(25) NOT NULL DEFAULT '',
    "offset"        INTEGER,
    agenda_item_id  UUID NOT NULL REFERENCES public.c1_eventagendaitem(id) ON DELETE CASCADE,
    classification  VARCHAR(100) NOT NULL DEFAULT '',
    links           JSONB NOT NULL DEFAULT '[]'::JSONB
);
CREATE INDEX IF NOT EXISTS ix_c1_eventagendamedia_agenda_item_id
    ON public.c1_eventagendamedia (agenda_item_id);
COMMENT ON TABLE public.c1_eventagendamedia IS
    'Media attachments per agenda item (mirrors opencivicdata_eventagendamedia).';


-- =====================================================================
-- c1_eventdocument  (mirrors opencivicdata_eventdocument)
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.c1_eventdocument (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note            TEXT NOT NULL,
    date            VARCHAR(25) NOT NULL DEFAULT '',
    event_id        VARCHAR(50) NOT NULL,    -- soft FK -> c1_event.id
    classification  VARCHAR(50) NOT NULL DEFAULT '',
    links           JSONB NOT NULL DEFAULT '[]'::JSONB
);
CREATE INDEX IF NOT EXISTS ix_c1_eventdocument_event_id
    ON public.c1_eventdocument (event_id);
CREATE INDEX IF NOT EXISTS ix_c1_eventdocument_classification
    ON public.c1_eventdocument (classification);
COMMENT ON TABLE public.c1_eventdocument IS
    'Event-level documents — agendas, minutes, attachments (mirrors opencivicdata_eventdocument).';
COMMENT ON COLUMN public.c1_eventdocument.event_id IS
    'Soft FK to c1_event.id.';


-- =====================================================================
-- c1_eventmedia  (mirrors opencivicdata_eventmedia)
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.c1_eventmedia (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note            VARCHAR(300) NOT NULL,
    date            VARCHAR(25) NOT NULL DEFAULT '',
    "offset"        INTEGER,
    event_id        VARCHAR(50) NOT NULL,
    classification  VARCHAR(50) NOT NULL DEFAULT '',
    links           JSONB NOT NULL DEFAULT '[]'::JSONB
);
CREATE INDEX IF NOT EXISTS ix_c1_eventmedia_event_id
    ON public.c1_eventmedia (event_id);
COMMENT ON TABLE public.c1_eventmedia IS
    'Event-level media — recordings, photos, etc. (mirrors opencivicdata_eventmedia).';


-- =====================================================================
-- c1_eventparticipant  (mirrors opencivicdata_eventparticipant)
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.c1_eventparticipant (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(2000) NOT NULL,
    entity_type     VARCHAR(20) NOT NULL,          -- 'person' | 'organization'
    note            TEXT NOT NULL DEFAULT '',
    event_id        VARCHAR(50) NOT NULL,          -- soft FK -> c1_event.id
    organization_id VARCHAR(53),                   -- soft FK -> c1_organization.id
    person_id       VARCHAR(47)                    -- soft FK -> c1_person.id
);
CREATE INDEX IF NOT EXISTS ix_c1_eventparticipant_event_id
    ON public.c1_eventparticipant (event_id);
CREATE INDEX IF NOT EXISTS ix_c1_eventparticipant_person_id
    ON public.c1_eventparticipant (person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_eventparticipant_organization_id
    ON public.c1_eventparticipant (organization_id) WHERE organization_id IS NOT NULL;
COMMENT ON TABLE public.c1_eventparticipant IS
    'Attendees/participants at an event (mirrors opencivicdata_eventparticipant). '
    'entity_type discriminates between person_id and organization_id.';


-- =====================================================================
-- c1_eventrelatedentity  (mirrors opencivicdata_eventrelatedentity)
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.c1_eventrelatedentity (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(2000) NOT NULL,
    entity_type     VARCHAR(20) NOT NULL,
    note            TEXT NOT NULL DEFAULT '',
    agenda_item_id  UUID NOT NULL REFERENCES public.c1_eventagendaitem(id) ON DELETE CASCADE,
    bill_id         VARCHAR(45),
    organization_id VARCHAR(53),
    person_id       VARCHAR(47),
    vote_event_id   VARCHAR(45)
);
CREATE INDEX IF NOT EXISTS ix_c1_eventrelatedentity_agenda_item_id
    ON public.c1_eventrelatedentity (agenda_item_id);
CREATE INDEX IF NOT EXISTS ix_c1_eventrelatedentity_person_id
    ON public.c1_eventrelatedentity (person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_eventrelatedentity_organization_id
    ON public.c1_eventrelatedentity (organization_id) WHERE organization_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_c1_eventrelatedentity_bill_id
    ON public.c1_eventrelatedentity (bill_id) WHERE bill_id IS NOT NULL;
COMMENT ON TABLE public.c1_eventrelatedentity IS
    'Entities referenced by an agenda item — bills, people, organizations, vote events '
    '(mirrors opencivicdata_eventrelatedentity).';

COMMIT;
