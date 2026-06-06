# Bronze to Production Merge - Quick Start

## 🚀 Overview

Merge AI-extracted data from Bronze tables (meeting transcript analysis) into production search tables with automatic deduplication and entity resolution.

## 📋 Prerequisites

1. ✅ Bronze tables populated with AI extractions
2. ✅ Production Neon database accessible
3. ✅ Schema migration applied

## 🔧 Step-by-Step Workflow

### 1. Apply Schema Migration (One-time)

Add datasource tracking fields to production tables:

```bash
# Apply migration
psql $NEON_DATABASE_URL_DEV -f packages/hosting/scripts/neon/migrations/001_add_datasource_fields.sql

# If needed, rollback
psql $NEON_DATABASE_URL_DEV -f packages/hosting/scripts/neon/migrations/001_add_datasource_fields_rollback.sql
```

**What this does:**
- Adds `datasource`, `datasource_id`, `confidence_score`, `verified` fields to all search tables
- Creates junction tables: `bills_meetings`, `contacts_meeting_attendance`, `organizations_meetings`
- Creates `bronze_merge_log` for debugging

### 2. Extract Meeting Transcripts to Bronze

Run AI analysis on meeting transcripts:

```bash
# Extract from events_text_ai to bronze tables
python -m llm.enrichment.load_meeting_transcripts_bronze

# Check what was extracted
python -m llm.enrichment.load_meeting_transcripts_bronze --create-tables-only
```

**Bronze tables created:**
- `bronze_contacts` - People mentioned (officials, lobbyists, citizens)
- `bronze_organizations` - Organizations mentioned
- `bronze_bills` - Legislation discussed
- `bronze_financial_items` - Budget items, grants, contracts

### 3. Merge Bronze → Production (DRY RUN)

Preview what would be merged:

```bash
# Dry run - show what would happen
python -m llm.enrichment.merge_bronze_to_production --dry-run

# Dry run for contacts only
python -m llm.enrichment.merge_bronze_to_production --entity contacts --dry-run
```

### 4. Run Actual Merge

Merge with entity resolution:

```bash
# Merge contacts only
python -m llm.enrichment.merge_bronze_to_production --entity contacts

# Merge all entities (contacts, organizations, bills)
python -m llm.enrichment.merge_bronze_to_production --all
```

**Entity Resolution:**
- ✅ Exact match on IDs (Wikidata QID, OpenStates ID, EIN)
- ✅ Exact match on name + jurisdiction
- ✅ Fuzzy match with similarity threshold (0.85+)
- ✅ Phonetic match (Soundex)
- ✅ Conflict resolution (prioritize authoritative sources)

### 5. Review Duplicates/Conflicts

Generate report of records needing manual review:

```bash
python -m llm.enrichment.merge_bronze_to_production --report-duplicates
```

**What gets flagged:**
- Fuzzy matches with score 0.85-0.95 (uncertain)
- Multiple potential matches (needs human decision)
- Conflicts with existing authoritative data

### 6. Query Merged Data

```sql
-- View all AI-extracted contacts
SELECT name, title, organization_name, datasource, confidence_score
FROM contact
WHERE datasource = 'gemini_ai_extraction'
ORDER BY confidence_score DESC;

-- View contacts needing review
SELECT name, title, organization_name, review_notes
FROM contact
WHERE needs_review = TRUE;

-- View which bills were discussed in which meetings
SELECT 
    b.bill_number, b.title,
    e.event_title as meeting_title, e.event_date,
    bm.action_taken, bm.vote_result
FROM bills_meetings bm
JOIN bills_search b ON bm.bill_id = b.id
JOIN event e ON bm.event_id = e.event_id
WHERE bm.datasource = 'gemini_ai_extraction'
ORDER BY e.event_date DESC;

-- View lobbyist activity in meetings
SELECT 
    c.name, c.title,
    e.event_title as meeting,
    cma.appeared_as,
    cma.lobbyist_registration_number
FROM contacts_meeting_attendance cma
JOIN contact c ON cma.contact_id = c.id
JOIN event e ON cma.event_id = e.event_id
WHERE cma.is_lobbyist = TRUE
ORDER BY e.event_date DESC;
```

## 📊 Data Quality Tiers

| Tier | Score | Datasource | Display |
|------|-------|------------|---------|
| **Authoritative** | 1.0 | `openstates_api`, `irs_bmf`, `irs_990` | Show without warnings |
| **High Quality** | 0.90-0.99 | `localview`, `youtube_api` | Minor disclaimer |
| **Medium Quality** | 0.70-0.89 | Manual entry, YouTube metadata | "Unverified" badge |
| **AI Extracted** | 0.50-0.69 | `gemini_ai_extraction` | "AI-generated" disclaimer |
| **Low Quality** | < 0.50 | Unverified submissions | Hide by default |

## 🔄 Reload Strategy

To reload data from a specific source:

```python
# Reload all contacts from OpenStates
UPDATE contact 
SET verified = FALSE 
WHERE datasource = 'openstates_api';

# Re-run load script
python scripts/datasources/openstates/load_openstates_people.py

# Any old records not updated are now marked unverified
```

## 🐛 Troubleshooting

### "Too many duplicates created"

**Cause:** Entity resolution thresholds too low
**Fix:** Increase similarity threshold in merge script:

```python
# In merge_bronze_to_production.py
fuzzy_matches = ContactMatcher.fuzzy_match(
    dict(bronze_contact),
    [dict(c) for c in prod_candidates],
    threshold=0.90  # Increase from 0.85 to be more strict
)
```

### "Authoritative data was overwritten"

**Cause:** Merge logic didn't respect datasource priority
**Check:** Review merge log:

```sql
SELECT * FROM bronze_merge_log
WHERE action_taken = 'updated'
  AND production_record_id IN (
    SELECT id FROM contact 
    WHERE datasource IN ('openstates_api', 'irs_990')
  );
```

### "Missing relationships (bills not linked to meetings)"

**Cause:** Bill merge didn't create junction table entries
**Check:**

```sql
SELECT COUNT(*) FROM bills_meetings;

-- Should have entries for bronze_bills with source_event_id
SELECT COUNT(*) FROM bronze_bills WHERE source_event_id IS NOT NULL;
```

## 📁 File Structure

```
llm/enrichment/
├── load_meeting_transcripts_bronze.py  # Extract from events_text_ai → bronze
├── entity_resolution.py                # Fuzzy matching logic
├── merge_bronze_to_production.py       # Main merge script
└── README.md                           # This file

packages/hosting/scripts/neon/migrations/
├── 001_add_datasource_fields.sql
└── 001_add_datasource_fields_rollback.sql

website/docs/development/
└── bronze-to-production-merge.md       # Full strategy guide
```

## ⏭️ Next Steps

1. **Implement Organizations Merge**
   - Match by EIN (exact)
   - Match by name (fuzzy)
   - Create `organizations_meetings` junction entries

2. **Implement Bills Merge**
   - Match by OpenStates bill_id (exact)
   - Match by jurisdiction + session + bill_number
   - Detect local ordinances (not in OpenStates)
   - Create `bills_meetings` junction entries

3. **Create Deduplication Dashboard**
   - Web UI for reviewing flagged duplicates
   - Side-by-side comparison
   - Merge/reject actions

4. **Add Verification Workflow**
   - Flag high-value records for human verification
   - Track verifier and verification date
   - Promote verified records to higher confidence

## 📚 Related Documentation

- [Bronze to Production Merge Strategy](../../website/docs/development/bronze-to-production-merge.md) - Full guide
- [Data Sources](../../docs/DATA_SOURCES.md) - All data sources and formats
- [Gold Table Consolidation](../../website/docs/development/gold-consolidation.md) - Parquet file structure
