-- ============================================================================
-- ROLLBACK: Remove Datasource Tracking Fields
-- ============================================================================
-- This script removes the datasource tracking fields added by migration 001
--
-- Usage:
--   psql $NEON_DATABASE_URL_DEV -f scripts/deployment/neon/migrations/001_add_datasource_fields_rollback.sql
-- ============================================================================

BEGIN;

-- Drop junction tables
DROP TABLE IF EXISTS bronze_merge_log CASCADE;
DROP TABLE IF EXISTS organizations_meetings CASCADE;
DROP TABLE IF EXISTS contacts_meeting_attendance CASCADE;
DROP TABLE IF EXISTS bills_meetings CASCADE;

-- Remove columns from contact
ALTER TABLE contact 
  DROP COLUMN IF EXISTS datasource,
  DROP COLUMN IF EXISTS datasource_id,
  DROP COLUMN IF EXISTS confidence_score,
  DROP COLUMN IF EXISTS verified,
  DROP COLUMN IF EXISTS verification_date,
  DROP COLUMN IF EXISTS needs_review,
  DROP COLUMN IF EXISTS review_notes;

-- Remove columns from organizations_nonprofit_search
ALTER TABLE organizations_nonprofit_search
  DROP COLUMN IF EXISTS datasource,
  DROP COLUMN IF EXISTS datasource_id,
  DROP COLUMN IF EXISTS confidence_score,
  DROP COLUMN IF EXISTS verified,
  DROP COLUMN IF EXISTS verification_date,
  DROP COLUMN IF EXISTS needs_review,
  DROP COLUMN IF EXISTS review_notes;

-- Remove columns from bills_search
ALTER TABLE bills_search
  DROP COLUMN IF EXISTS datasource,
  DROP COLUMN IF EXISTS datasource_id,
  DROP COLUMN IF EXISTS confidence_score,
  DROP COLUMN IF EXISTS verified,
  DROP COLUMN IF EXISTS verification_date,
  DROP COLUMN IF EXISTS needs_review,
  DROP COLUMN IF EXISTS review_notes,
  DROP COLUMN IF EXISTS is_local_ordinance;

-- Remove columns from event
ALTER TABLE event
  DROP COLUMN IF EXISTS datasource,
  DROP COLUMN IF EXISTS datasource_id,
  DROP COLUMN IF EXISTS confidence_score;

COMMIT;

\echo ''
\echo '✅ Rollback complete - datasource fields removed'
\echo ''
