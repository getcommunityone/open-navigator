---
sidebar_position: 12
---

# Nonprofit Officers & Board Members Contact Data

Extract and track nonprofit leadership (officers, directors, trustees) from IRS Form 990 filings as searchable contacts.

## 🎯 Overview

The system now enriches nonprofit data with **officer and board member information** from IRS Form 990 Schedule J, creating versioned contact records with:

- **Officer names** (CEO, CFO, Executive Director, etc.)
- **Board members** and trustees
- **Titles/positions**
- **Compensation** amounts
- **Hours per week**
- **Annual snapshots** for historical tracking

## 📊 Data Sources

### IRS Form 990 Part VII (Officers, Directors, Trustees)

**Primary Source: GivingTuesday Data Lake** 🎉

We use the [GivingTuesday 990 Data Lake](https://990data.givingtuesday.org/) which hosts complete Form 990 XML files on AWS S3.

**Advantages:**
- ✅ **Recent Data**: 2013-2023 filings (vs BigQuery's 2017 cutoff)
- ✅ **No Auth Required**: Public S3 bucket, no credentials needed
- ✅ **Complete Coverage**: 5.4M+ Form 990 filings indexed
- ✅ **Detailed**: Part VII includes officer names, titles, hours, compensation

**Fields Extracted from Form 990 Part VII:**
| Field | Description | Example |
|-------|-------------|---------|
| `name` | Officer/director name | "Sarah Johnson" |
| `title` | Position/title | "CEO", "Board Chair" |
| `compensation` | Total annual compensation | 150000 |
| `hours_per_week` | Average hours worked | 40 |
| `compensation_org` | From this organization | 145000 |
| `compensation_related` | From related orgs | 5000 |
| `compensation_other` | Benefits, deferred comp | 2500 |

## 🚀 Quick Start

### Step 1: Download GivingTuesday Data Lake Index (One-Time Setup)

```bash
# Activate environment
source .venv/bin/activate

# Download the index of 5.4M+ Form 990 filings (~900MB)
python scripts/enrich_nonprofits_gt990.py --download-index

# Index will be cached at: data/cache/form990_gt_index.parquet
```

### Step 2: Enrich Nonprofits with Officer Data

```bash
# Enrich with Form 990 data (includes officers from Part VII)
python scripts/enrich_nonprofits_gt990.py \
  --input data/gold/states/MA/nonprofits_organizations.parquet \
  --output data/gold/states/MA/nonprofits_organizations.parquet \
  --concurrent 20

# This downloads XMLs from S3, parses them, and adds form_990_officers field
```

This adds a `form_990_officers` JSON field to each nonprofit record:

```json
{
  "ein": "123456789",
  "organization_name": "Alabama Oral Health Foundation",
  "form_990_officers": [
    {
      "name": "Sarah Johnson",
      "title": "CEO",
      "compensation": 150000,
      "compensation_org": 145000,
      "compensation_related": 5000,
      "compensation_other": 2500,
      "hours_per_week": 40
    },
    {
      "name": "John Smith",
      "title": "Board Chair",
      "compensation": 0,
      "hours_per_week": 5
    }
  ],
  "form_990_tax_year": "2022-12-31",
  "form_990_status": "found"
}
```

### Step 3: Create Contact Tables with Versioning

```bash
# Create nonprofit officer contacts (state-specific)
python -c "
from pipeline.create_contacts_gold_tables import ContactsGoldTableCreator

# Massachusetts nonprofit officers
creator = ContactsGoldTableCreator(
    output_dir='data/gold',
    state_code='MA'  # Output to data/gold/states/MA/
)

# Create current year + 2 historical years
creator.create_all_contacts_tables(
    include_nonprofit_officers=True,
    snapshot_years=[2023, 2022, 2021]
)
"
```

**Creates:**
- `data/gold/states/MA/contacts_nonprofit_officers.parquet` - Current year
- `data/gold/states/MA/contacts_nonprofit_officers_2023.parquet` - 2023 snapshot
- `data/gold/states/MA/contacts_nonprofit_officers_2022.parquet` - 2022 snapshot  
- `data/gold/states/MA/contacts_nonprofit_officers_2021.parquet` - 2021 snapshot
- `data/gold/states/MA/contacts_nonprofit_officers_history.parquet` - Combined history

**Note:** Files are organized by state in `data/gold/states/{STATE}/` to match the pattern used for other contact types.

### Step 3: Search Officers

Officers are now searchable alongside elected officials:

```bash
curl "http://localhost:8000/api/search/?q=Sarah&types=contacts&state=AL"
```

**Returns:**

```json
{
  "query": "Sarah",
  "total_results": 5,
  "results": {
    "contacts": [
      {
        "type": "contact",
        "title": "Sarah Johnson",
        "subtitle": "CEO - Alabama Oral Health Foundation ($150,000)",
        "description": "Nonprofit officer in Birmingham, AL",
        "url": "/nonprofits?name=Alabama-Oral-Health-Foundation",
        "score": 1.5,
        "metadata": {
          "title": "CEO",
          "organization": "Alabama Oral Health Foundation",
          "compensation": 150000,
          "contact_type": "nonprofit_officer"
        }
      }
    ]
  }
}
```

## 📋 Data Schema

### Nonprofit Officers Contact Table

```python
{
    # Officer Info
    'name': 'Sarah Johnson',
    'title': 'CEO',
    'compensation': 150000,
    'hours_per_week': 40,
    
    # Organization
    'organization_ein': '123456789',
    'organization_name': 'Alabama Oral Health Foundation',
    'organization_ntee_code': 'E',
    'organization_type': 'nonprofit',
    
    # Location
    'state': 'AL',
    'city': 'Birmingham',
    'zip_code': '35203',
    
    # Versioning (for annual snapshots)
    'snapshot_year': 2023,
    
    # Metadata
    'source': 'irs_990_schedule_j',
    'contact_type': 'nonprofit_officer',
    'extracted_date': '2024-01-15'
}
```

## 📅 Annual Snapshots & Historical Tracking

### Why Versioning?

**Track changes over time:**
- Officer turnover
- Compensation changes
- Board composition
- Leadership transitions

### Creating Snapshots

```python
from pipeline.create_contacts_gold_tables import ContactsGoldTableCreator

creator = ContactsGoldTableCreator()

# Create snapshot for specific year
creator.create_contacts_nonprofit_officers(snapshot_year=2022)

# Create multi-year history
creator.create_nonprofit_officers_history(years=[2023, 2022, 2021])
```

### Querying Historical Data

```python
import pandas as pd

# Load history for specific state
history = pd.read_parquet('data/gold/states/MA/contacts_nonprofit_officers_history.parquet')

# Find all positions held by a person
sarah_history = history[history['name'] == 'Sarah Johnson']

# Track compensation changes
comp_changes = history.groupby(['organization_ein', 'snapshot_year'])['compensation'].mean()

# Identify board turnover
turnover = history.groupby('organization_ein')['name'].nunique()
```

## 🔍 Use Cases

### 1. Nonprofit Leadership Research

**Find health nonprofit CEOs in Alabama:**

```python
import pandas as pd

# Load from state directory
officers = pd.read_parquet('data/gold/states/AL/contacts_nonprofit_officers.parquet')

health_ceos = officers[
    (officers['organization_ntee_code'].str.startswith('E')) &
    (officers['title'].str.contains('CEO|Executive Director', case=False, na=False))
]

print(f"Found {len(health_ceos)} health nonprofit CEOs in Alabama")
print(health_ceos[['name', 'organization_name', 'compensation']].head())
```

### 2. Compensation Analysis

**Identify highest-paid nonprofit executives:**

```python
top_paid = officers.nlargest(20, 'compensation')[
    ['name', 'title', 'organization_name', 'compensation', 'state']
]
```

### 3. Board Composition

**Find board members (zero/low compensation):**

```python
board_members = officers[
    (officers['title'].str.contains('Board|Director|Trustee', case=False, na=False)) &
    (officers['compensation'] < 10000)
]
```

### 4. Network Analysis

**Map leadership connections across organizations:**

```python
# Find people who serve on multiple boards
multi_board = officers.groupby('name')['organization_ein'].nunique()
cross_board = multi_board[multi_board > 1].sort_values(ascending=False)

print(f"{len(cross_board)} people serve on multiple boards")
```

## 🎯 Integration Points

### Search API

Officers appear in unified search results:

```bash
GET /api/search/?q=dental&types=contacts
GET /api/search/?q=CEO&state=AL
GET /api/search/?q=Board+Chair&ntee_code=E
```

### Frontend Display

**Contact cards show:**
- Officer name and title
- Organization affiliation
- Compensation (if public)
- Link to organization profile

### Data Pipeline

**Automatic updates:**
1. Form 990 enrichment runs annually (when new 990s filed to IRS)
2. GivingTuesday Data Lake updated with new XMLs
3. Contact tables regenerated with new snapshot_year
4. Historical tables updated automatically
5. Search index refreshed

## 📈 Statistics

**Example coverage (Alabama health nonprofits):**
- **Organizations**: 2,500 health nonprofits
- **Officer records**: ~15,000 (avg 6 officers per org)
- **With compensation data**: ~8,000 (53%)
- **Board members**: ~10,000
- **Executive staff**: ~5,000

## 🔧 Technical Notes

### Data Source: GivingTuesday vs BigQuery

**Why GivingTuesday Data Lake?**

During implementation, we discovered limitations with BigQuery's public IRS 990 dataset:
- ❌ Data only available through 2017 (7+ years old)
- ❌ Schedule J (officer compensation) tables not in public dataset
- ❌ Requires Google Cloud authentication

**GivingTuesday advantages:**
- ✅ Current data through 2023
- ✅ Complete Form 990 XMLs with Part VII officer data
- ✅ Public S3 bucket, no authentication required
- ✅ 5.4M+ filings indexed and searchable

### Form 990 XML Parsing

The enrichment script:
1. Downloads index of 5.4M+ Form 990 filings from S3
2. Looks up EINs to find most recent filing
3. Downloads XML from `s3://gt990datalake-rawdata/` (public read)
4. Parses Part VII (Form990PartVIISectionAGrp) for officer data
5. Caches XMLs locally to avoid re-downloading

**Parsing performance:**
- ~2-5 seconds per nonprofit (includes download + parse)
- Run with `--concurrent 20` for 20 parallel downloads
- XMLs cached in `data/cache/form_990_xml/`

### Parquet Storage

Officers stored as JSON string in nonprofit table:
```python
'form_990_officers': '[{"name":"Sarah Johnson","title":"CEO",...}]'
```

Expanded to individual rows in contacts table for searchability.

### Annual Snapshots

**File organization (state-based):**
- Current: `data/gold/states/{STATE}/contacts_nonprofit_officers.parquet`
- Historical: `data/gold/states/{STATE}/contacts_nonprofit_officers_2023.parquet`
- Combined: `data/gold/states/{STATE}/contacts_nonprofit_officers_history.parquet`

**Example for Massachusetts:**
- `data/gold/states/MA/contacts_nonprofit_officers.parquet`
- `data/gold/states/MA/contacts_nonprofit_officers_2023.parquet`
- `data/gold/states/MA/contacts_nonprofit_officers_history.parquet`

This matches the organization pattern for other contact types (`contacts_local_officials.parquet`, `contacts_meeting_attendance.parquet`).

## 🚨 Limitations

### Data Availability

1. **Only e-filed returns**: Schedule J not always available
2. **Varies by form type**: 990-EZ may not include all officers
3. **990-PF different**: Foundation filings use different schema
4. **Lag time**: 990s filed ~18 months after tax year end

### Privacy Considerations

**Public data but sensitive:**
- Compensation is public information (legally required disclosure)
- Names and titles are part of public record
- Consider context when displaying (advocacy vs. general search)

## 📚 Related Documentation

- [IRS Form 990 XML Data (GivingTuesday)](https://990data.givingtuesday.org/)
- [Form 990 Enrichment Script](/scripts/enrich_nonprofits_gt990.py)
- [Contacts Gold Tables](/docs/guides/contacts-officials)
- [Search API Reference](/docs/api-reference)

## 🎉 Next Steps

1. **Download GivingTuesday index** (one-time setup, ~900MB)
2. **Enrich your nonprofit data** with officer information from Form 990 XMLs
3. **Create versioned snapshots** for historical tracking
4. **Search officers** via API or frontend
5. **Analyze leadership** patterns and compensation
6. **Track changes** over time with history tables

**Questions?** See [Form 990 enrichment script](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/scripts/enrich_nonprofits_gt990.py) for implementation details.
