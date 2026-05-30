---
sidebar_position: 10
---

# Bronze to Production Merge Strategy

## Overview

This guide explains how to merge AI-extracted data from Bronze tables (meeting transcript analysis) with production search tables in Neon PostgreSQL.

## Problem Statement

**Bronze tables** contain AI-extracted entities from meeting transcripts:
- `bronze_contacts` - People mentioned in meetings (officials, lobbyists, citizens)
- `bronze_organizations` - Organizations mentioned
- `bronze_bills` - Legislation discussed
- `bronze_decisions` - Policy decisions made
- `bronze_financial_items` - Budget items, grants, contracts

**Production tables** contain curated data from authoritative sources:
- `contact` - State legislators (OpenStates), nonprofit officers (IRS 990s), local officials
- `organization_nonprofit` - IRS Business Master File nonprofits
- `bills_search` - State legislation from OpenStates API
- `event` - Meeting metadata from LocalView/YouTube

**Challenge**: How to merge AI-extracted data (noisy, unverified) with production data (authoritative, clean) without:
- Creating duplicates
- Losing data provenance (knowing where each record came from)
- Corrupting authoritative data with AI hallucinations

## Solution: Multi-Source Data Management

### 1. Add `datasource` Field to All Production Tables

**Schema Changes Required:**

```sql
-- Add datasource column to track data origin
ALTER TABLE contact 
  ADD COLUMN IF NOT EXISTS datasource VARCHAR(100) DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS datasource_id VARCHAR(255),  -- ID in source system
  ADD COLUMN IF NOT EXISTS confidence_score FLOAT,      -- AI confidence (0.0-1.0)
  ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE,  -- Human-verified?
  ADD COLUMN IF NOT EXISTS verification_date TIMESTAMP;

ALTER TABLE organization_nonprofit
  ADD COLUMN IF NOT EXISTS datasource VARCHAR(100) DEFAULT 'irs_bmf',
  ADD COLUMN IF NOT EXISTS datasource_id VARCHAR(255),
  ADD COLUMN IF NOT EXISTS confidence_score FLOAT,
  ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS verification_date TIMESTAMP;

ALTER TABLE bills_search
  ADD COLUMN IF NOT EXISTS datasource VARCHAR(100) DEFAULT 'openstates_api',
  ADD COLUMN IF NOT EXISTS datasource_id VARCHAR(255),
  ADD COLUMN IF NOT EXISTS confidence_score FLOAT,
  ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS verification_date TIMESTAMP;

ALTER TABLE event
  ADD COLUMN IF NOT EXISTS datasource VARCHAR(100) DEFAULT 'localview',
  ADD COLUMN IF NOT EXISTS datasource_id VARCHAR(255),
  ADD COLUMN IF NOT EXISTS confidence_score FLOAT;
```

**Datasource Values:**

| Datasource | Confidence | Description |
|------------|-----------|-------------|
| `openstates_api` | 1.0 | OpenStates API (authoritative) |
| `irs_bmf` | 1.0 | IRS Business Master File (authoritative) |
| `irs_990` | 1.0 | IRS Form 990 filings (authoritative) |
| `localview` | 0.95 | LocalView structured data (high quality) |
| `youtube_metadata` | 0.90 | YouTube metadata (mostly accurate) |
| `gemini_ai_extraction` | 0.60 | AI extraction from transcripts (needs verification) |
| `manual_entry` | 0.80 | Human-entered data (varies) |

### 2. Create Deduplication & Merge Logic

#### A. Entity Resolution for Contacts

**Matching Strategy:**

1. **Exact Match** (High confidence)
   - `full_name` + `jurisdiction` (for local officials)
   - `full_name` + `organization_ein` (for nonprofit officers)
   - `person_id` (if using Wikidata QID or OpenStates ID)

2. **Fuzzy Match** (Medium confidence)
   - Normalized name similarity (Levenshtein distance < 3)
   - Same role type + same organization
   - Same address or phone number

3. **No Match** (Insert as new record)
   - Flag with low confidence score
   - Mark as `verified = FALSE`

**Example Merge Logic:**

```python
def merge_contact_from_bronze(bronze_contact, production_db):
    """
    Merge a bronze_contact record into contact table
    
    Args:
        bronze_contact: Row from bronze_contacts table
        production_db: Connection to Neon production DB
    
    Returns:
        (action, contact_id) where action is 'inserted', 'updated', or 'skipped'
    """
    # Step 1: Try exact match on Wikidata QID (if available)
    if bronze_contact.get('wikidata_qid'):
        existing = find_contact_by_datasource_id(
            production_db,
            datasource='wikidata',
            datasource_id=bronze_contact['wikidata_qid']
        )
        if existing:
            # Update if AI extraction has newer info
            if bronze_contact['extracted_at'] > existing['last_updated']:
                update_contact_from_bronze(production_db, existing['id'], bronze_contact)
                return ('updated', existing['id'])
            return ('skipped', existing['id'])
    
    # Step 2: Try exact match on name + jurisdiction
    existing = find_contact_by_name_jurisdiction(
        production_db,
        name=normalize_name(bronze_contact['full_name']),
        jurisdiction=bronze_contact.get('jurisdiction'),
        org_ein=bronze_contact.get('ein')
    )
    
    if existing:
        # CONFLICT: Decide which source to trust
        if existing['datasource'] in ['openstates_api', 'irs_990']:
            # Don't override authoritative sources with AI extraction
            log.info(f"Skipping update - authoritative source exists: {existing['datasource']}")
            return ('skipped', existing['id'])
        
        elif existing['confidence_score'] < 0.70:
            # Replace low-confidence records with AI extraction
            update_contact_from_bronze(production_db, existing['id'], bronze_contact)
            return ('updated', existing['id'])
    
    # Step 3: Try fuzzy match
    candidates = find_similar_contacts(
        production_db,
        name=bronze_contact['full_name'],
        threshold=0.85  # 85% similarity
    )
    
    if candidates:
        # Log for human review
        log.warning(f"Potential duplicates found for {bronze_contact['full_name']}")
        log.warning(f"Candidates: {candidates}")
        
        # Insert anyway but mark for review
        contact_id = insert_contact_from_bronze(
            production_db,
            bronze_contact,
            needs_review=True
        )
        return ('inserted_needs_review', contact_id)
    
    # Step 4: No match - insert as new
    contact_id = insert_contact_from_bronze(production_db, bronze_contact)
    return ('inserted', contact_id)
```

#### B. Entity Resolution for Bills

**Matching Strategy:**

1. **Exact Match**
   - `bill_id` from OpenStates (format: `ocd-bill/state-session-billnumber`)
   - `jurisdiction` + `session` + `bill_number`

2. **Fuzzy Match**
   - Title similarity + same state + same year
   - Official number match (e.g., "HB 123" = "House Bill 123")

3. **Local Bills** (Not in OpenStates)
   - Many local ordinances discussed in meetings aren't tracked by OpenStates
   - Insert with `datasource='gemini_ai_extraction'` and low confidence

**Example Merge Logic:**

```python
def merge_bill_from_bronze(bronze_bill, production_db):
    """
    Merge a bronze_bill record into bills_search table
    """
    # Step 1: Try exact match on bill_id (if AI extracted OpenStates ID)
    if bronze_bill.get('leg_id') and bronze_bill['leg_id'].startswith('ocd-bill/'):
        existing = find_bill_by_id(production_db, bronze_bill['leg_id'])
        if existing:
            # Bill already in DB from OpenStates - enhance with meeting context
            add_meeting_context_to_bill(
                production_db,
                bill_id=existing['id'],
                event_id=bronze_bill['source_event_id'],
                relevance=bronze_bill['relevance']
            )
            return ('enhanced', existing['id'])
    
    # Step 2: Try match on jurisdiction + session + bill_number
    if bronze_bill.get('official_number'):
        existing = find_bill_by_number(
            production_db,
            jurisdiction=bronze_bill['jurisdiction'],
            year=bronze_bill['year'],
            bill_number=normalize_bill_number(bronze_bill['official_number'])
        )
        if existing:
            add_meeting_context_to_bill(
                production_db,
                bill_id=existing['id'],
                event_id=bronze_bill['source_event_id'],
                relevance=bronze_bill['relevance']
            )
            return ('enhanced', existing['id'])
    
    # Step 3: Local ordinance or resolution (not tracked by OpenStates)
    # These are valuable - insert with low confidence
    bill_id = insert_bill_from_bronze(
        production_db,
        bronze_bill,
        datasource='gemini_ai_extraction',
        confidence_score=0.60
    )
    return ('inserted_local', bill_id)
```

### 3. Create Junction Tables for Provenance

Some entities benefit from many-to-many relationships to preserve provenance:

```sql
-- Track which meetings discussed which bills
CREATE TABLE IF NOT EXISTS bills_meetings (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER REFERENCES bills_search(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES event(event_id) ON DELETE CASCADE,
    
    -- Context from AI analysis
    relevance TEXT,
    action_taken VARCHAR(100),  -- 'passed', 'tabled', 'discussed', 'voted_on'
    vote_result VARCHAR(50),    -- 'approved', 'rejected', 'no_action'
    
    -- Metadata
    datasource VARCHAR(100) DEFAULT 'gemini_ai_extraction',
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(bill_id, event_id)
);

-- Track which contacts attended which meetings
CREATE TABLE IF NOT EXISTS contacts_meeting_attendance (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER REFERENCES contact(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES event(event_id) ON DELETE CASCADE,
    
    -- Role in this specific meeting
    appeared_as VARCHAR(100),  -- 'speaker', 'council_member', 'witness', 'lobbyist'
    title_at_time VARCHAR(200),
    
    -- Metadata
    datasource VARCHAR(100) DEFAULT 'gemini_ai_extraction',
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(contact_id, event_id)
);

-- Track which organizations were mentioned in which meetings
CREATE TABLE IF NOT EXISTS organizations_meetings (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organization_nonprofit(ein) ON DELETE CASCADE,
    event_id INTEGER REFERENCES event(event_id) ON DELETE CASCADE,
    
    -- Context
    role_in_meeting TEXT,
    financial_interest TEXT,
    
    -- Metadata
    datasource VARCHAR(100) DEFAULT 'gemini_ai_extraction',
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(organization_id, event_id)
);
```

### 4. Merge Script Implementation

**Location:** `scripts/datasources/gemini/merge_bronze_to_production.py`

**Key Features:**
1. Idempotent - can run multiple times safely
2. Incremental - only processes new records since last sync
3. Resumable - tracks progress in case of failure
4. Reviewable - generates report of conflicts/duplicates

**Usage:**

```bash
# Dry run (show what would be merged)
python scripts/datasources/gemini/merge_bronze_to_production.py --dry-run

# Merge contacts only
python scripts/datasources/gemini/merge_bronze_to_production.py --entity contacts

# Merge all entities
python scripts/datasources/gemini/merge_bronze_to_production.py --all

# Generate deduplication report
python scripts/datasources/gemini/merge_bronze_to_production.py --report-duplicates
```

## Data Quality Tiers

Use `confidence_score` to classify data quality:

| Tier | Score | Source Examples | Usage |
|------|-------|-----------------|-------|
| **Authoritative** | 1.0 | OpenStates API, IRS BMF | Display without warnings |
| **High Quality** | 0.90-0.99 | LocalView structured data | Display with minor disclaimers |
| **Medium Quality** | 0.70-0.89 | YouTube metadata, manual entry | Display with "unverified" badge |
| **AI Extracted** | 0.50-0.69 | Gemini AI from transcripts | Show with "AI-generated" disclaimer |
| **Low Quality** | < 0.50 | Unverified user submissions | Hide by default, manual review |

## UI Implications

**Frontend Search Results:**

```jsx
// Example: Contact search result with datasource badge
function ContactCard({ contact }) {
  const badges = {
    'openstates_api': { label: 'Official Data', color: 'green' },
    'irs_990': { label: 'IRS Verified', color: 'green' },
    'gemini_ai_extraction': { label: 'AI Extracted', color: 'yellow' },
    'manual_entry': { label: 'Unverified', color: 'gray' }
  };
  
  const badge = badges[contact.datasource] || badges['manual_entry'];
  
  return (
    <div className="contact-card">
      <h3>{contact.name}</h3>
      <p>{contact.title} - {contact.organization_name}</p>
      <span className={`badge badge-${badge.color}`}>
        {badge.label}
      </span>
      {contact.confidence_score < 0.70 && (
        <p className="warning">
          ⚠️ This information has not been verified
        </p>
      )}
    </div>
  );
}
```

## Reload Strategy

**Handling Data Reloads:**

```python
def reload_datasource(datasource_name):
    """
    Reload all records from a specific datasource
    
    Args:
        datasource_name: 'openstates_api', 'irs_bmf', 'gemini_ai_extraction', etc.
    """
    # Step 1: Mark all existing records from this source for review
    UPDATE contact 
    SET verified = FALSE, last_updated = NOW()
    WHERE datasource = datasource_name
    
    # Step 2: Reload from source
    if datasource_name == 'openstates_api':
        run_openstates_load()
    elif datasource_name == 'gemini_ai_extraction':
        run_bronze_extraction()
        run_bronze_merge()
    
    # Step 3: Any records not touched in reload are marked as stale
    UPDATE contact
    SET verified = FALSE
    WHERE datasource = datasource_name 
      AND last_updated < (NOW() - INTERVAL '1 hour')
```

## Next Steps

1. ✅ Create schema migration to add datasource fields
2. ✅ Update existing load scripts to populate datasource
3. ⏳ Implement entity resolution functions (contacts, bills, organizations)
4. ⏳ Create merge_bronze_to_production.py script
5. ⏳ Update frontend to display datasource badges
6. ⏳ Create deduplication review dashboard

## Related Files

- Bronze extraction: `scripts/datasources/gemini/load_meeting_transcripts_bronze.py`
- Production schema: `packages/hosting/src/hosting/neon/schema.sql`
- Production loader: `packages/hosting/src/hosting/neon/migrate.py`
- Entity resolution (to be created): `scripts/datasources/gemini/entity_resolution.py`
- Merge script (to be created): `scripts/datasources/gemini/merge_bronze_to_production.py`
