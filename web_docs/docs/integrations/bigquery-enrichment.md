---
title: BigQuery Nonprofit Enrichment
---

# BigQuery Nonprofit Enrichment

## Overview

Enrich nonprofit data with mission statements and website URLs from Google BigQuery's public IRS 990 dataset.

## Workflow

### Option 1: Web UI (No Authentication Required) ✅ RECOMMENDED

**Step 1: Export SQL Query**
```bash
python scripts/enrich_nonprofits_bigquery.py \
    --input data/gold/nonprofits_tuscaloosa_form990.parquet \
    --export-sql scripts/bigquery_tuscaloosa_missions.sql
```

**Step 2: Run Query in BigQuery**
1. Go to https://console.cloud.google.com/bigquery
2. Click **"COMPOSE NEW QUERY"**
3. Paste SQL from `scripts/bigquery_tuscaloosa_missions.sql`
4. Click **"RUN"**
5. Wait for results (~200-400 rows expected)

**Step 3: Export Results**
1. Click **"SAVE RESULTS"** → **"CSV (local file)"**
2. Save as: `data/cache/bigquery_results.csv`

**Step 4: Merge into Gold Data**
```bash
python scripts/enrich_nonprofits_bigquery.py \
    --input data/gold/nonprofits_tuscaloosa_form990.parquet \
    --from-csv data/cache/bigquery_results.csv \
    --update-in-place
```

### Option 2: Direct Query (Requires gcloud Auth)

**Setup (one-time):**
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud auth application-default login
```

**Run:**
```bash
python scripts/enrich_nonprofits_bigquery.py \
    --input data/gold/nonprofits_tuscaloosa_form990.parquet \
    --output data/gold/nonprofits_tuscaloosa_bigquery.parquet \
    --project YOUR_PROJECT_ID
```

## Data Schema

### New Fields Added

| Field | Type | Description | Coverage |
|-------|------|-------------|----------|
| `bigquery_mission` | string | Activity or mission description from Form 990 | ~30-40% |
| `bigquery_website` | string | Website URL from Form 990 | ~30-40% |
| `bigquery_tax_year` | string | Tax year of the filing | ~30-40% |
| `bigquery_form_type` | string | Form type: "990" or "990-EZ" | ~30-40% |
| `bigquery_updated_date` | string | Date when BigQuery data was added (YYYY-MM-DD) | 100% |

### Data Sources Queried

The script queries across multiple IRS 990 tables:
- `bigquery-public-data.irs_990.irs_990_2023` (Full Form 990)
- `bigquery-public-data.irs_990.irs_990_2022` (Full Form 990)
- `bigquery-public-data.irs_990.irs_990_2021` (Full Form 990)
- `bigquery-public-data.irs_990.irs_990_ez_2023` (990-EZ for smaller orgs)
- `bigquery-public-data.irs_990.irs_990_ez_2022` (990-EZ for smaller orgs)
- `bigquery-public-data.irs_990.irs_990_ez_2021` (990-EZ for smaller orgs)

**Deduplication:** Prefers most recent year, then Full 990 over 990-EZ.

## Combined Data Coverage

After enrichment with both GivingTuesday and BigQuery:

### For Tuscaloosa (921 nonprofits)

**Missions:**
- EO-BMF: 0 (0%)
- GivingTuesday: ~299 (32.5%)
- BigQuery: ~200-400 (30-40%)
- **Combined: ~400-500 (40-50%)** ✅

**Websites:**
- EO-BMF: 0 (0%)
- GivingTuesday: 0 (0%)
- BigQuery: ~200-400 (30-40%)
- **Combined: ~200-400 (30-40%)** ✅

**Financials:**
- GivingTuesday: 307 orgs with revenue/expenses/assets (33.3%)
- BigQuery: Same data, different source

## Best Practices

### When to Use BigQuery vs GivingTuesday

| Data Need | Best Source |
|-----------|-------------|
| **Mission statements** | Both (GivingTuesday + BigQuery for coverage) |
| **Website URLs** | BigQuery (GivingTuesday doesn't extract this) |
| **Detailed financials** | GivingTuesday Data Lake (XML parsing) |
| **Grants paid** | GivingTuesday Data Lake |
| **Executive compensation** | BigQuery (irs_990_schedule_j_YYYY) |
| **Related organizations** | BigQuery (irs_990_schedule_r_YYYY) |

### Update Frequency

Re-run BigQuery enrichment:
- Annually after IRS releases new Form 990 data (typically June/July)
- When expanding to new jurisdictions
- After major nonprofit landscape changes

### Data Cleaning

Mission statements from BigQuery may contain XML artifacts:
```python
import re

# Remove XML tags
mission = re.sub(r'<[^>]+>', ' ', mission)

# Clean whitespace
mission = re.sub(r'\s+', ' ', mission).strip()
```

## Cost

**FREE** when using:
- Public BigQuery datasets via web UI
- Within Google Cloud's 1TB free tier per month

Typical query cost: **$0** (Tuscaloosa query ~10 MB)

## Troubleshooting

### "No results returned"

- EINs may not have filed 990 in queried years
- Check if organizations are too small (< $50K revenue exempts from 990)
- Try expanding `--years` to include more historical data

### "CSV column names don't match"

BigQuery exports use lowercase column names. The script handles this automatically.

### "Existing BigQuery columns found"

The script automatically drops and replaces existing BigQuery columns when using `--update-in-place`.

## Examples

**Full Alabama health nonprofits:**
```bash
# 1. Export SQL
python scripts/enrich_nonprofits_bigquery.py \
    --input data/gold/nonprofits_organizations.parquet \
    --export-sql scripts/bigquery_alabama_health.sql \
    --states AL --ntee E

# 2. Run in BigQuery web UI, export CSV

# 3. Merge
python scripts/enrich_nonprofits_bigquery.py \
    --input data/gold/nonprofits_organizations.parquet \
    --from-csv data/cache/bigquery_alabama_health.csv \
    --update-in-place
```

**Sample 100 orgs for testing:**
```bash
python scripts/enrich_nonprofits_bigquery.py \
    --input data/gold/nonprofits_tuscaloosa_form990.parquet \
    --export-sql scripts/bigquery_sample.sql \
    --sample 100
```

## Related Documentation

- [Form 990 XML Guide](website/docs/data-sources/form-990-xml.md)
- [GivingTuesday Data Lake](scripts/enrich_nonprofits_gt990.py)
- [Citations](CITATIONS.md)
