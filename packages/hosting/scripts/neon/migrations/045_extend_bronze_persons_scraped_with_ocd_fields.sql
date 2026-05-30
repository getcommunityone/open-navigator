-- Migration: extend bronze.bronze_persons_scraped with OpenCivicData Person fields
-- mirrored from openstates.public.opencivicdata_person:
--   biography, given_name, family_name, gender, birth_date, death_date,
--   image (portrait URL), primary_party
-- Plus the FK-style join key to OCD persons:
--   openstates_person_id   = ocd-person/<UUID> (from opencivicdata_person.id)
-- And aggregated child-table arrays (JSONB) for downstream enrichment:
--   links       = array of {note, url} from opencivicdata_personlink
--   identifiers = array of {scheme, identifier} from opencivicdata_personidentifier
--
-- All columns nullable — the scraper populates them best-effort, the enrichment
-- model fills the rest from bronze.bronze_jurisdiction_openstates (migration 046).
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/045_extend_bronze_persons_scraped_with_ocd_fields.sql

BEGIN;

ALTER TABLE bronze.bronze_persons_scraped
    ADD COLUMN IF NOT EXISTS biography             TEXT,
    ADD COLUMN IF NOT EXISTS given_name            TEXT,
    ADD COLUMN IF NOT EXISTS family_name           TEXT,
    ADD COLUMN IF NOT EXISTS gender                TEXT,
    ADD COLUMN IF NOT EXISTS birth_date            TEXT,
    ADD COLUMN IF NOT EXISTS death_date            TEXT,
    ADD COLUMN IF NOT EXISTS image                 TEXT,
    ADD COLUMN IF NOT EXISTS primary_party         TEXT,
    ADD COLUMN IF NOT EXISTS openstates_person_id  TEXT,
    ADD COLUMN IF NOT EXISTS links                 JSONB NOT NULL DEFAULT '[]'::JSONB,
    ADD COLUMN IF NOT EXISTS identifiers           JSONB NOT NULL DEFAULT '[]'::JSONB;

CREATE INDEX IF NOT EXISTS idx_bronze_persons_scraped_openstates_person_id
    ON bronze.bronze_persons_scraped (openstates_person_id);

COMMENT ON COLUMN bronze.bronze_persons_scraped.biography            IS 'OCD Person.biography — narrative bio text.';
COMMENT ON COLUMN bronze.bronze_persons_scraped.given_name           IS 'OCD Person.given_name — first/given name.';
COMMENT ON COLUMN bronze.bronze_persons_scraped.family_name          IS 'OCD Person.family_name — surname/family name.';
COMMENT ON COLUMN bronze.bronze_persons_scraped.gender               IS 'OCD Person.gender.';
COMMENT ON COLUMN bronze.bronze_persons_scraped.image                IS 'OCD Person.image — portrait URL.';
COMMENT ON COLUMN bronze.bronze_persons_scraped.primary_party        IS 'OpenStates extension — primary political party.';
COMMENT ON COLUMN bronze.bronze_persons_scraped.openstates_person_id IS 'FK-style join key to opencivicdata_person.id (ocd-person/<UUID>).';
COMMENT ON COLUMN bronze.bronze_persons_scraped.links                IS 'JSONB array of {note,url} mirrored from opencivicdata_personlink.';
COMMENT ON COLUMN bronze.bronze_persons_scraped.identifiers          IS 'JSONB array of {scheme,identifier} mirrored from opencivicdata_personidentifier.';

COMMIT;
