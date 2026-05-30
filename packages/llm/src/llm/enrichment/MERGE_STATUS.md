# Bronze to Production Merge - Current Status

## 📊 Current State

### ✅ Completed

**1. Bronze Data Loaded**
- ✅ 382 contacts extracted from meeting transcripts
- ✅ 185 organizations identified
- ✅ 22 bills/legislation tracked
- ✅ 157 policy decisions recorded
- ✅ 20 financial items cataloged

**2. Infrastructure Created**
- ✅ Entity resolution module: `scripts/datasources/gemini/entity_resolution.py`
  - Name normalization (lowercase, trim, remove punctuation)
  - Soundex phonetic matching
  - Fuzzy text similarity (SequenceMatcher)
  - Bill number normalization
  
- ✅ Merge script: `scripts/datasources/gemini/merge_bronze_to_production.py`
  - **Contacts merge** - Full entity resolution with fuzzy matching
  - **Organizations merge** - EIN matching, name fuzzy matching, meeting context
  - **Bills merge** - OpenStates ID matching, local ordinance detection
  - Dry-run mode for testing
  - Conflict resolution logic
  - Audit logging to bronze_merge_log table
  
- ✅ Schema migration: `scripts/deployment/neon/migrations/001_add_datasource_fields.sql`
  - Adds datasource tracking columns
  - Creates junction tables (bills_meetings, contacts_meeting_attendance, organizations_meetings)
  - Creates merge audit log table
  
- ✅ Automated workflow: `scripts/datasources/gemini/run_bronze_merge.sh`
  - Step-by-step guided process
  - Dry-run before actual merge
  - Results verification

**3. Documentation**
- ✅ Complete strategy guide: `website/docs/development/bronze-to-production-merge.md`
- ✅ Quick start: `scripts/datasources/gemini/README_BRONZE_MERGE.md`
- ✅ This status doc: `scripts/datasources/gemini/MERGE_STATUS.md`

**4. dbt Integration**
- ✅ dbt project structure: `dbt_project/`
- ✅ Staging models for bronze tables
- ✅ Incremental production models
- ✅ Data quality tests

### ⏳ Ready to Run

**All merge logic is implemented!** You can now merge:
- ✅ **Contacts** (382 records) - Fully implemented
- ✅ **Organizations** (185 records) - Fully implemented
- ✅ **Bills** (22 records) - Fully implemented

**1. Apply Schema Migration**
```bash
# Run this ONCE to add datasource columns
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator \
  -f scripts/deployment/neon/migrations/001_add_datasource_fields.sql
```

**2. Run Merge (First Time)**
```bash
# Option A: Use automated workflow (recommended)
./scripts/datasources/gemini/run_bronze_merge.sh

# Option B: Manual - merge all entities
python scripts/datasources/gemini/merge_bronze_to_production.py --all

# Option C: Manual - merge one at a time
python scripts/datasources/gemini/merge_bronze_to_production.py --entity contacts
python scripts/datasources/gemini/merge_bronze_to_production.py --entity organizations
python scripts/datasources/gemini/merge_bronze_to_production.py --entity bills
```

### 🚧 Future Enhancements

**1. Deduplication Dashboard**
- Web UI for reviewing flagged duplicates
- Side-by-side comparison
- Merge/reject actions

**2. Advanced Entity Resolution**
- Machine learning for fuzzy matching
- Cross-reference validation
- Confidence score tuning

**3. Incremental Processing**
- Automated daily/hourly runs
- Only process new bronze records
- Change data capture (CDC)

## 🚀 How to Run (Quick Start)

### Method 1: Automated Workflow (Recommended)

```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate

# Run the complete workflow (interactive)
./scripts/datasources/gemini/run_bronze_merge.sh
```

This script will:
1. ✅ Check bronze data counts
2. ✅ Apply schema migration (asks permission)
3. ✅ Run dry-run merge
4. ✅ Ask to proceed with actual merge
5. ✅ Show results by datasource
6. ✅ Optional: Generate duplicate report

### Method 2: Manual Steps

```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate

# 1. Apply migration (one-time)
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator \
  -f scripts/deployment/neon/migrations/001_add_datasource_fields.sql

# 2. Test merge (dry-run)
python scripts/datasources/gemini/merge_bronze_to_production.py --dry-run --entity contacts

# 3. Run actual merge
python scripts/datasources/gemini/merge_bronze_to_production.py --entity contacts

# 4. Check results
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator -c "
  SELECT datasource, COUNT(*), AVG(confidence_score)::NUMERIC(3,2)
  FROM contact
  GROUP BY datasource
  ORDER BY COUNT(*) DESC;
"

# 5. Review duplicates (optional)
python scripts/datasources/gemini/merge_bronze_to_production.py --report-duplicates
```

### Method 3: Using dbt (Alternative)

```bash
cd dbt_project

# 1. Install dbt (one-time)
./setup.sh

# 2. Run transformations
dbt run --select staging+
dbt run --select intermediate+
dbt run --select marts+

# 3. Run tests
dbt test

# 4. View documentation
dbt docs generate && dbt docs serve
```

## 📊 Expected Results

After running the merge, you should see:

```sql
-- Production contacts by source
SELECT 
    datasource,
    COUNT(*) as contact_count,
    AVG(confidence_score)::NUMERIC(3,2) as avg_confidence,
    SUM(CASE WHEN needs_review THEN 1 ELSE 0 END) as needs_review_count
FROM contact
GROUP BY datasource
ORDER BY contact_count DESC;

-- Example output:
--  datasource              | contact_count | avg_confidence | needs_review_count
-- -------------------------+---------------+----------------+-------------------
--  openstates_api          |         1,234 |           1.00 |                  0
--  irs_990                 |         5,678 |           1.00 |                  0
--  gemini_ai_extraction    |           382 |           0.60 |                 15
--  localview               |           456 |           0.70 |                  5
```

## 🐛 Troubleshooting

### Issue: "relation 'bronze_contacts' does not exist"

**Cause:** Bronze tables not loaded yet

**Fix:**
```bash
python scripts/datasources/gemini/load_meeting_transcripts_bronze.py
```

### Issue: "column 'datasource' does not exist"

**Cause:** Schema migration not applied

**Fix:**
```bash
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator \
  -f scripts/deployment/neon/migrations/001_add_datasource_fields.sql
```

### Issue: "Too many duplicates created"

**Cause:** Entity resolution threshold too low

**Fix:** Edit `merge_bronze_to_production.py` and increase threshold:
```python
fuzzy_matches = ContactMatcher.fuzzy_match(
    dict(bronze_contact),
    [dict(c) for c in prod_candidates],
    threshold=0.90  # Increase from 0.85
)
```

### Issue: "Dry run shows no matches"

**Cause:** Production database empty (no existing contacts)

**Fix:** This is normal for first run. The merge will insert all bronze contacts as new records.

## 📚 Next Steps

After successful merge:

1. **Review flagged duplicates:**
   ```sql
   SELECT * FROM contact WHERE needs_review = TRUE;
   ```

2. **Check merge audit log:**
   ```sql
   SELECT * FROM bronze_merge_log 
   ORDER BY merged_at DESC 
   LIMIT 20;
   ```

3. **Implement organizations merge:**
   - Edit `merge_bronze_to_production.py`
   - Add `merge_organizations()` method
   - Test with `--entity organizations`

4. **Implement bills merge:**
   - Edit `merge_bronze_to_production.py`
   - Add `merge_bills()` method
   - Test with `--entity bills`

5. **Set up incremental updates:**
   - Run merge script on schedule (daily/hourly)
   - Only processes new bronze records since last run

6. **Create deduplication UI:**
   - Web interface for reviewing flagged records
   - Side-by-side comparison
   - One-click merge/reject

## 🔗 Related Files

**Core Implementation:**
- `scripts/datasources/gemini/entity_resolution.py` - Matching logic
- `scripts/datasources/gemini/merge_bronze_to_production.py` - Main merge script
- `scripts/datasources/gemini/load_meeting_transcripts_bronze.py` - Bronze extraction

**Schema:**
- `scripts/deployment/neon/migrations/001_add_datasource_fields.sql` - Add columns
- `scripts/deployment/neon/migrations/001_add_datasource_fields_rollback.sql` - Undo

**Documentation:**
- `website/docs/development/bronze-to-production-merge.md` - Full strategy
- `scripts/datasources/gemini/README_BRONZE_MERGE.md` - Quick start guide
- `website/docs/development/dbt-etl-strategy.md` - dbt integration

**Workflows:**
- `scripts/datasources/gemini/run_bronze_merge.sh` - Automated workflow
- `dbt_project/` - Alternative dbt-based transformation
