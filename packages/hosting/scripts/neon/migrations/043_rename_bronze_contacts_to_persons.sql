-- Migration: rename bronze.bronze_contacts_scraped -> bronze.bronze_persons_scraped
-- and align column names with OpenCivicData Popolo conventions
-- (https://open-civic-data.readthedocs.io/, https://www.popoloproject.com/).
--
-- Column mapping:
--   person_name    -> name           (Popolo Person.name)
--   title_or_role  -> role           (Popolo Membership.role)
--   department    -> organization   (Popolo Membership.organization)
--
-- Email, phone, mailing_address stay as denormalized convenience columns; the
-- structured ``contact_details`` JSONB column already exists for the strict
-- Popolo array form ([{type:"email"/"voice"/"address", value:"..."}, ...]).
--
-- Indexes are renamed for consistency so downstream observability tools that
-- search by index name don't drift.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/043_rename_bronze_contacts_to_persons.sql

BEGIN;

ALTER TABLE bronze.bronze_contacts_scraped RENAME TO bronze_persons_scraped;

ALTER TABLE bronze.bronze_persons_scraped RENAME COLUMN person_name   TO name;
ALTER TABLE bronze.bronze_persons_scraped RENAME COLUMN title_or_role TO role;
ALTER TABLE bronze.bronze_persons_scraped RENAME COLUMN department    TO organization;

ALTER INDEX bronze.idx_bronze_contacts_scraped_jurisdiction RENAME TO idx_bronze_persons_scraped_jurisdiction;
ALTER INDEX bronze.idx_bronze_contacts_scraped_batch         RENAME TO idx_bronze_persons_scraped_batch;
ALTER INDEX bronze.idx_bronze_contacts_scraped_scraped_at    RENAME TO idx_bronze_persons_scraped_scraped_at;
ALTER INDEX bronze.idx_bronze_contacts_scraped_source_page   RENAME TO idx_bronze_persons_scraped_source_page;

COMMENT ON TABLE bronze.bronze_persons_scraped IS
    'Best-effort structured persons scraped from HTML directory pages (board/council/officials). '
    'Column names align with OpenCivicData Popolo: ``name`` (Person), ``role`` (Membership.role), '
    '``organization`` (Membership.organization). Denormalized ``email``/``phone``/``mailing_address`` '
    'kept for convenience; structured form in ``contact_details`` JSONB.';

COMMENT ON COLUMN bronze.bronze_persons_scraped.name         IS 'Popolo Person.name';
COMMENT ON COLUMN bronze.bronze_persons_scraped.role         IS 'Popolo Membership.role';
COMMENT ON COLUMN bronze.bronze_persons_scraped.organization IS 'Popolo Membership.organization';

COMMIT;
