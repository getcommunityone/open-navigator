---
sidebar_position: 7
---

# FEC Campaign Finance Integration

Track political contributions and campaign finance data using the **Federal Election Commission (FEC)** via **OpenFEC API** and **Bulk Downloads**.

## 🎯 Overview

The FEC integration enables tracking of:
- Individual political contributions ($200+)
- Federal candidates (House, Senate, President)
- Political committees and PACs
- Nonprofit leadership political giving
- Donor networks in advocacy organizations
- Campaign expenditures and disbursements

**Two access methods:**
1. **OpenFEC API** - Real-time queries, filtered searches (API key required)
2. **Bulk Downloads** - Complete datasets, no rate limits (no API key needed)

This data integrates with nonprofit and contacts data to reveal political influence patterns.

## 🔑 Get API Access

### OpenFEC API (Real-time Queries)

**1. Sign Up for Free API Key**

Visit: **https://api.data.gov/signup/**

- Free tier: **1,000 requests/hour**
- No credit card required
- Instant activation

**2. Set Environment Variable**

```bash
# Add to your .env file
echo 'FEC_API_KEY="your_api_key_here"' >> .env

# Or export for current session
export FEC_API_KEY="your_api_key_here"
```

Without an API key, you'll use `DEMO_KEY` (limited to 30 requests/hour).

### Bulk Downloads (Complete Datasets)

**No API key required!** Download complete datasets directly:

**Bulk Data Portal:** https://www.fec.gov/data/browse-data/?tab=bulk-data

**Available datasets:**
- **Contributions** (Schedule A) - All individual contributions $200+
- **Expenditures** (Schedule B) - All operating expenditures
- **Candidate Master** - All federal candidates
- **Committee Master** - All PACs and committees
- **Campaign Finance Totals** - Summary by cycle

**Format:** CSV, FEC format  
**Update Frequency:** Nightly  
**Historical Coverage:** 1980s to present  
**Rate Limits:** None (direct download)  

**When to use bulk downloads:**
- Analyzing complete datasets (millions of records)
- Historical analysis across election cycles
- Offline analysis without API rate limits
- Data warehousing and archival

**When to use API:**
- Real-time contribution lookups
- Filtered searches (by name, employer, state)
- Incremental updates
- Web application queries

## 📊 Gold Tables Created

The FEC integration creates 4 gold tables per state:

| Table | Description | Key Fields |
|-------|-------------|------------|
| **campaigns_candidates** | Federal candidates in state | candidate_id, name, party, office, district |
| **campaigns_committees** | PACs and campaign committees | committee_id, name, type, party |
| **campaigns_contributions** | Individual contributions $200+ | contributor_name, employer, amount, date, recipient |
| **campaigns_nonprofit_donors** | Nonprofit leadership donations | ein, organization_name, contributor_name, amount |

## 🚀 Quick Start

### Run Demo Script

```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate

# Basic demo (using DEMO_KEY)
python examples/demo_fec_integration.py --state MA

# With your API key
export FEC_API_KEY="your_key_here"
python examples/demo_fec_integration.py --state MA --cycle 2024

# Search for specific nonprofit donors
python examples/demo_fec_integration.py --state MA --employer "Community Health"
```

### Create Gold Tables

```bash
# Create campaign finance tables for Massachusetts
python pipeline/create_campaigns_gold_tables.py \
  --state MA \
  --cycle 2024 \
  --max-contributions 10000

# With custom API key
python pipeline/create_campaigns_gold_tables.py \
  --state MA \
  --api-key "your_key_here"
```

## 📖 Use Cases

### 1. Track Nonprofit Leadership Donations

Identify politically active nonprofit officers and directors:

```python
from pipeline.create_campaigns_gold_tables import CampaignsGoldTableCreator

creator = CampaignsGoldTableCreator(state_code="MA")
creator.create_all_campaigns_tables(cycle=2024)

# Analyzes:
# - Contributions where employer matches nonprofit name
# - Contributions from known nonprofit officers/directors
# - Political giving patterns in advocacy sector
```

**Output:** `data/gold/states/MA/campaigns_nonprofit_donors.parquet`

### 2. Map Donor Networks

Find connections between organizations and political campaigns:

```python
from discovery.fec_integration import OpenFECAPI

api = OpenFECAPI(api_key="your_key")

# Search for contributions from health sector
result = api.search_individual_contributions(
    contributor_state="MA",
    contributor_employer="Health",
    min_amount=1000
)

for contrib in result['results']:
    print(f"{contrib['contributor_name']} ({contrib['contributor_employer']})")
    print(f"  → ${contrib['contribution_receipt_amount']} to {contrib['committee_name']}")
```

### 3. Analyze Political Influence on Policy

Cross-reference campaign contributions with grant awards:

```python
import pandas as pd

# Load campaign contributions
contributions = pd.read_parquet('data/gold/states/MA/campaigns_contributions.parquet')

# Load grant data
grants = pd.read_parquet('data/gold/states/MA/grants_revenue_sources.parquet')

# Find organizations that both give politically and receive grants
donor_orgs = contributions['contributor_employer'].unique()
grant_recipients = grants['organization_name'].unique()

overlap = set(donor_orgs) & set(grant_recipients)
print(f"Organizations that both donate politically and receive grants: {len(overlap)}")
```

## 💾 Using Bulk Downloads

For large-scale analysis, use FEC bulk downloads instead of the API:

### Download Complete Datasets

```bash
# Download candidate master file (all federal candidates)
wget https://www.fec.gov/files/bulk-downloads/2024/cn24.zip
unzip cn24.zip

# Download committee master file (all PACs and committees)
wget https://www.fec.gov/files/bulk-downloads/2024/cm24.zip
unzip cm24.zip

# Download individual contributions (Schedule A)
# Warning: Very large file (100s of MB to GBs)
wget https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip
unzip indiv24.zip
```

### Process Bulk Data with Pandas

```python
import pandas as pd
from pathlib import Path

# Load contributions for specific cycle
contributions_file = Path("data/fec/bulk/indiv24.txt")
df = pd.read_csv(
    contributions_file,
    sep="|",
    header=None,
    names=[
        "CMTE_ID", "AMNDT_IND", "RPT_TP", "TRANSACTION_PGI",
        "IMAGE_NUM", "TRANSACTION_TP", "ENTITY_TP", "NAME",
        "CITY", "STATE", "ZIP_CODE", "EMPLOYER", "OCCUPATION",
        "TRANSACTION_DT", "TRANSACTION_AMT", "OTHER_ID",
        "TRAN_ID", "FILE_NUM", "MEMO_CD", "MEMO_TEXT", "SUB_ID"
    ],
    encoding="latin1",
    low_memory=False
)

# Filter to Massachusetts contributors
ma_contributions = df[df['STATE'] == 'MA']

# Filter to health sector
health_donors = ma_contributions[
    ma_contributions['EMPLOYER'].str.contains('Health|Hospital|Dental', case=False, na=False)
]

print(f"Found {len(health_donors):,} health sector contributions from MA")
print(f"Total amount: ${health_donors['TRANSACTION_AMT'].sum():,.2f}")

# Save to parquet for faster future access
health_donors.to_parquet('data/gold/states/MA/campaigns_contributions.parquet')
```

### Bulk Download File Formats

**Candidate Master File (cn.txt):**
- Delimiter: Pipe (`|`)
- Columns: `CAND_ID`, `CAND_NAME`, `CAND_PTY_AFFILIATION`, `CAND_ELECTION_YR`, `CAND_OFFICE_ST`, `CAND_OFFICE`, `CAND_OFFICE_DISTRICT`, etc.

**Committee Master File (cm.txt):**
- Delimiter: Pipe (`|`)
- Columns: `CMTE_ID`, `CMTE_NM`, `TRES_NM`, `CMTE_CITY`, `CMTE_ST`, `CMTE_TP`, `CMTE_PTY_AFFILIATION`, etc.

**Individual Contributions (indiv.txt):**
- Delimiter: Pipe (`|`)
- Columns: `CMTE_ID`, `NAME`, `CITY`, `STATE`, `ZIP_CODE`, `EMPLOYER`, `OCCUPATION`, `TRANSACTION_DT`, `TRANSACTION_AMT`, etc.
- Contains all contributions $200+ as required by law

### Advantages of Bulk Downloads

✅ **Complete data** - No pagination, no missing records  
✅ **No rate limits** - Download once, analyze forever  
✅ **Historical data** - Access to all election cycles  
✅ **Offline analysis** - No API dependency  
✅ **Faster processing** - Local files vs HTTP requests  

### When to Use Each Method

| Scenario | Method | Reason |
|----------|--------|--------|
| Find specific donor | API | Filtered search, fast lookup |
| All MA contributions | Bulk Download | Complete dataset, no limits |
| Real-time updates | API | Latest filings |
| Historical analysis | Bulk Download | Multi-cycle coverage |
| Web application | API | Dynamic queries |
| Research/analysis | Bulk Download | Full data access |


## 🛠️ API Reference

### Search Individual Contributions

```python
from discovery.fec_integration import OpenFECAPI

api = OpenFECAPI(api_key="your_key")

# Search by contributor
result = api.search_individual_contributions(
    contributor_name="Smith",
    contributor_state="MA",
    min_amount=200,
    min_date="2023-01-01",
    max_date="2024-12-31"
)

# Search by employer
result = api.search_individual_contributions(
    contributor_employer="Community Foundation",
    contributor_state="MA",
    min_amount=1000
)
```

### Search Candidates

```python
# House candidates in Massachusetts
result = api.search_candidates(
    state="MA",
    office="H",  # H=House, S=Senate, P=President
    cycle=2024
)

# Senate candidates
result = api.search_candidates(
    state="MA",
    office="S",
    party="DEM",  # or "REP"
    cycle=2024
)
```

### Search Committees

```python
# Find PACs in Massachusetts
result = api.search_committees(
    state="MA",
    committee_type="N"  # N=PAC, Q=Super PAC
)
```

## 📋 Data Model Integration

### Links to Nonprofit Data

The `campaigns_nonprofit_donors` table links FEC data to nonprofits:

```sql
-- Conceptual SQL (use pandas for actual queries)
SELECT 
    nd.organization_name,
    nd.contributor_name,
    nd.contributor_title,
    SUM(nd.contribution_amount) as total_contributions,
    COUNT(*) as num_contributions
FROM campaigns_nonprofit_donors nd
GROUP BY nd.organization_name, nd.contributor_name
ORDER BY total_contributions DESC;
```

### Links to Contacts

Match contributions to nonprofit officers:

```python
import pandas as pd

# Load data
officers = pd.read_parquet('data/gold/states/MA/contacts_nonprofit_officers.parquet')
contributions = pd.read_parquet('data/gold/states/MA/campaigns_contributions.parquet')

# Match by name
merged = officers.merge(
    contributions,
    left_on='officer_name',
    right_on='contributor_name',
    how='inner'
)

print(f"Found {len(merged)} contribution records from known nonprofit officers")
```

## ⚙️ Configuration

### Environment Variables

```bash
# Required (or use DEMO_KEY)
FEC_API_KEY="your_api_key_here"

# Optional
FEC_CACHE_DIR="data/cache/fec"  # Where to cache bulk downloads
```

### Rate Limits

| API Key | Rate Limit | Notes |
|---------|------------|-------|
| DEMO_KEY | 30 requests/hour | Shared across all users |
| Free API Key | 1,000 requests/hour | Recommended |
| Bulk Download | No limit | 1-5 GB files, use for comprehensive data |

## 🎓 Advanced Usage

### Bulk Data Download

For comprehensive historical analysis, download bulk files:

```python
from discovery.fec_integration import FECBulkDataLoader

loader = FECBulkDataLoader(cache_dir="data/cache/fec")

# Download 2024 individual contributions (WARNING: 1-5 GB)
zip_path = loader.download_individual_contributions(cycle="2024")

# Parse and filter
df = loader.parse_individual_contributions(
    zip_path=zip_path,
    state_filter="MA",
    employer_filter="Foundation",
    min_amount=200
)

print(f"Found {len(df):,} contributions from MA foundations")
```

### Custom Analysis Pipeline

Build custom analysis workflows:

```python
from discovery.fec_integration import OpenFECAPI
import pandas as pd

api = OpenFECAPI(api_key="your_key")

# 1. Get all House candidates in MA
candidates_result = api.search_candidates(state="MA", office="H", cycle=2024)
candidates = candidates_result['results']

# 2. For each candidate, get top donors
for candidate in candidates:
    candidate_id = candidate['candidate_id']
    
    # Get candidate committees
    committees_result = api.search_committees(candidate_id=candidate_id)
    
    # Analyze fundraising
    print(f"\n{candidate['name']} ({candidate['party']})")
    print(f"  Committees: {len(committees_result['results'])}")
```

## 🔍 Data Quality Notes

### Contribution Reporting Threshold

- FEC requires reporting for contributions **$200 or more**
- Smaller contributions are not itemized
- Use `min_amount=200` for complete data

### Employer Field

- Self-reported by contributor
- May have inconsistent formatting
- "Community Health Center" vs "Community Health Ctr"
- Use fuzzy matching for nonprofit employer analysis

### Update Frequency

- FEC data updated **daily**
- Electronic filings appear within 24 hours
- Paper filings may take 30+ days

## 📚 Additional Resources

- **OpenFEC API Docs:** https://api.open.fec.gov/developers/
- **FEC Bulk Data:** https://www.fec.gov/data/browse-data/?tab=bulk-data
- **Campaign Finance Guide:** https://www.fec.gov/help-candidates-and-committees/
- **Data Dictionary:** https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/

## 🤝 Related Integrations

- [Nonprofit Discovery](nonprofit-discovery.md) - Match employers to EINs
- [IRS BMF Data](irs-bmf-data.md) - Nonprofit organization data
- [Gold Table Pipeline](../guides/gold-table-pipeline.md) - Full data model

---

## 💡 Pro Tips

1. **Start with API, use bulk for scale:** API is easier for exploration, bulk files for comprehensive analysis
2. **Cache aggressively:** Set up `data/cache/fec/` to avoid re-downloading
3. **Match on lowercase:** Employer names vary in capitalization
4. **Use year ranges:** Contributions span multiple years, use date filters
5. **Join with EINs:** Match FEC employer field to `nonprofits_organizations.ein` for verified linkage
