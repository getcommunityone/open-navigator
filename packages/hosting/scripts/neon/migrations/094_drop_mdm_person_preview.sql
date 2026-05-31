-- Drop the superseded `mdm_person_preview` table.
--
-- `mdm_person_preview` was an early prototype build of the person golden record
-- (8 columns: person_uid, full_name, entity_type, source_system, external_id,
-- city_norm, state_code, name_norm). It has been fully replaced by the richer
-- `mdm_person` mart (PK person_uid; adds source_pk, normalized given/family
-- name, phonetic keys, email, phone, zip5 — see dbt_project/models/marts/
-- mdm_person.sql). Both tables cover the same population, but the preview is
-- not produced by any dbt model and is referenced by no view, FK, or code.
--
-- This migration drops the orphaned table. No dependents exist, so no CASCADE
-- is needed.
--
-- Dev only: psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/094_drop_mdm_person_preview.sql

BEGIN;

DROP TABLE IF EXISTS public.mdm_person_preview;

COMMIT;
