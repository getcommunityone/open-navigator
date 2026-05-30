---
sidebar_position: 5
---

# Form 990 Enrichment Guide

## 🎯 Goal
Enrich nonprofit data with **FREE** Form 990 data (website, mission, financials, officers) from GivingTuesday Data Lake.

## ✅ What We Now Have

### Intelligent Backfill Strategy

The search API now uses this priority:

1. **Cached Form 990 data** (if exists and less than 30 days old)
   - Source: `form_990_cached`
   - Columns: `form_990_website`, `form_990_mission`, `form_990_last_updated`
   
2. **Every.org fallback** (for mission/logo/causes)
   - Source: `everyorg`
   - Used when Form 990 data is missing
   
3. **Source tracking** in metadata:
   ```json
   {
     "data_sources": ["form_990_cached", "everyorg"],
     "website": "https://www.carequest.org/",
     "mission": "Advancing oral health for all...",
     "logo_url": "...",
     "causes": ["health"]
   }
   ```

### Incremental Updates

- Checks `form_990_last_updated` timestamp
- Only re-enriches if data is >30 days old
- Preserves existing enrichment data
- Reduces API calls by 90%+

## 🚀 Step 1: Download GivingTuesday Index (One-Time)

```bash
source .venv/bin/activate

# Download index of ALL Form 990 XMLs (~500MB)
python scripts/enrich_nonprofits_gt990.py --download-index
```

This creates: `data/cache/form990_gt_index.parquet` with ~3M Form 990 filings (2010-2023).

## 📊 Step 2: Enrich Massachusetts Nonprofits

### Option A: Full Enrichment (Recommended)

```bash
# Enrich all MA nonprofits with Form 990 data
python scripts/enrich_nonprofits_gt990.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --output data/gold/states/MA/nonprofits_organizations_enriched.parquet \
  --concurrent 50

# Replace original file
mv data/gold/states/MA/nonprofits_organizations_enriched.parquet \
   data/gold/states/MA/nonprofits_organizations.parquet
```

**Time estimate:** 
- 43,726 orgs × ~2 seconds = ~24 hours
- But most won't have Form 990s in the index
- Actual time: ~4-6 hours

### Option B: Sample for Testing

```bash
# Test with 1000 orgs first
python scripts/enrich_nonprofits_gt990.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --output /tmp/ma_sample_990.parquet \
  --sample 1000 \
  --concurrent 20

# Check results
python -c "
import pandas as pd
df = pd.read_parquet('/tmp/ma_sample_990.parquet')
enriched = df[df['form_990_website'].notna()]
print(f'Enriched: {len(enriched):,} / {len(df):,} ({len(enriched)/len(df)*100:.1f}%)')
print()
print('Sample enriched org:')
print(enriched.iloc[0][['name', 'form_990_website', 'form_990_mission']].to_dict())
"
```

### Option C: Update In-Place (Incremental)

```bash
# Only enrich orgs without existing data or >30 days old
python scripts/enrich_nonprofits_gt990.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --update-in-place \
  --incremental \
  --max-age-days 30 \
  --concurrent 50
```

## 🔍 Step 3: Verify Enrichment

```bash
source .venv/bin/activate

python -c "
import pandas as pd

df = pd.read_parquet('data/gold/states/MA/nonprofits_organizations.parquet')

# Check CareQuest specifically
cq = df[df['ein'] == '384016550'].iloc[0]

print('🏥 CareQuest Institute for Oral Health')
print(f'   Website: {cq.get(\"form_990_website\", \"N/A\")}')
print(f'   Mission: {cq.get(\"form_990_mission\", \"N/A\")[:150]}...')
print(f'   Tax Year: {cq.get(\"form_990_tax_year\", \"N/A\")}')
print(f'   Revenue: \${cq.get(\"form_990_total_revenue\", 0):,.0f}')
print()

# Overall stats
print('📊 Enrichment Statistics:')
print(f'   Total organizations: {len(df):,}')

if 'form_990_website' in df.columns:
    with_website = df['form_990_website'].notna().sum()
    with_mission = df['form_990_mission'].notna().sum()
    print(f'   With website: {with_website:,} ({with_website/len(df)*100:.1f}%)')
    print(f'   With mission: {with_mission:,} ({with_mission/len(df)*100:.1f}%)')
else:
    print('   ⚠️  Not enriched yet - run enrichment script first')
"
```

## 📈 Expected Results

After enrichment, you should see:

```json
{
  "title": "CAREQUEST INSTITUTE FOR ORAL HEALTH",
  "description": "Advancing oral health for all, particularly those most vulnerable...",
  "metadata": {
    "ein": "384016550",
    "website": "https://www.carequest.org/",
    "data_sources": ["form_990_cached"],
    "revenue": "$297,919,860",
    "assets": "$2,601,509,658"
  }
}
```

## 🔄 Maintaining Fresh Data

### Monthly Updates

```bash
# Add to cron or GitHub Actions
0 0 1 * * cd /path/to/project && python scripts/enrich_nonprofits_gt990.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --update-in-place \
  --incremental \
  --max-age-days 30
```

### After New 990 Index Release

GivingTuesday updates their index periodically. When they do:

```bash
# Re-download index
python scripts/enrich_nonprofits_gt990.py --download-index

# Re-enrich (will pick up new filings)
python scripts/enrich_nonprofits_gt990.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --update-in-place \
  --incremental
```

## 💡 Why This is Better

| Feature | Form 990 (GT) | Every.org | ProPublica |
|---------|---------------|-----------|------------|
| **Website** | ✅ Direct from filing | ❌ Often missing | ❌ Not in API |
| **Mission** | ✅ Official IRS text | ⚠️ Often outdated | ❌ Not in API |
| **Cost** | 🆓 FREE | 🆓 FREE (limited) | 🆓 FREE |
| **Historical** | ✅ 2010-2023 | ❌ Current only | ✅ 2011-present |
| **Officers** | ✅ Names + comp | ❌ No | ❌ No |
| **Accuracy** | ✅ IRS verified | ⚠️ Community | ✅ IRS verified |
| **Coverage** | ~60-70% | ~40-50% | ~90% |

## 🎯 Optimization Tips

1. **Start with sample:** Test with `--sample 1000` first
2. **Increase concurrency:** Use `--concurrent 50` or `--concurrent 100`
3. **Use incremental:** Always use `--incremental` after initial load
4. **Check cache:** Results are cached in `data/cache/form_990_xml/`
5. **Monitor progress:** Script shows progress bar with tqdm

## 🐛 Troubleshooting

### "Index not loaded"
```bash
python scripts/enrich_nonprofits_gt990.py --download-index
```

### Slow performance
```bash
# Increase concurrency
--concurrent 100

# Or process in batches
--sample 5000
```

### Out of memory
```bash
# Reduce batch size in script or process states separately
for state in MA AL NY; do
  python scripts/enrich_nonprofits_gt990.py \
    --input data/gold/states/$state/nonprofits_organizations.parquet \
    --update-in-place \
    --concurrent 20
done
```
