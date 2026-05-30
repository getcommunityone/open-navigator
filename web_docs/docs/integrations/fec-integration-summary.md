# FEC Campaign Finance Integration - Implementation Summary

## ✅ What Was Added

### 1. Pipeline Module
**File:** [`pipeline/create_campaigns_gold_tables.py`](../pipeline/create_campaigns_gold_tables.py)

Creates 4 campaign finance gold tables per state:
- `campaigns_candidates.parquet` - Federal candidates (House, Senate, President)
- `campaigns_committees.parquet` - PACs and campaign committees  
- `campaigns_contributions.parquet` - Individual contributions $200+
- `campaigns_nonprofit_donors.parquet` - Nonprofit leadership political giving analysis

**Key Features:**
- State-specific data extraction
- Links to nonprofits via employer matching
- Links to nonprofit officers via name matching
- Configurable contribution limits and cycle years

### 2. Example Demo Script
**File:** [`examples/demo_fec_integration.py`](../examples/demo_fec_integration.py)

Interactive demonstration of FEC API capabilities:
- Search for candidates in a state
- Find contributions from specific employers
- Track nonprofit leadership donations
- Create gold tables for integration

**Usage:**
```bash
# Basic demo
python examples/demo_fec_integration.py --state MA

# Search specific employer
python examples/demo_fec_integration.py --state MA --employer "Community Health"

# Create gold tables
python examples/demo_fec_integration.py --state MA --create-gold-tables
```

### 3. Comprehensive Documentation
**File:** [`website/docs/integrations/fec-campaign-finance.md`](../website/docs/integrations/fec-campaign-finance.md)

Complete integration guide including:
- API access setup (get free key from api.data.gov)
- Gold table schemas
- Use case examples
- Data model integration
- Advanced usage patterns
- Best practices

**Complements existing file:** [`website/docs/integrations/fec-political-contributions.md`](../website/docs/integrations/fec-political-contributions.md)

## 🔄 Integration with Existing Data Model

### Data Linkages

The FEC integration connects to existing gold tables:

```
campaigns_contributions.parquet
    ├─► contributor_employer  ───────► nonprofits_organizations.organization_name
    └─► contributor_name      ───────► contacts_nonprofit_officers.officer_name

campaigns_nonprofit_donors.parquet (Analysis Table)
    ├─► ein                   ───────► nonprofits_organizations.ein
    ├─► organization_name     ───────► nonprofits_organizations.organization_name
    └─► contributor_name      ───────► contacts_nonprofit_officers.officer_name

campaigns_candidates.parquet
    └─► state                 ───────► State-partitioned data structure

campaigns_committees.parquet
    └─► state                 ───────► State-partitioned data structure
```

### Use Cases Enabled

1. **Track Political Influence on Grant Awards**
   ```python
   # Load data
   contributions = pd.read_parquet('data/gold/states/MA/campaigns_contributions.parquet')
   grants = pd.read_parquet('data/gold/states/MA/grants_revenue_sources.parquet')
   
   # Analyze correlation between political giving and grant receipt
   ```

2. **Identify Politically Active Nonprofit Leaders**
   ```python
   # Load nonprofit donor analysis
   donors = pd.read_parquet('data/gold/states/MA/campaigns_nonprofit_donors.parquet')
   
   # See which nonprofit officers donate politically
   print(donors.groupby('organization_name')['contribution_amount'].sum())
   ```

3. **Map Donor Networks in Healthcare Policy**
   ```python
   # Find health sector political contributions
   health_contribs = contributions[
       contributions['contributor_employer'].str.contains('Health', case=False, na=False)
   ]
   ```

## 📊 Directory Structure

```
data/gold/states/{STATE}/
├── campaigns_candidates.parquet          ← NEW
├── campaigns_committees.parquet          ← NEW  
├── campaigns_contributions.parquet       ← NEW
├── campaigns_nonprofit_donors.parquet    ← NEW (Analysis)
├── nonprofits_organizations.parquet      (Links via employer)
├── contacts_nonprofit_officers.parquet   (Links via name)
└── grants_revenue_sources.parquet        (Cross-reference)
```

## 🚀 Quick Start

### 1. Get FEC API Key
Visit: https://api.data.gov/signup/
- Free tier: 1,000 requests/hour
- Instant activation

### 2. Set Environment Variable
```bash
echo 'FEC_API_KEY="your_key_here"' >> .env
```

### 3. Create Gold Tables
```bash
# Activate environment
source .venv/bin/activate

# Create campaign finance tables for Massachusetts
python pipeline/create_campaigns_gold_tables.py \
  --state MA \
  --cycle 2024 \
  --max-contributions 10000
```

### 4. Analyze Data
```python
import pandas as pd

# Load nonprofit donor analysis
donors = pd.read_parquet('data/gold/states/MA/campaigns_nonprofit_donors.parquet')

# Top nonprofit organizations by political giving
print(donors.groupby('organization_name').agg({
    'contribution_amount': 'sum',
    'contributor_name': 'count'
}).sort_values('contribution_amount', ascending=False).head(10))
```

## 📖 API Reference

### Main Classes

**`CampaignsGoldTableCreator`** - Pipeline for creating gold tables
- `create_campaigns_candidates(cycle)` - Extract candidate data
- `create_campaigns_committees(cycle)` - Extract committee data
- `create_campaigns_contributions(min_amount, max_records, cycle)` - Extract contributions
- `create_campaigns_nonprofit_donors(contributions_df)` - Analyze nonprofit leadership donations
- `create_all_campaigns_tables(cycle, min_contribution_amount, max_contributions)` - Run full pipeline

**`OpenFECAPI`** (from `discovery/fec_integration.py`) - API client
- `search_individual_contributions(...)` - Search contributions
- `search_candidates(...)` - Find candidates
- `search_committees(...)` - Find PACs/committees

## 🔗 Related Files

### Existing Files (Enhanced)
- [`discovery/fec_integration.py`](../discovery/fec_integration.py) - FEC API client (already existed)
- [`website/docs/integrations/fec-political-contributions.md`](../website/docs/integrations/fec-political-contributions.md) - General integration guide (already existed)

### New Files (Created)
- [`pipeline/create_campaigns_gold_tables.py`](../pipeline/create_campaigns_gold_tables.py) - **NEW** - Gold table pipeline
- [`examples/demo_fec_integration.py`](../examples/demo_fec_integration.py) - **NEW** - Demo script
- [`website/docs/integrations/fec-campaign-finance.md`](../website/docs/integrations/fec-campaign-finance.md) - **NEW** - Technical guide

## 🎯 Future Enhancements

Potential additions to consider:

1. **Add to main orchestration script**
   - Update `scripts/create_all_gold_tables.py` to include campaigns pipeline

2. **Dashboard integration**
   - Add FEC visualizations to React app
   - Display political connections on nonprofit profiles
   - Show donor network graphs

3. **Automated analysis**
   - Scheduled updates (campaigns data updated daily by FEC)
   - Alerts for new major contributions
   - Influence score calculations

4. **Extended matching**
   - Fuzzy name matching for officers
   - Organization name normalization
   - Cross-reference with local officials data

## 📝 Documentation Links

- **Technical Guide:** [FEC Campaign Finance](../website/docs/integrations/fec-campaign-finance.md)
- **General Guide:** [FEC Political Contributions](../website/docs/integrations/fec-political-contributions.md)
- **Demo Script:** [examples/demo_fec_integration.py](../examples/demo_fec_integration.py)
- **API Client:** [discovery/fec_integration.py](../discovery/fec_integration.py)
- **Pipeline Module:** [pipeline/create_campaigns_gold_tables.py](../pipeline/create_campaigns_gold_tables.py)

## ✅ Checklist for Integration

- [x] Create pipeline module for gold table generation
- [x] Add example demo script
- [x] Write comprehensive documentation
- [ ] Add to main orchestration script (optional)
- [ ] Create React dashboard components (optional)
- [ ] Set up automated updates (optional)

---

**Implementation Date:** April 28, 2026
**Author:** GitHub Copilot
**License:** MIT (consistent with project)
