-- ============================================================================
-- Add Datasource Tracking Fields to Production Tables
-- ============================================================================
-- This migration adds columns to track data provenance and quality
--
-- Usage:
--   psql $NEON_DATABASE_URL_DEV -f scripts/deployment/neon/migrations/001_add_datasource_fields.sql
--
-- Rollback:
--   psql $NEON_DATABASE_URL_DEV -f scripts/deployment/neon/migrations/001_add_datasource_fields_rollback.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- CONTACTS_SEARCH
-- ============================================================================

ALTER TABLE contact 
  ADD COLUMN IF NOT EXISTS datasource VARCHAR(100) DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS datasource_id VARCHAR(255),  -- ID in source system (Wikidata QID, OpenStates ID, etc.)
  ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.50,  -- 0.0-1.0
  ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE,  -- Human-verified?
  ADD COLUMN IF NOT EXISTS verification_date TIMESTAMP,
  ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE,  -- Flagged for manual review
  ADD COLUMN IF NOT EXISTS review_notes TEXT;

-- Update existing records to have appropriate datasource
UPDATE contact 
SET datasource = CASE
  WHEN source = 'openstates' THEN 'openstates_api'
  WHEN source = 'irs_form990' THEN 'irs_990'
  WHEN source = 'meeting_transcript' THEN 'localview'
  ELSE 'unknown'
END,
confidence_score = CASE
  WHEN source = 'openstates' THEN 1.0
  WHEN source = 'irs_form990' THEN 1.0
  WHEN source = 'meeting_transcript' THEN 0.70
  ELSE 0.50
END
WHERE datasource = 'unknown';

-- Indexes for datasource queries
CREATE INDEX IF NOT EXISTS idx_contacts_datasource ON contact(datasource);
CREATE INDEX IF NOT EXISTS idx_contacts_datasource_id ON contact(datasource_id) WHERE datasource_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_verified ON contact(verified);
CREATE INDEX IF NOT EXISTS idx_contacts_needs_review ON contact(needs_review) WHERE needs_review = TRUE;

COMMENT ON COLUMN contact.datasource IS 'Source system: openstates_api, irs_990, gemini_ai_extraction, localview, manual_entry';
COMMENT ON COLUMN contact.datasource_id IS 'ID in source system (Wikidata QID, OpenStates person_id, etc.)';
COMMENT ON COLUMN contact.confidence_score IS 'Data quality score: 1.0=authoritative, 0.6=AI extracted, 0.0=uncertain';
COMMENT ON COLUMN contact.verified IS 'Has this record been human-verified?';


-- ============================================================================
-- ORGANIZATIONS_NONPROFIT_SEARCH
-- ============================================================================

ALTER TABLE organizations_nonprofit_search
  ADD COLUMN IF NOT EXISTS datasource VARCHAR(100) DEFAULT 'irs_bmf',
  ADD COLUMN IF NOT EXISTS datasource_id VARCHAR(255),
  ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 1.0,
  ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT TRUE,  -- IRS data is authoritative
  ADD COLUMN IF NOT EXISTS verification_date TIMESTAMP,
  ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS review_notes TEXT;

-- Update existing records
UPDATE organizations_nonprofit_search
SET datasource = 'irs_bmf',
    confidence_score = 1.0,
    verified = TRUE
WHERE datasource IS NULL OR datasource = 'irs_bmf';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_orgs_datasource ON organizations_nonprofit_search(datasource);
CREATE INDEX IF NOT EXISTS idx_orgs_datasource_id ON organizations_nonprofit_search(datasource_id) WHERE datasource_id IS NOT NULL;

COMMENT ON COLUMN organizations_nonprofit_search.datasource IS 'Source: irs_bmf, irs_990, gemini_ai_extraction, wikidata';
COMMENT ON COLUMN organizations_nonprofit_search.datasource_id IS 'Wikidata QID if linked';


-- ============================================================================
-- BILLS_SEARCH
-- ============================================================================

ALTER TABLE bills_search
  ADD COLUMN IF NOT EXISTS datasource VARCHAR(100) DEFAULT 'openstates_api',
  ADD COLUMN IF NOT EXISTS datasource_id VARCHAR(255),  -- OpenStates bill_id
  ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 1.0,
  ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS verification_date TIMESTAMP,
  ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS review_notes TEXT,
  ADD COLUMN IF NOT EXISTS is_local_ordinance BOOLEAN DEFAULT FALSE;  -- Local bills not in OpenStates

-- Update existing records (all current bills are from OpenStates)
UPDATE bills_search
SET datasource = 'openstates_api',
    datasource_id = bill_id,  -- bill_id is the OpenStates ID
    confidence_score = 1.0,
    verified = TRUE,
    is_local_ordinance = FALSE
WHERE datasource IS NULL OR datasource = 'openstates_api';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bills_datasource ON bills_search(datasource);
CREATE INDEX IF NOT EXISTS idx_bills_datasource_id ON bills_search(datasource_id) WHERE datasource_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bills_is_local ON bills_search(is_local_ordinance) WHERE is_local_ordinance = TRUE;

COMMENT ON COLUMN bills_search.datasource IS 'Source: openstates_api, gemini_ai_extraction, manual_entry';
COMMENT ON COLUMN bills_search.datasource_id IS 'OpenStates bill ID (ocd-bill/...)';
COMMENT ON COLUMN bills_search.is_local_ordinance IS 'True for local ordinances/resolutions not tracked by OpenStates';


-- ============================================================================
-- EVENTS_SEARCH
-- ============================================================================

ALTER TABLE event
  ADD COLUMN IF NOT EXISTS datasource VARCHAR(100) DEFAULT 'localview',
  ADD COLUMN IF NOT EXISTS datasource_id VARCHAR(255),  -- YouTube video ID, Legistar ID, etc.
  ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.90;

-- Update existing records
UPDATE event
SET datasource = CASE
  WHEN source = 'localview' THEN 'localview'
  WHEN source = 'youtube' THEN 'youtube_api'
  WHEN source = 'legistar' THEN 'legistar_api'
  ELSE 'unknown'
END,
datasource_id = video_url,  -- Use video URL as ID for now
confidence_score = CASE
  WHEN source = 'localview' THEN 0.95
  WHEN source = 'youtube' THEN 0.85
  ELSE 0.70
END
WHERE datasource IS NULL OR datasource = 'localview';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_datasource ON event(datasource);
CREATE INDEX IF NOT EXISTS idx_events_datasource_id ON event(datasource_id) WHERE datasource_id IS NOT NULL;

COMMENT ON COLUMN event.datasource IS 'Source: localview, youtube_api, legistar_api, granicus';


-- ============================================================================
-- JUNCTION TABLES (Many-to-Many Relationships)
-- ============================================================================

-- Track which bills were discussed in which meetings
CREATE TABLE IF NOT EXISTS bills_meetings (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER REFERENCES bills_search(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES event(id) ON DELETE CASCADE,
    
    -- Context from AI analysis
    relevance TEXT,
    action_taken VARCHAR(100),  -- 'passed', 'tabled', 'discussed', 'voted_on'
    vote_result VARCHAR(50),    -- 'approved', 'rejected', 'no_action'
    decision_id VARCHAR(255),   -- Link to bronze_decisions if applicable
    
    -- Metadata
    datasource VARCHAR(100) DEFAULT 'gemini_ai_extraction',
    confidence_score FLOAT DEFAULT 0.60,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(bill_id, event_id)
);

CREATE INDEX idx_bills_meetings_bill ON bills_meetings(bill_id);
CREATE INDEX idx_bills_meetings_event ON bills_meetings(event_id);
CREATE INDEX idx_bills_meetings_datasource ON bills_meetings(datasource);

COMMENT ON TABLE bills_meetings IS 'Many-to-many: bills discussed in meetings';


-- Track which contacts attended which meetings
CREATE TABLE IF NOT EXISTS contacts_meeting_attendance (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER REFERENCES contact(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES event(id) ON DELETE CASCADE,
    
    -- Role in this specific meeting
    appeared_as VARCHAR(100),  -- 'speaker', 'council_member', 'witness', 'lobbyist'
    title_at_time VARCHAR(200),
    is_lobbyist BOOLEAN DEFAULT FALSE,
    lobbyist_registration_number VARCHAR(100),
    
    -- Metadata
    datasource VARCHAR(100) DEFAULT 'gemini_ai_extraction',
    confidence_score FLOAT DEFAULT 0.60,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(contact_id, event_id)
);

CREATE INDEX idx_attendance_contact ON contacts_meeting_attendance(contact_id);
CREATE INDEX idx_attendance_event ON contacts_meeting_attendance(event_id);
CREATE INDEX idx_attendance_is_lobbyist ON contacts_meeting_attendance(is_lobbyist) WHERE is_lobbyist = TRUE;

COMMENT ON TABLE contacts_meeting_attendance IS 'Many-to-many: contacts attending meetings';


-- Track which organizations were mentioned in meetings
CREATE TABLE IF NOT EXISTS organizations_meetings (
    id SERIAL PRIMARY KEY,
    organization_ein VARCHAR(20) REFERENCES organizations_nonprofit_search(ein) ON DELETE CASCADE,
    event_id INTEGER REFERENCES event(id) ON DELETE CASCADE,
    
    -- Context
    role_in_meeting TEXT,
    financial_interest TEXT,
    is_lobbyist_entity BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    datasource VARCHAR(100) DEFAULT 'gemini_ai_extraction',
    confidence_score FLOAT DEFAULT 0.60,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(organization_ein, event_id)
);

CREATE INDEX idx_orgs_meetings_org ON organizations_meetings(organization_ein);
CREATE INDEX idx_orgs_meetings_event ON organizations_meetings(event_id);
CREATE INDEX idx_orgs_meetings_lobbyist ON organizations_meetings(is_lobbyist_entity) WHERE is_lobbyist_entity = TRUE;

COMMENT ON TABLE organizations_meetings IS 'Many-to-many: organizations mentioned in meetings';


-- ============================================================================
-- MERGE TRACKING TABLE
-- ============================================================================

-- Track merge operations for debugging
CREATE TABLE IF NOT EXISTS bronze_merge_log (
    id SERIAL PRIMARY KEY,
    merge_run_id UUID NOT NULL,  -- Group related merges
    entity_type VARCHAR(50) NOT NULL,  -- 'contact', 'organization', 'bill'
    bronze_table VARCHAR(100) NOT NULL,
    bronze_record_id INTEGER NOT NULL,
    production_table VARCHAR(100) NOT NULL,
    production_record_id INTEGER,  -- NULL if no match found
    
    -- Match details
    match_type VARCHAR(50),  -- 'exact_id', 'name_jurisdiction', 'fuzzy', 'none'
    match_confidence FLOAT,  -- Similarity score
    action_taken VARCHAR(50),  -- 'inserted', 'updated', 'skipped', 'needs_review'
    
    -- Metadata
    merged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    merged_by VARCHAR(100) DEFAULT CURRENT_USER
);

CREATE INDEX idx_merge_log_run ON bronze_merge_log(merge_run_id);
CREATE INDEX idx_merge_log_entity ON bronze_merge_log(entity_type);
CREATE INDEX idx_merge_log_action ON bronze_merge_log(action_taken);
CREATE INDEX idx_merge_log_needs_review ON bronze_merge_log(action_taken) WHERE action_taken = 'needs_review';

COMMENT ON TABLE bronze_merge_log IS 'Audit log for bronze → production merges';


COMMIT;

-- ============================================================================
-- SUMMARY
-- ============================================================================

SELECT 
    'Migration complete!' as status,
    COUNT(*) as total_contacts,
    SUM(CASE WHEN datasource = 'openstates_api' THEN 1 ELSE 0 END) as openstates,
    SUM(CASE WHEN datasource = 'irs_990' THEN 1 ELSE 0 END) as irs_990,
    SUM(CASE WHEN datasource = 'localview' THEN 1 ELSE 0 END) as localview,
    SUM(CASE WHEN datasource = 'unknown' THEN 1 ELSE 0 END) as unknown
FROM contact;

\echo ''
\echo '✅ Datasource tracking fields added to all tables'
\echo '✅ Junction tables created for many-to-many relationships'
\echo '✅ Merge log table created for debugging'
\echo ''
\echo 'Next steps:'
\echo '  1. Run bronze extraction: python scripts/datasources/gemini/load_meeting_transcripts_bronze.py'
\echo '  2. Run merge script: python scripts/datasources/gemini/merge_bronze_to_production.py'
\echo ''
