---
sidebar_position: 3
---

# Grants.gov API Integration

Track federal grant opportunities and match them to nonprofits in your database.

## Overview

The Grants.gov API provides access to **federal grant opportunities** from all federal agencies. This integration adds a NEW dimension to your data by tracking **available grants** (future opportunities) alongside your existing **IRS Form 990 data** (past awards).

**API Documentation**: https://www.grants.gov/api

## What You Get

### Data NOT in Your Current System

✅ **Federal Grant Opportunities**:
- Grant titles, descriptions, and purposes
- Funding amounts and award ceilings
- Eligibility criteria
- Application deadlines
- Opportunity status (forecasted, posted, closed, archived)
- Assistance Listing Numbers (ALN/CFDA)
- Agency contact information

✅ **Search Capabilities**:
- Filter by keyword (e.g., "oral health", "dental care")
- Filter by funding category (HL = Health)
- Filter by federal agency (HHS, NIH, CDC)
- Filter by opportunity status

### Authentication

**NO API KEY REQUIRED** for public endpoints (`search2` and `fetchOpportunity`)!

## Use Cases

### 1. Grant Opportunity Alerts

Alert nonprofits in your database about relevant funding opportunities:

```python
from discovery.grants_gov_integration import GrantsGovAPI, GrantMatcher

# Initialize API
api = GrantsGovAPI()
matcher = GrantMatcher(api)

# Find all oral health grants
oral_health_grants = matcher.find_oral_health_grants(
    opp_statuses="forecasted|posted"
)

print(f"Found {len(oral_health_grants):,} opportunities")
```

### 2. Match Grants to State Nonprofits

```python
import pandas as pd

# Load MA nonprofits
nonprofits = pd.read_parquet("data/gold/states/MA/nonprofits_organizations.parquet")

# Match grants to MA organizations
matches = matcher.match_grants_to_state(
    state_code="MA",
    grants_df=oral_health_grants,
    nonprofits_df=nonprofits
)

# Save results
matches.to_parquet("data/gold/states/MA/available_grants.parquet")
```

### 3. Track Funding Trends

Compare available opportunities (Grants.gov) with received funding (IRS 990):

```python
# What grants are AVAILABLE?
available = api.search_to_dataframe(
    keyword="oral health",
    funding_categories="HL",
    opp_statuses="posted"
)

# What grants were RECEIVED? (from IRS 990)
received = pd.read_parquet("data/gold/states/MA/grants_revenue_sources.parquet")

# Analysis: Are there gaps?
# - High demand categories with few opportunities?
# - Opportunities that aren't being utilized?
```

## Quick Start

### Search for Oral Health Grants

```bash
python scripts/discovery/grants_gov_integration.py \
  --oral-health \
  --output data/gold/grants
```

### Custom Search

```bash
python scripts/discovery/grants_gov_integration.py \
  --keyword "fluoridation" \
  --funding-category HL \
  --agency HHS \
  --output data/gold/grants
```

## API Endpoints

### search2

Search for grant opportunities:

```python
api = GrantsGovAPI()

results = api.search_opportunities(
    keyword="oral health",
    funding_categories="HL",      # Health
    agencies="HHS",                # Health & Human Services
    opp_statuses="forecasted|posted",
    rows=100
)
```

**Parameters**:
- `keyword`: Search term (e.g., "oral health", "dental")
- `funding_categories`: Category codes (HL=Health, ED=Education, ENV=Environment)
- `agencies`: Agency codes (HHS, HHS-NIH, HHS-CDC, EPA)
- `opp_statuses`: Pipe-separated statuses (forecasted|posted|closed|archived)
- `eligibilities`: Eligibility codes
- `aln`: Assistance Listing Number (formerly CFDA)
- `rows`: Results per page (max 100)

### fetchOpportunity

Get detailed information about a specific grant:

```python
details = api.fetch_opportunity(opportunity_id=289999)

# Access detailed data
synopsis = details['data']['synopsis']
eligibility = details['data']['eligibility']
funding = details['data']['fundingDetails']
```

## Data Schema

### Opportunity Fields

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Opportunity ID | 289999 |
| `opportunityNumber` | Grant number | HHS-2024-ACF-001 |
| `opportunityTitle` | Grant title | Oral Health Community Programs |
| `agencyCode` | Agency code | HHS |
| `agencyName` | Agency name | Health & Human Services |
| `openDate` | Application open date | 2024-10-15 |
| `closeDate` | Application deadline | 2024-12-31 |
| `opportunityStatus` | Status | posted, forecasted, closed |
| `cfdaList` | Assistance Listing Numbers | `[{"cfdaNumber": "93.223"}]` |
| `fundingCategories` | Funding category codes | HL (Health) |

## Integration with Existing Data

### Complete Grant Lifecycle Tracking

```
┌─────────────────────────┐
│  Grants.gov API         │  ← FUTURE: Available opportunities
│  (This Integration)     │
│  • Posted grants        │
│  • Eligibility          │
│  • Deadlines            │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Your Dashboard         │  ← PRESENT: Alert & match
│  • Match to nonprofits  │
│  • Send alerts          │
│  • Track applications   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  IRS Form 990           │  ← PAST: Received funding
│  (Existing Data)        │
│  • Government grants    │
│  • Foundation grants    │
│  • Revenue sources      │
└─────────────────────────┘
```

### Combined Analysis

```python
# Which MA nonprofits received federal health grants last year?
past_grants = pd.read_parquet("data/gold/states/MA/grants_revenue_sources.parquet")
federal_recipients = past_grants[past_grants['government_grants'] > 0]

# What federal health grants are available NOW?
current_opportunities = api.search_to_dataframe(
    keyword="health",
    funding_categories="HL",
    agencies="HHS",
    opp_statuses="posted"
)

# Analysis: Success rate, funding gaps, opportunity awareness
```

## Funding Categories

Common funding category codes:

| Code | Category | Examples |
|------|----------|----------|
| `HL` | Health | Oral health, mental health, public health |
| `ED` | Education | School programs, literacy |
| `ENV` | Environment | Clean water, pollution control |
| `FA` | Food & Agriculture | Nutrition, food safety |
| `CD` | Community Development | Housing, economic development |
| `O` | Other | Multi-purpose grants |

## Agency Codes

Major federal agencies:

| Code | Agency | Focus Areas |
|------|--------|-------------|
| `HHS` | Health & Human Services | Health programs |
| `HHS-NIH` | National Institutes of Health | Medical research |
| `HHS-CDC` | Centers for Disease Control | Public health |
| `HHS-HRSA` | Health Resources & Services | Healthcare access |
| `EPA` | Environmental Protection Agency | Environmental health |
| `ED` | Department of Education | School health programs |

## Rate Limiting

The API does not publish official rate limits, but best practices:

- **Recommended**: 1-2 requests per second
- **Polite**: 0.5-1 second delay between requests
- **Batch operations**: Use pagination (`rows=100`) to minimize requests

Our implementation includes automatic rate limiting (500ms delay).

## Error Handling

All API responses include an error code:

```python
response = api.search_opportunities(keyword="health")

if response.get("errorcode") == 0:
    # Success
    opportunities = response['data']['oppHits']
else:
    # Error
    print(f"Error: {response.get('msg')}")
```

## Next Steps

1. **Test the integration**:
   ```bash
   python scripts/discovery/grants_gov_integration.py --oral-health
   ```

2. **Schedule regular updates**:
   - Daily cron job to fetch new opportunities
   - Weekly digest emails to nonprofits
   - Dashboard widget showing "Latest Grants"

3. **Enhance matching**:
   - Filter by NTEE codes (oral health orgs only)
   - Check organization size (capacity to apply)
   - Historical success rate analysis

4. **Build alerts system**:
   - Email notifications for relevant grants
   - SMS alerts for approaching deadlines
   - Dashboard notifications for new opportunities

## Additional Resources

- [Grants.gov API Documentation](https://www.grants.gov/api)
- [API Guide](https://www.grants.gov/api/api-guide)
- [Assistance Listings (formerly CFDA)](https://sam.gov/content/assistance-listings)
- [Grants.gov Learning Center](https://www.grants.gov/learning-center)

## Related Data Sources

- **USAspending.gov API**: Actual grant awards and spending data (complements Grants.gov opportunities)
- **SAM.gov**: Entity registration and contract opportunities
- **IRS Form 990** (your existing data): Nonprofit financial reports showing received grants
