-- Migration: rename public.{event, jurisdiction, contact} -> public.c1_{...} and
-- align their column structure with the OpenStates ``opencivicdata_*`` tables.
--
-- The ``c1_`` prefix denotes "communityone" (the existing open-navigator domain layer)
-- and is kept distinct from ``opencivicdata_*`` so a future cross-DB sync can preserve
-- both views simultaneously.
--
-- Approach:
--   1. Rename table.
--   2. Rename matching columns to the OpenStates name (e.g. ``event_title`` -> ``name``).
--   3. Add OpenStates columns that don't exist yet, with sensible defaults so existing
--      rows pass the NOT NULL constraints. Keep them NULLable here — tightening to
--      NOT NULL belongs in a follow-up once data is backfilled.
--   4. Communityone-only columns stay at the end and get a ``COMMENT '[source:
--      communityone]'`` so the lineage is greppable.
--   5. Integer PKs become ``legacy_id`` to preserve any in-app references; a new
--      varchar ``id`` is added to match the OCD ``ocd-<entity>/UUID`` convention.
--      The legacy_id PK constraint is preserved.
--
-- Reversible? Partially. ``ALTER COLUMN ... TYPE TIMESTAMPTZ`` is the only operation
-- here that loses information (assumes UTC for naive timestamps).
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/048_rename_public_to_c1_align_with_openstates.sql

BEGIN;

-- =====================================================================
-- public.event -> public.c1_event   (aligns to openstates.opencivicdata_event)
-- =====================================================================

ALTER TABLE public.event RENAME TO c1_event;

-- Matching column renames
ALTER TABLE public.c1_event RENAME COLUMN event_title       TO name;
ALTER TABLE public.c1_event RENAME COLUMN event_description TO description;
ALTER TABLE public.c1_event RENAME COLUMN event_date        TO start_date;
ALTER TABLE public.c1_event RENAME COLUMN meeting_type      TO classification;
ALTER TABLE public.c1_event RENAME COLUMN last_updated      TO updated_at;

-- PK strategy: preserve int as legacy_id; new varchar id for OCD alignment
ALTER TABLE public.c1_event RENAME COLUMN event_id TO legacy_id;
ALTER TABLE public.c1_event ADD COLUMN IF NOT EXISTS id VARCHAR(50);

-- New OpenStates columns
ALTER TABLE public.c1_event
    ADD COLUMN IF NOT EXISTS created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS extras      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS end_date    VARCHAR(25),
    ADD COLUMN IF NOT EXISTS all_day     BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS location_id UUID,
    ADD COLUMN IF NOT EXISTS dedupe_key  VARCHAR(500),
    ADD COLUMN IF NOT EXISTS deleted     BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS upstream_id VARCHAR(300),
    ADD COLUMN IF NOT EXISTS links       JSONB       NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS sources     JSONB       NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE public.c1_event
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

COMMENT ON TABLE  public.c1_event       IS 'Communityone events table, column structure aligned to openstates.opencivicdata_event (migration 048).';
COMMENT ON COLUMN public.c1_event.id              IS 'OpenStates-aligned identifier (ocd-event/UUID). NULL until backfilled.';
COMMENT ON COLUMN public.c1_event.legacy_id       IS '[source: communityone] original integer PK preserved during migration 048.';
COMMENT ON COLUMN public.c1_event.event_time          IS '[source: communityone] not in opencivicdata_event; merge into start_date as needed';
COMMENT ON COLUMN public.c1_event.jurisdiction_name   IS '[source: communityone] denormalized; opencivicdata_event uses jurisdiction_id lookup';
COMMENT ON COLUMN public.c1_event.jurisdiction_type   IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_event.state               IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_event.city                IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_event.location            IS '[source: communityone] denormalized; OCD uses location_id -> opencivicdata_eventlocation';
COMMENT ON COLUMN public.c1_event.agenda_url          IS '[source: communityone] denormalized; OCD uses opencivicdata_eventdocument';
COMMENT ON COLUMN public.c1_event.minutes_url         IS '[source: communityone] denormalized; OCD uses opencivicdata_eventdocument';
COMMENT ON COLUMN public.c1_event.video_url           IS '[source: communityone] denormalized; OCD uses links jsonb or eventmedia';
COMMENT ON COLUMN public.c1_event.source              IS '[source: communityone] denormalized; OCD uses sources jsonb';
COMMENT ON COLUMN public.c1_event.channel_id          IS '[source: communityone] YouTube channel binding (not in OCD)';
COMMENT ON COLUMN public.c1_event.view_count          IS '[source: communityone] YouTube metric';
COMMENT ON COLUMN public.c1_event.duration_minutes    IS '[source: communityone] YouTube metric';
COMMENT ON COLUMN public.c1_event.like_count          IS '[source: communityone] YouTube metric';
COMMENT ON COLUMN public.c1_event.language            IS '[source: communityone] not in OCD';
COMMENT ON COLUMN public.c1_event.channel_type        IS '[source: communityone] not in OCD';
COMMENT ON COLUMN public.c1_event.location_description IS '[source: communityone] not in OCD';
COMMENT ON COLUMN public.c1_event.channel_url         IS '[source: communityone] YouTube binding';


-- =====================================================================
-- public.jurisdiction -> public.c1_jurisdiction
--                                 (aligns to openstates.opencivicdata_jurisdiction)
-- =====================================================================

ALTER TABLE public.jurisdiction RENAME TO c1_jurisdiction;

-- Matching column renames
ALTER TABLE public.c1_jurisdiction RENAME COLUMN type         TO classification;
ALTER TABLE public.c1_jurisdiction RENAME COLUMN last_updated TO updated_at;

-- PK strategy: int id -> legacy_id; existing varchar jurisdiction_id becomes the new id
ALTER TABLE public.c1_jurisdiction RENAME COLUMN id              TO legacy_id;
ALTER TABLE public.c1_jurisdiction RENAME COLUMN jurisdiction_id TO id;

-- New OpenStates columns
ALTER TABLE public.c1_jurisdiction
    ADD COLUMN IF NOT EXISTS created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS extras               JSONB       NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS url                  VARCHAR(2000),
    ADD COLUMN IF NOT EXISTS division_id          VARCHAR(300),
    ADD COLUMN IF NOT EXISTS latest_bill_update   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS latest_people_update TIMESTAMPTZ;

ALTER TABLE public.c1_jurisdiction
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

COMMENT ON TABLE  public.c1_jurisdiction IS 'Communityone jurisdiction table, column structure aligned to openstates.opencivicdata_jurisdiction (migration 048).';
COMMENT ON COLUMN public.c1_jurisdiction.legacy_id     IS '[source: communityone] original integer PK preserved during migration 048';
COMMENT ON COLUMN public.c1_jurisdiction.id            IS 'OpenStates-aligned identifier (ocd-jurisdiction/...). Populated from previous jurisdiction_id column.';
COMMENT ON COLUMN public.c1_jurisdiction.state         IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_jurisdiction.county        IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_jurisdiction.geoid         IS '[source: communityone] Census GEOID';
COMMENT ON COLUMN public.c1_jurisdiction.fips_code     IS '[source: communityone] FIPS code';
COMMENT ON COLUMN public.c1_jurisdiction.population    IS '[source: communityone] denormalized (ACS / Census)';
COMMENT ON COLUMN public.c1_jurisdiction.area_sq_miles IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_jurisdiction.source        IS '[source: communityone] data provenance label';


-- =====================================================================
-- public.contact -> public.c1_contact   (aligns to openstates.opencivicdata_person)
-- =====================================================================

ALTER TABLE public.contact RENAME TO c1_contact;

-- Matching column renames
ALTER TABLE public.c1_contact RENAME COLUMN last_updated TO updated_at;

-- PK strategy: int id -> legacy_id; new varchar id matches ocd-person/UUID
ALTER TABLE public.c1_contact RENAME COLUMN id TO legacy_id;
ALTER TABLE public.c1_contact ADD COLUMN IF NOT EXISTS id VARCHAR(47);

-- New OpenStates Person columns
ALTER TABLE public.c1_contact
    ADD COLUMN IF NOT EXISTS created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS extras                  JSONB       NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS family_name             VARCHAR(100),
    ADD COLUMN IF NOT EXISTS given_name              VARCHAR(100),
    ADD COLUMN IF NOT EXISTS image                   VARCHAR(2000),
    ADD COLUMN IF NOT EXISTS gender                  VARCHAR(100),
    ADD COLUMN IF NOT EXISTS biography               TEXT,
    ADD COLUMN IF NOT EXISTS birth_date              VARCHAR(10),
    ADD COLUMN IF NOT EXISTS death_date              VARCHAR(10),
    ADD COLUMN IF NOT EXISTS primary_party           VARCHAR(100),
    ADD COLUMN IF NOT EXISTS current_jurisdiction_id VARCHAR(300),
    ADD COLUMN IF NOT EXISTS "current_role"            JSONB;

ALTER TABLE public.c1_contact
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

COMMENT ON TABLE  public.c1_contact IS 'Communityone contact/person table, column structure aligned to openstates.opencivicdata_person (migration 048).';
COMMENT ON COLUMN public.c1_contact.legacy_id          IS '[source: communityone] original integer PK preserved during migration 048';
COMMENT ON COLUMN public.c1_contact.id                 IS 'OpenStates-aligned identifier (ocd-person/UUID). NULL until backfilled.';
COMMENT ON COLUMN public.c1_contact.title              IS '[source: communityone] not in opencivicdata_person; can be merged into "current_role" JSONB';
COMMENT ON COLUMN public.c1_contact.organization_name  IS '[source: communityone] not in opencivicdata_person';
COMMENT ON COLUMN public.c1_contact.organization_ein   IS '[source: communityone] 990 nonprofit field';
COMMENT ON COLUMN public.c1_contact.phone              IS '[source: communityone] OCD Person uses contact_details for phone';
COMMENT ON COLUMN public.c1_contact.street_address     IS '[source: communityone] OCD Person uses contact_details for address';
COMMENT ON COLUMN public.c1_contact.city               IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_contact.state              IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_contact.zip_code           IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_contact.role_type          IS '[source: communityone] not in opencivicdata_person';
COMMENT ON COLUMN public.c1_contact.compensation       IS '[source: communityone] 990 nonprofit field';
COMMENT ON COLUMN public.c1_contact.hours_per_week     IS '[source: communityone] 990 nonprofit field';
COMMENT ON COLUMN public.c1_contact.source             IS '[source: communityone] data provenance label';
COMMENT ON COLUMN public.c1_contact.tax_year           IS '[source: communityone] 990 nonprofit field';

COMMIT;
