-- Migration: two more renames continuing the OpenStates-alignment work from 048.
--
--   1. public.organization -> public.c1_organization, columns aligned to
--      openstates.opencivicdata_organization.
--   2. public.c1_contact   -> public.c1_person (more accurate Popolo / OCD term).
--
-- Same conventions as migration 048:
--   * Rename matching columns to the OpenStates name.
--   * Add OCD columns at the end with sensible defaults.
--   * Communityone-only columns stay with ``COMMENT '[source: communityone]'``.
--   * Integer PK preserved as ``legacy_id``; new varchar ``id`` added.
--   * Indexes renamed for consistency so observability tools that search by index
--     name don't drift.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/049_rename_organization_to_c1_and_contact_to_person.sql

BEGIN;

-- =====================================================================
-- public.organization -> public.c1_organization
--                                (aligns to openstates.opencivicdata_organization)
-- =====================================================================

ALTER TABLE public.organization RENAME TO c1_organization;

-- Matching column renames
ALTER TABLE public.c1_organization RENAME COLUMN org_type TO classification;

-- PK strategy: int id -> legacy_id; new varchar id for OCD alignment.
ALTER TABLE public.c1_organization RENAME COLUMN id TO legacy_id;
ALTER TABLE public.c1_organization ADD COLUMN IF NOT EXISTS id VARCHAR(53);

-- New OpenStates columns
ALTER TABLE public.c1_organization
    ADD COLUMN IF NOT EXISTS extras          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS jurisdiction_id VARCHAR(300),
    ADD COLUMN IF NOT EXISTS parent_id       VARCHAR(53),
    ADD COLUMN IF NOT EXISTS links           JSONB        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS sources         JSONB        NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS other_names     JSONB        NOT NULL DEFAULT '[]'::jsonb;

-- Widen the timestamps from naive to TZ-aware (OCD uses timestamptz).
ALTER TABLE public.c1_organization
    ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

-- Rename indexes for consistency (the int PK and its index follow the column rename).
ALTER INDEX public.organizations_pkey      RENAME TO c1_organization_pkey;
ALTER INDEX public.ix_organizations_ein    RENAME TO ix_c1_organization_ein;
ALTER INDEX public.ix_organizations_id     RENAME TO ix_c1_organization_legacy_id;
ALTER INDEX public.ix_organizations_name   RENAME TO ix_c1_organization_name;
ALTER INDEX public.ix_organizations_slug   RENAME TO ix_c1_organization_slug;

COMMENT ON TABLE  public.c1_organization               IS 'Communityone organization table, column structure aligned to openstates.opencivicdata_organization (migration 049).';
COMMENT ON COLUMN public.c1_organization.id            IS 'OpenStates-aligned identifier (ocd-organization/UUID). NULL until backfilled.';
COMMENT ON COLUMN public.c1_organization.legacy_id     IS '[source: communityone] original integer PK preserved during migration 049';
COMMENT ON COLUMN public.c1_organization.slug          IS '[source: communityone] URL-friendly slug; not in opencivicdata_organization';
COMMENT ON COLUMN public.c1_organization.description   IS '[source: communityone] not in opencivicdata_organization';
COMMENT ON COLUMN public.c1_organization.logo_url      IS '[source: communityone] not in OCD; OCD uses links jsonb';
COMMENT ON COLUMN public.c1_organization.website       IS '[source: communityone] not in OCD; OCD uses links jsonb';
COMMENT ON COLUMN public.c1_organization.state         IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_organization.county        IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_organization.city          IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_organization.address       IS '[source: communityone] denormalized';
COMMENT ON COLUMN public.c1_organization.email         IS '[source: communityone] OCD uses contact_details elsewhere';
COMMENT ON COLUMN public.c1_organization.phone         IS '[source: communityone] OCD uses contact_details elsewhere';
COMMENT ON COLUMN public.c1_organization.ein           IS '[source: communityone] 990 nonprofit field';
COMMENT ON COLUMN public.c1_organization.ntee_code     IS '[source: communityone] 990 nonprofit classification';
COMMENT ON COLUMN public.c1_organization.revenue       IS '[source: communityone] 990 nonprofit field';
COMMENT ON COLUMN public.c1_organization.follower_count IS '[source: communityone] application metric, not in OCD';
COMMENT ON COLUMN public.c1_organization.is_verified   IS '[source: communityone] application flag, not in OCD';
COMMENT ON COLUMN public.c1_organization.verified_at   IS '[source: communityone] application flag, not in OCD';


-- =====================================================================
-- public.c1_contact -> public.c1_person
--   c1_person is the Popolo / OCD canonical term. Same column structure as
--   c1_contact (no column changes); just a table rename and index renames.
-- =====================================================================

ALTER TABLE public.c1_contact RENAME TO c1_person;

-- Indexes (the PK index was already named ``contacts_search_pkey``)
ALTER INDEX public.contacts_search_pkey         RENAME TO c1_person_pkey;
ALTER INDEX public.idx_contacts_ein             RENAME TO idx_c1_person_ein;
ALTER INDEX public.idx_contacts_name_search     RENAME TO idx_c1_person_name_search;
ALTER INDEX public.idx_contacts_org_name_search RENAME TO idx_c1_person_org_name_search;
ALTER INDEX public.idx_contacts_role            RENAME TO idx_c1_person_role;
ALTER INDEX public.idx_contacts_state           RENAME TO idx_c1_person_state;

COMMENT ON TABLE public.c1_person IS
    'Communityone person table (renamed from c1_contact in migration 049). '
    'Column structure aligned to openstates.opencivicdata_person via migration 048.';

COMMIT;
