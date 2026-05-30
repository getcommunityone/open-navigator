---
sidebar_position: 8
---

# Logo Enrichment with Logo.dev

Enrich nonprofit data with high-quality organization logos using the Logo.dev API.

## 🎨 Overview

The Logo.dev integration automatically fetches organization logos based on their website domain names. This provides:

- **High-quality logos** - Professional vector logos in multiple sizes
- **Multiple sizes** - Small (32px), Medium (128px), Large (200px)
- **Efficient storage** - URLs stored in parquet (not the images themselves)
- **Incremental updates** - Only fetch logos for new organizations
- **Automatic caching** - Avoid duplicate API calls

## 🔧 Setup

### 1. Get API Key

Sign up for a Logo.dev API key:

1. Go to https://www.logo.dev/
2. Sign up for an account
3. Copy your API key

**Pricing:**
- Free tier: 1,000 requests/month
- Paid plans: Starting at $9/month for 10,000 requests

### 2. Add to Environment

Add your API key to `.env`:

```bash
# Logo.dev API Key (for organization logos)
LOGODEV_API_KEY=your_api_key_here
```

## 📊 Usage

### Prerequisites

Organizations must have **website URLs** before logo enrichment. Get website data first using:

1. **Every.org API** (recommended - also provides logos):
   ```bash
   python scripts/enrich_nonprofits_everyorg.py \
     --input data/gold/states/MA/nonprofits_organizations.parquet \
     --update-in-place
   ```

2. **IRS Form 990 BigQuery** (limited availability):
   ```bash
   python scripts/enrich_nonprofits_bigquery.py \
     --input data/gold/states/MA/nonprofits_organizations.parquet \
     --update-in-place \
     --project YOUR_PROJECT_ID
   ```

3. **Custom data source** - Add `website` column to your parquet file

### Basic Usage

**Test with sample data:**
```bash
python scripts/enrich_nonprofits_logodev.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --output /tmp/test_logos.parquet \
  --sample 100
```

**Enrich all organizations:**
```bash
python scripts/enrich_nonprofits_logodev.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --update-in-place
```

**Incremental enrichment** (only fetch missing logos):
```bash
python scripts/enrich_nonprofits_logodev.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --update-in-place \
  --incremental
```

**Custom website column:**
```bash
python scripts/enrich_nonprofits_logodev.py \
  --input data/gold/nonprofits.parquet \
  --output data/gold/nonprofits_logos.parquet \
  --website-column bigquery_website
```

## 📋 Output Schema

The script adds these columns to your parquet file:

| Column | Type | Description |
|--------|------|-------------|
| `logodev_domain` | string | Extracted domain (e.g., 'carequest.org') |
| `logodev_logo_url` | string | Primary logo URL (200px) |
| `logodev_logo_small` | string | Small logo URL (32px) |
| `logodev_logo_medium` | string | Medium logo URL (128px) |
| `logodev_logo_large` | string | Large logo URL (200px) |
| `logodev_status` | string | 'success', 'not_found', or 'no_domain' |

### Example Data

```json
{
  "ein": "384016550",
  "name": "CAREQUEST INSTITUTE FOR ORAL HEALTH INC",
  "website": "https://carequest.org",
  "logodev_domain": "carequest.org",
  "logodev_logo_url": "https://img.logo.dev/carequest.org?token=XXX&size=200",
  "logodev_logo_small": "https://img.logo.dev/carequest.org?token=XXX&size=32",
  "logodev_logo_medium": "https://img.logo.dev/carequest.org?token=XXX&size=128",
  "logodev_logo_large": "https://img.logo.dev/carequest.org?token=XXX&size=200",
  "logodev_status": "success"
}
```

## 🖼️ Using Logos in Frontend

### Direct URL Usage

Logo URLs can be used directly in HTML/React:

```tsx
// React component
function OrganizationCard({ org }) {
  return (
    <div className="org-card">
      {org.logodev_logo_url && (
        <img 
          src={org.logodev_logo_url} 
          alt={`${org.name} logo`}
          className="org-logo"
        />
      )}
      <h3>{org.name}</h3>
    </div>
  );
}
```

### Responsive Images

Use different sizes for different screen sizes:

```tsx
function OrganizationLogo({ org, size = 'medium' }) {
  const logoMap = {
    small: org.logodev_logo_small,
    medium: org.logodev_logo_medium,
    large: org.logodev_logo_large
  };
  
  return (
    <img 
      src={logoMap[size]} 
      alt={`${org.name} logo`}
      loading="lazy"
    />
  );
}
```

### Fallback Handling

Handle missing logos gracefully:

```tsx
function OrganizationLogo({ org }) {
  const [imgError, setImgError] = useState(false);
  
  if (!org.logodev_logo_url || imgError) {
    // Show organization initials as fallback
    const initials = org.name
      .split(' ')
      .map(word => word[0])
      .join('')
      .slice(0, 2);
    
    return (
      <div className="logo-fallback">
        {initials}
      </div>
    );
  }
  
  return (
    <img 
      src={org.logodev_logo_url}
      alt={`${org.name} logo`}
      onError={() => setImgError(true)}
    />
  );
}
```

## 🔄 Workflow Examples

### Complete Enrichment Pipeline

```bash
# 1. Get base nonprofit data
python scripts/discovery/irs_bmf_ingestion.py --state MA

# 2. Enrich with website URLs (Every.org)
python scripts/enrich_nonprofits_everyorg.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --update-in-place

# 3. Enrich with Logo.dev logos
python scripts/enrich_nonprofits_logodev.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --update-in-place \
  --incremental

# 4. Check results
python -c "
import pandas as pd
df = pd.read_parquet('data/gold/states/MA/nonprofits_organizations.parquet')
print(f'Total organizations: {len(df):,}')
print(f'With logos: {df[\"logodev_logo_url\"].notna().sum():,}')
print(f'Coverage: {df[\"logodev_logo_url\"].notna().sum() / len(df) * 100:.1f}%')
"
```

### Weekly Update Job

```bash
#!/bin/bash
# weekly-logo-update.sh
# Run weekly to fetch logos for new organizations

source .venv/bin/activate

python scripts/enrich_nonprofits_logodev.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --update-in-place \
  --incremental

echo "✅ Logo enrichment complete"
```

## 💡 Best Practices

### 1. Use Incremental Mode

Always use `--incremental` for regular updates to avoid re-fetching existing logos:

```bash
python scripts/enrich_nonprofits_logodev.py \
  --input data.parquet \
  --update-in-place \
  --incremental
```

### 2. Test with Samples

Test with `--sample` before running on full dataset:

```bash
# Test with 100 records first
python scripts/enrich_nonprofits_logodev.py \
  --input data.parquet \
  --output /tmp/test.parquet \
  --sample 100
```

### 3. Monitor API Usage

Logo.dev free tier: 1,000 requests/month

- Each organization = 3 API requests (small, medium, large sizes)
- Free tier covers ~333 organizations/month
- Use `--incremental` to minimize API usage

### 4. Storage Efficiency

**✅ DO:** Store logo URLs in parquet
```python
# Efficient - URLs are ~100 bytes each
df['logodev_logo_url'] = 'https://img.logo.dev/...'
```

**❌ DON'T:** Download and store logo images
```python
# Inefficient - images are 10-100 KB each
# Let browsers fetch logos directly from Logo.dev CDN
```

### 5. Handle Missing Logos

Not all organizations will have logos. Plan for fallbacks:

- Use organization initials
- Generic placeholder icon
- Text-only display

## 📈 Performance

**Speed:**
- ~3 API requests per organization (3 sizes)
- ~100-200 organizations/minute
- 43,726 MA nonprofits ≈ 4-8 hours (first run)
- Subsequent runs (incremental): Only new orgs

**API Efficiency:**
- HEAD requests first (faster than GET)
- In-memory caching (avoid duplicate calls)
- Automatic retries with backoff (future enhancement)

## 🔍 Troubleshooting

### No Logos Found

**Problem:** All organizations showing `logodev_status: 'no_domain'`

**Solution:** Ensure website column exists and has data:
```bash
python -c "
import pandas as pd
df = pd.read_parquet('data.parquet')
print(f'Websites: {df[\"website\"].notna().sum():,} / {len(df):,}')
"
```

### API Key Error

**Problem:** `LOGODEV_API_KEY not found in environment`

**Solution:**
1. Add key to `.env` file
2. Restart terminal/reload environment
3. Verify: `echo $LOGODEV_API_KEY`

### Rate Limiting

**Problem:** 429 Too Many Requests errors

**Solution:**
- Check API quota at https://www.logo.dev/dashboard
- Upgrade plan or wait for quota reset
- Use `--sample` to test with fewer records

## 🔗 Related

- [Logo.dev API Documentation](https://www.logo.dev/docs)
- [Every.org Enrichment](./everyorg-enrichment.md)
- [Data Pipeline Guide](../deployment/data-pipeline.md)
