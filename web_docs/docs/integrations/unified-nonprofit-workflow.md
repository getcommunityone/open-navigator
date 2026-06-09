---
title: Unified Nonprofit Data Management
---

# Unified Nonprofit Data Management

**Single Source of Truth**: `data/gold/nonprofits_organizations.parquet`

## 🎯 **New Workflow**

### ✅ **DO THIS** (Single Unified File)

```bash
# Check stats
python scripts/manage_nonprofits.py stats

# Enrich a subset (updates main file in place)
python scripts/manage_nonprofits.py enrich-990 --states AL --sample 100

# Enrich specific orgs
python scripts/manage_nonprofits.py enrich-990 --ein-list eins.txt

# Enrich all Alabama + Michigan health nonprofits
python scripts/manage_nonprofits.py enrich-990 --states AL MI --ntee E

# BigQuery enrichment
python scripts/manage_nonprofits.py enrich-bigquery --states AL
# ... run SQL in BigQuery web UI, export CSV ...
python scripts/manage_nonprofits.py merge-bigquery
```

### ❌ **DON'T DO THIS** (Creates Separate Files)

```bash
# OLD WAY - Creates proliferation of files
python scripts/enrich_nonprofits_gt990.py \
    --input data/gold/nonprofits_tuscaloosa.parquet \
    --output data/gold/nonprofits_tuscaloosa_form990.parquet  # ❌ Extra file!
```

## 📊 **Key Commands**

### Show Statistics

```bash
python scripts/manage_nonprofits.py stats
```

Output:
```
📊 TOTAL: 1,952,238 organizations
💰 ENRICHMENT STATUS:
   Form 990 data: 307 (0.0%)
   BigQuery data: 0 (0.0%)
📝 MISSION STATEMENTS:
   At least one source: 299 (0.0%)
```

### Enrich Incrementally

**By State:**
```bash
python scripts/manage_nonprofits.py enrich-990 --states AL
# Updates main file with 62K Alabama nonprofits enriched
```

**By NTEE Category:**
```bash
python scripts/manage_nonprofits.py enrich-990 --ntee E
# Updates main file with 45K health nonprofits enriched
```

**Combined Filters:**
```bash
python scripts/manage_nonprofits.py enrich-990 --states AL MI --ntee E
# Updates main file with Alabama + Michigan health orgs
```

**Test on Sample:**
```bash
python scripts/manage_nonprofits.py enrich-990 --sample 100
# Updates main file with 100 random orgs enriched (for testing)
```

**Specific EINs:**
```bash
# Create file with EINs (one per line)
echo "631024890" > eins.txt
echo "631041304" >> eins.txt

python scripts/manage_nonprofits.py enrich-990 --ein-list eins.txt
```

## 🔄 **How In-Place Updates Work**

1. **Load** full dataset (1.9M orgs)
2. **Filter** to subset (e.g., Alabama = 62K orgs)
3. **Enrich** only the filtered subset
4. **Merge** back:
   - Remove old data for those EINs
   - Add newly enriched data
   - Sort by EIN
5. **Save** back to same file

**Result:** Only one file, incrementally enriched!

## 🗑️ **Cleanup Old Files**

### Preview Cleanup (Dry Run)

```bash
python scripts/cleanup_nonprofit_files.py
```

Output:
```
🔄 Found enriched data: nonprofits_tuscaloosa_form990.parquet
   ✅ Merged 921 enriched organizations

🗑️  Found 9 file(s) to clean up:
   - nonprofits_tuscaloosa.parquet (0.0 MB)
   - nonprofits_tuscaloosa_form990.parquet (0.1 MB)
   - /tmp/test_*.parquet (0.1 MB)
   
⚠️  DRY RUN - No files will be deleted
   Run with --execute to actually delete files
```

### Execute Cleanup

```bash
python scripts/cleanup_nonprofit_files.py --execute
```

**What it does:**
- ✅ Merges any enrichment from old files into main file
- ✅ Deletes old/redundant files
- ✅ Leaves only `data/gold/nonprofits_organizations.parquet`

## 📁 **File Organization**

### ✅ **Keep (Single Source of Truth)**

```
data/gold/nonprofits_organizations.parquet  # 1.9M orgs, incrementally enriched
```

### 🗑️ **Remove (Old Workflow)**

```
data/gold/nonprofits_tuscaloosa.parquet              # ❌ Subset
data/gold/nonprofits_tuscaloosa_form990.parquet      # ❌ Enriched subset  
data/gold/nonprofits_990_enriched.parquet            # ❌ Another version
/tmp/test_*.parquet                                   # ❌ Test files
```

## 🎨 **Progressive Enrichment Strategy**

Enrich the dataset progressively to avoid overwhelming API limits:

### Phase 1: Test Sample (TODAY)
```bash
python scripts/manage_nonprofits.py enrich-990 --sample 1000
# Test with 1K random orgs
```

### Phase 2: Priority States (WEEK 1)
```bash
python scripts/manage_nonprofits.py enrich-990 --states AL MI
# Enrich Alabama + Michigan (118K orgs)
```

### Phase 3: Priority NTEE (WEEK 2)
```bash
python scripts/manage_nonprofits.py enrich-990 --ntee E P
# Health + Human Services (199K orgs)
```

### Phase 4: Remaining States (MONTH 1)
```bash
# Enrich 5-10 states per day
for state in CA TX NY FL PA; do
    python scripts/manage_nonprofits.py enrich-990 --states $state
    echo "Completed $state"
    sleep 3600  # Wait 1 hour between states
done
```

### Phase 5: BigQuery Layer (MONTH 2)
```bash
# Add missions + websites from BigQuery
python scripts/manage_nonprofits.py enrich-bigquery
# ... export CSV ...
python scripts/manage_nonprofits.py merge-bigquery
```

## 🔍 **Advanced Usage**

### Check Enrichment Status by State

```bash
python -c "
import pandas as pd
df = pd.read_parquet('data/gold/nonprofits_organizations.parquet')
enriched = df[df['form_990_status'] == 'found']
by_state = enriched.groupby('state').size().sort_values(ascending=False).head(10)
print('Top 10 states by Form 990 coverage:')
print(by_state)
"
```

### Export EINs Needing Enrichment

```bash
python -c "
import pandas as pd
df = pd.read_parquet('data/gold/nonprofits_organizations.parquet')
# Alabama health orgs without 990 data
needs_enrichment = df[
    (df['state'] == 'AL') & 
    (df['ntee_code'].str.startswith('E', na=False)) &
    (df['form_990_status'].isna())
]['ein']
needs_enrichment.to_csv('alabama_health_needs_enrichment.txt', index=False, header=False)
print(f'Exported {len(needs_enrichment)} EINs')
"
```

## 💡 **Benefits of Unified File**

1. ✅ **Single source of truth** - No confusion about which file is current
2. ✅ **Incremental updates** - Add enrichment data without duplicating base data
3. ✅ **Smaller disk usage** - No duplicate base data across files
4. ✅ **Easier tracking** - One file to track, version, backup
5. ✅ **Simpler workflows** - No need to manage file versions
6. ✅ **Better for git** - One file to track changes in (with git-lfs)

## 📝 **Migration Checklist**

- [x] **Merge** existing enrichment data into main file
- [x] **Verify** enrichment was merged (run `stats`)
- [ ] **Clean up** old files with `--execute`
- [ ] **Update** any scripts/docs referencing old files
- [ ] **Test** new workflow with small sample
- [ ] **Document** team workflow

## 🆘 **Troubleshooting**

### "Main file not found"

```bash
# Create main file from EO-BMF data
python pipeline/create_gold_tables.py --nonprofits-only
```

### "Lost my enrichment data!"

Don't worry! Run cleanup script first (without `--execute`) - it will merge any enrichment data before deleting files.

### "Want to keep a backup"

```bash
# Backup before cleanup
cp data/gold/nonprofits_organizations.parquet \
   data/gold/nonprofits_organizations.$(date +%Y%m%d).parquet.bak
```

## 📚 **Related Documentation**

- [Form 990 Enrichment](../data-sources/form-990-xml.md)
- [BigQuery Integration](./bigquery-enrichment.md)
- [Charity Navigator](../data-sources/charity-navigator.md)
