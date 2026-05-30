-- Migration: add ocd_id columns and refactor contact schema to OCD conventions.
--
-- Changes:
-- 1. Add ocd_id to intermediate.int_jurisdiction_websites and bronze tables
-- 2. Refactor bronze.bronze_contacts_scraped to use OCD-style contact_details (JSONB array)
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/041_add_ocd_ids.sql

BEGIN;

-- Add OCD ID to jurisdiction website table
ALTER TABLE intermediate.int_jurisdiction_websites
    ADD COLUMN IF NOT EXISTS ocd_id TEXT;

COMMENT ON COLUMN intermediate.int_jurisdiction_websites.ocd_id IS
    'OpenCivicData canonical jurisdiction ID (e.g., ocd-division/country:us/state:ma/place:boston)';

-- Add OCD ID to contacts table
ALTER TABLE bronze.bronze_contacts_scraped
    ADD COLUMN IF NOT EXISTS ocd_id TEXT;

COMMENT ON COLUMN bronze.bronze_contacts_scraped.ocd_id IS
    'OpenCivicData canonical jurisdiction ID for referential integrity';

-- Refactor contacts to use OCD contact_details convention
-- contact_details: JSONB array of {type, value} objects
-- Example: [{"type": "email", "value": "mayor@..."}, {"type": "phone", "value": "+1-..."}]
ALTER TABLE bronze.bronze_contacts_scraped
    ADD COLUMN IF NOT EXISTS contact_details JSONB NOT NULL DEFAULT '[]'::JSONB;

COMMENT ON COLUMN bronze.bronze_contacts_scraped.contact_details IS
    'OCD-style contact details: JSONB array of {type, value} objects (email, phone, twitter, etc.)';

-- Add contact type tracking for audit trail
ALTER TABLE bronze.bronze_contacts_scraped
    ADD COLUMN IF NOT EXISTS contact_source TEXT;

COMMENT ON COLUMN bronze.bronze_contacts_scraped.contact_source IS
    'Source of contact information (website_contacts_page, directory, seed_url, etc.)';

-- Add OCD ID to YouTube table
ALTER TABLE bronze.bronze_jurisdiction_youtube
    ADD COLUMN IF NOT EXISTS ocd_id TEXT;

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.ocd_id IS
    'OpenCivicData canonical jurisdiction ID for referential integrity';

-- Create indexes for faster OCD lookups
CREATE INDEX IF NOT EXISTS idx_bronze_contacts_ocd_id ON bronze.bronze_contacts_scraped(ocd_id);
CREATE INDEX IF NOT EXISTS idx_bronze_youtube_ocd_id ON bronze.bronze_jurisdiction_youtube(ocd_id);
CREATE INDEX IF NOT EXISTS idx_int_jurisdictions_ocd_id ON intermediate.int_jurisdiction_websites(ocd_id);

COMMIT;
