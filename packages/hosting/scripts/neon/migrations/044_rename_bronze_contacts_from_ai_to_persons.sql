-- Migration: rename bronze.bronze_contacts_from_ai -> bronze.bronze_persons_from_ai
-- Companion to 043; the AI-generated contacts table follows the same Person-not-Contact
-- terminology shift to align with OpenCivicData Popolo.
--
-- No column renames here — leaving the AI table's schema alone in this pass; the
-- subsequent column-alignment migration can apply once we've audited who writes to it.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/044_rename_bronze_contacts_from_ai_to_persons.sql

BEGIN;

ALTER TABLE bronze.bronze_contacts_from_ai RENAME TO bronze_persons_from_ai;

COMMENT ON TABLE bronze.bronze_persons_from_ai IS
    'AI-extracted person records. Renamed from bronze_contacts_from_ai for Popolo alignment.';

COMMIT;
