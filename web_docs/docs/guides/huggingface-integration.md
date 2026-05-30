---
sidebar_position: 9
---

# 🚀 HuggingFace Dataset Integration - Quick Start Guide

## 📋 Overview

You now have **3 new files** to push your 1.9M+ nonprofit datasets to HuggingFace and query them from React:

1. **`packages/hosting` (`python -m hosting.huggingface nonprofits`)** - Upload tooling
2. **`frontend/src/utils/huggingface.ts`** - TypeScript API client
3. **`frontend/src/pages/NonprofitsHF.tsx`** - Example React page
4. **`website/docs/guides/huggingface-datasets.md`** - Complete documentation

---

## ⚡ Quick Start (5 Steps)

### Step 1: Get HuggingFace Token

1. Visit: https://huggingface.co/settings/tokens
2. Click "New token"
3. Name it: `oral-health-upload`
4. Permission: **Write**
5. Copy the token (starts with `hf_...`)

### Step 2: Set Environment Variable

```bash
# Add to .env file
echo 'HF_TOKEN=hf_YOUR_TOKEN_HERE' >> .env

# Or export for current session
export HF_TOKEN="hf_YOUR_TOKEN_HERE"
```

### Step 3: Install Dependencies

```bash
# Python dependencies
pip install huggingface_hub datasets pyarrow

# Already installed in your project
# datasets and huggingface-hub
```

### Step 4: Upload Datasets

```bash
cd /home/developer/projects/open-navigator

# Upload all 4 nonprofit tables
python -m hosting.huggingface nonprofits

# Output:
# ✅ Logged in to Hugging Face
# ✅ Repository ready: https://huggingface.co/datasets/CommunityOne/one-nonprofits
# 📤 Uploading organizations from data/gold/nonprofits_organizations.parquet
#   Rows: 1,952,238
#   Columns: 28
#   Size: 156.43 MB
# ✅ Uploaded organizations: 1,952,238 records
# ... (uploads financials, programs, locations)
# 🎉 All uploads complete!
```

**What gets uploaded:**
- `nonprofits_organizations.parquet` → 1.9M+ orgs (split: "organizations")
- `nonprofits_financials.parquet` → Financial data (split: "financials")
- `nonprofits_programs.parquet` → Programs (split: "programs")
- `nonprofits_locations.parquet` → Locations (split: "locations")

### Step 5: Test the Dataset

```bash
# Test with curl (no auth required for public datasets!)
curl "https://datasets-server.huggingface.co/rows?dataset=CommunityOne/one-nonprofits&config=default&split=organizations&offset=0&length=10" | jq .

# Search for "dental"
curl "https://datasets-server.huggingface.co/search?dataset=CommunityOne/one-nonprofits&config=default&split=organizations&query=dental" | jq .
```

Expected response:
```json
{
  "features": [...],
  "rows": [
    {
      "row_idx": 0,
      "row": {
        "ein": "630123456",
        "name": "ALABAMA DENTAL ASSOCIATION",
        "city": "MONTGOMERY",
        "state": "AL",
        "ntee_code": "E12",
        ...
      }
    }
  ],
  "num_rows_total": 1952238,
  "num_rows_per_page": 100
}
```

---

## 🌐 Using in React

### Option A: Replace Current Nonprofits Page

```bash
# Backup current page
mv frontend/src/pages/Nonprofits.tsx frontend/src/pages/Nonprofits.backup.tsx

# Use HuggingFace version
mv frontend/src/pages/NonprofitsHF.tsx frontend/src/pages/Nonprofits.tsx
```

### Option B: Add New Route

Edit `frontend/src/App.tsx`:

```typescript
import NonprofitsHF from './pages/NonprofitsHF'

// Add route
<Route path="/nonprofits-hf" element={<NonprofitsHF />} />
```

### Test Locally

```bash
cd frontend
npm run dev

# Visit: http://localhost:5173/nonprofits
# or: http://localhost:5173/nonprofits-hf
```

---

## 🔍 Query Examples

### Python

```python
from datasets import load_dataset
import pandas as pd

# Load dataset
dataset = load_dataset("CommunityOne/one-nonprofits")

# Get organizations table
orgs = dataset["organizations"]

# Convert to pandas
df = pd.DataFrame(orgs)

# Filter by state
alabama = df[df['state'] == 'AL']
print(f"Alabama nonprofits: {len(alabama):,}")
# Output: Alabama nonprofits: 26,148

# Filter by NTEE (E = Health)
health = df[df['ntee_code'].str.startswith('E', na=False)]
print(f"Health organizations: {len(health):,}")
# Output: Health organizations: 80,000+

# Search for "dental"
dental = df[df['name'].str.contains('dental', case=False, na=False)]
print(f"Dental organizations: {len(dental):,}")
```

### JavaScript/TypeScript

```typescript
import { searchNonprofits } from '../utils/huggingface'

// Search for dental orgs in California
const results = await searchNonprofits({
  dataset: "CommunityOne/one-nonprofits",
  query: "dental",
  state: "CA",
  nteeCode: "E",
  limit: 100
})

console.log(`Found ${results.length} dental orgs in California`)
```

### REST API (curl)

```bash
# Get first 100 organizations
curl "https://datasets-server.huggingface.co/rows?dataset=CommunityOne/one-nonprofits&config=default&split=organizations&offset=0&length=100"

# Search for "dental"
curl "https://datasets-server.huggingface.co/search?dataset=CommunityOne/one-nonprofits&config=default&split=organizations&query=dental"

# Get dataset size
curl "https://datasets-server.huggingface.co/size?dataset=CommunityOne/one-nonprofits&config=default&split=organizations"
```

---

## 📊 What's in the Dataset?

### organizations (main table)
- **Records:** 1,952,238
- **Fields:** ein, name, sort_name, city, state, zip_code, street_address, ntee_code, subsection_code, foundation_code, tax_exempt_status, deductibility_status, ruling_date, organization_code, activity_codes, group_exemption, affiliation_code, data_source

### financials
- **Records:** 1,952,238
- **Fields:** ein, asset_amount, income_amount, revenue_amount, tax_period

### programs
- **Records:** 1,952,238
- **Fields:** ein, activity_codes, group_exemption, affiliation_code

### locations
- **Records:** 1,952,238
- **Fields:** ein, street_address, city, state, zip_code

---

## 🎯 Key Features

### ✅ FREE
- **Unlimited storage** (public datasets)
- **No authentication** required for reading
- **Free bandwidth** and API calls

### ✅ FAST
- **CDN-backed** by HuggingFace
- **Automatic caching**
- **Pagination** built-in (100 rows max per request)

### ✅ SEARCHABLE
- **Full-text search** included
- **Filter by columns** (state, NTEE code, etc.)
- **REST API** - works from any language

### ✅ SCALABLE
- **1.9M+ records** available instantly
- **No database** setup required
- **Global availability**

---

## 🛠️ Customization

### Change Dataset Name

Edit `scripts/upload_nonprofits_to_hf.py`:

```python
# Line 84
self.repo_name = repo_name or "YOUR_USERNAME/YOUR_DATASET_NAME"
```

Then upload:
```bash
python -m hosting.huggingface nonprofits --repo "your-username/nonprofits"
```

### Update React Components

Edit `frontend/src/pages/NonprofitsHF.tsx`:

```typescript
// Line 115
const DATASET_NAME = "your-username/nonprofits"
```

---

## 📚 Documentation

### Full Guide
- **Location:** `website/docs/guides/huggingface-datasets.md`
- **URL:** http://localhost:3000/docs/guides/huggingface-datasets

### HuggingFace Docs
- **Datasets:** https://huggingface.co/docs/datasets
- **API:** https://huggingface.co/docs/datasets-server
- **Hub:** https://huggingface.co/docs/hub

### IRS Data Source
- **EO-BMF:** https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
- **Search Tool:** https://www.irs.gov/charities-non-profits/tax-exempt-organization-search

---

## 🔧 Troubleshooting

### Error: "Hugging Face token required"

**Solution:**
```bash
export HF_TOKEN="hf_YOUR_TOKEN"
# Or add to .env file
```

### Error: "File not found: nonprofits_organizations.parquet"

**Solution:** Generate the gold tables first:
```bash
python scripts/create_all_gold_tables.py --nonprofits-only --use-irs --download-all-irs
```

### Error: "Repository does not exist"

**Solution:** Change the repo name or create it manually:
1. Visit: https://huggingface.co/new-dataset
2. Name: `one-nonprofits`
3. License: CC0-1.0 (Public Domain)
4. Click "Create"

### Dataset shows 0 rows

**Solution:** Wait 5-10 minutes after upload for HuggingFace to process the dataset. Then refresh the viewer.

---

## 🎉 Next Steps

1. **Upload datasets:** `python -m hosting.huggingface nonprofits`
2. **Test API:** Visit https://huggingface.co/datasets/CommunityOne/one-nonprofits
3. **Update React app:** Use `NonprofitsHF.tsx` example
4. **Add features:**
   - Map visualization with locations table
   - Financial charts with financials table
   - Advanced filters (subsection_code, foundation_code)
   - Autocomplete search
   - Export to CSV

---

## 📧 Support

- **Documentation:** `website/docs/guides/huggingface-datasets.md`
- **HuggingFace Support:** https://discuss.huggingface.co
- **IRS EO-BMF Guide:** `website/docs/data-sources/irs-bulk-data.md`

**Happy querying! 🚀**
