---
sidebar_position: 4
---

# FEC Political Contributions

Track political donations and their relationship to nonprofit leadership, policy decisions, and grant awards.

## Overview

The Federal Election Commission (FEC) provides comprehensive data on political contributions. Integrating this with your nonprofit and grant data reveals important connections between:

- **Nonprofit leadership** and political engagement
- **Political donations** and federal grant awards  
- **Policy advocacy** and campaign finance
- **Jurisdiction politics** and oral health funding

**API Documentation**: https://api.open.fec.gov/developers/

## What You Get

### FEC Data (NEW)

✅ **Individual Contributions**:
- Contributor name, address, employer
- Contribution amount and date
- Recipient (candidate or committee)
- Employer information (links to nonprofits!)

✅ **Candidate Information**:
- Office (House, Senate, President)
- Party affiliation
- State and district
- Election cycle

✅ **Committee Finances**:
- PAC and Super PAC spending
- Committee receipts and disbursements
- Independent expenditures

### Combined with Your Data

```
FEC Contributions     Your Nonprofit Data     IRS 990 / Grants.gov
─────────────────     ───────────────────     ───────────────────
John Smith      ────> Board Member at    ────> Received $2M
$5,000 to Sen X       MA Dental Clinic        federal grant
2024-06-15            Executive Director      2024-09-01
                      Salary: $150k
```

## Use Cases

### 1. Track Politically Active Nonprofit Leaders

Find which nonprofit executives and board members make political donations:

```python
from discovery.fec_integration import OpenFECAPI, PoliticalContributionMatcher

# Initialize API (get free key at https://api.data.gov/signup/)
api = OpenFECAPI(api_key="your_api_key_here")

# Load nonprofit officers (from IRS 990 data)
import pandas as pd
officers = pd.read_parquet("data/gold/states/MA/nonprofits_officers.parquet")

# Find their political contributions
matcher = PoliticalContributionMatcher(api)
contributions = matcher.find_nonprofit_leadership_contributions(
    officers_df=officers,
    state_code="MA",
    min_amount=200,
    election_cycle="2024"
)

print(f"Found {len(contributions):,} political contributions")
print(f"Total donated: ${contributions['contribution_amount'].sum():,.2f}")
```

### 2. Analyze Political Influence on Grant Awards

Compare political donations with federal grant awards:

```python
# Load grants data
grants = pd.read_parquet("data/gold/states/MA/grants_revenue_sources.parquet")

# Analyze influence patterns
influence_analysis = matcher.analyze_political_influence(
    contributions_df=contributions,
    grants_df=grants
)

# Which nonprofits have politically active leadership AND received grants?
influential_orgs = influence_analysis[
    (influence_analysis['total_political_donations'] > 1000) &
    (influence_analysis['total_grants_received'] > 100000)
]
```

### 3. Map Donor Networks in Health Policy

Track which health policy advocates donate to which campaigns:

```python
# Search for contributions from health sector
health_contributions = api.search_individual_contributions(
    contributor_employer="Health",
    contributor_state="MA",
    min_amount=1000,
    min_date="2024-01-01"
)

# Identify patterns
# - Which candidates get health sector donations?
# - Do dental/oral health professionals favor certain parties?
# - How does this correlate with oral health legislation?
```

## API Access

### Get Your Free API Key

1. Sign up at: https://api.data.gov/signup/
2. Receive API key via email (instant)
3. Use in API calls (see examples below)

**Note**: `DEMO_KEY` is available for testing but has strict limits (30 requests/hour)

### Search Individual Contributions

```python
api = OpenFECAPI(api_key="your_key")

# Search by contributor name
results = api.search_individual_contributions(
    contributor_name="John Smith",
    contributor_state="MA",
    min_amount=200
)

# Search by employer (find nonprofit employee donations)
results = api.search_individual_contributions(
    contributor_employer="Community Health Center",
    min_amount=500
)

# Search by amount and date range
results = api.search_individual_contributions(
    contributor_state="MA",
    min_amount=1000,
    max_amount=5000,
    min_date="2024-01-01",
    max_date="2024-12-31"
)
```

### Search Candidates

```python
# Find Massachusetts candidates
candidates = api.search_candidates(
    state="MA",
    office="S",  # Senate
    party="DEM",
    cycle=2024
)

# Find all House candidates
house_reps = api.search_candidates(
    state="MA",
    office="H",  # House
    cycle=2024
)
```

## Data Schema

### Contribution Fields

| Field | Description | Example |
|-------|-------------|---------|
| `contributor_name` | Individual donor name | John Smith |
| `contributor_city` | City | Boston |
| `contributor_state` | State | MA |
| `contributor_employer` | Employer name | MA Dental Clinic |
| `contributor_occupation` | Job title | Executive Director |
| `contribution_receipt_amount` | Donation amount | 2500.00 |
| `contribution_receipt_date` | Date of contribution | 2024-06-15 |
| `committee_name` | Recipient committee | Smith for Senate |
| `candidate_name` | Candidate (if applicable) | Jane Doe |

### Candidate Fields

| Field | Description | Example |
|-------|-------------|---------|
| `candidate_id` | FEC candidate ID | H0MA05123 |
| `name` | Candidate name | Jane Doe |
| `office` | Office type | H, S, P |
| `state` | State | MA |
| `district` | Congressional district | 05 |
| `party` | Party affiliation | DEM, REP |
| `cycles` | Election cycles | [2024, 2022] |

## Bulk Data Download

For comprehensive historical analysis, download bulk files:

```python
from discovery.fec_integration import FECBulkDataLoader

loader = FECBulkDataLoader()

# Download 2024 cycle data (WARNING: Large file ~3GB)
zip_file = loader.download_individual_contributions(cycle="2024")

# Parse with filters to reduce memory usage
contributions_df = loader.parse_individual_contributions(
    zip_path=zip_file,
    state_filter="MA",  # Only Massachusetts
    employer_filter="Health",  # Health sector only
    min_amount=200  # Significant contributions only
)
```

**Warning**: Bulk files are 1-5 GB. Use filters or the API for smaller queries.

## Integration with Your Data

### Complete Political-Financial Picture

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR DATA ECOSYSTEM                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  FEC Contributions          Nonprofit Data       Grants     │
│  ─────────────────          ──────────────       ──────     │
│  John Smith           ────> Board Member    <──── $2M       │
│  $5k to Sen X                MA Dental           Federal    │
│  2024-06-15                  Exec Director        Grant     │
│                              Salary: $150k        2024-09   │
│                                                             │
│  Voter Data                 Jurisdiction         Meetings   │
│  ───────────                ────────────         ────────   │
│  District: D+15       ────> Boston, MA     <──── Minutes    │
│  Dem majority                90,000 pop           discussing│
│  High turnout                                    fluoride  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Analysis Questions You Can Answer

1. **Political Influence**:
   - Do nonprofits with politically active leaders receive more federal grants?
   - What's the timeline from donation → grant award?
   - Which party's donors get more oral health funding?

2. **Advocacy Networks**:
   - Which dental health advocates donate to which candidates?
   - Do oral health nonprofits coordinate political giving?
   - How does political engagement correlate with policy success?

3. **Jurisdiction Politics**:
   - Do Democratic or Republican areas get more oral health grants?
   - Does legislator party affiliation affect local fluoridation votes?
   - Political polarization of oral health policy?

4. **Follow the Money**:
   - Corporate → Political donations → Policy decisions
   - Nonprofit leaders → Campaign contributions → Federal grants
   - Special interest influence on public health policy

## Example Analysis

### Which MA Health Nonprofits Have Political Connections?

```python
import pandas as pd
from discovery.fec_integration import OpenFECAPI, PoliticalContributionMatcher

# 1. Load your data
nonprofits = pd.read_parquet("data/gold/states/MA/nonprofits_organizations.parquet")
officers = pd.read_parquet("data/gold/states/MA/nonprofits_officers.parquet")
grants = pd.read_parquet("data/gold/states/MA/grants_revenue_sources.parquet")

# 2. Find political contributions from nonprofit leaders
api = OpenFECAPI(api_key="your_key")
matcher = PoliticalContributionMatcher(api)

contributions = matcher.find_nonprofit_leadership_contributions(
    officers_df=officers,
    state_code="MA",
    min_amount=200,
    election_cycle="2024"
)

# 3. Analyze influence
influence = matcher.analyze_political_influence(
    contributions_df=contributions,
    grants_df=grants
)

# 4. Results
print(f"Nonprofits with political donations: {len(influence):,}")
print(f"Total donated: ${influence['total_political_donations'].sum():,.2f}")
print(f"Total grants received: ${influence['total_grants_received'].sum():,.2f}")
print(f"ROI ratio: {influence['total_grants_received'].sum() / influence['total_political_donations'].sum():.1f}x")
```

## Rate Limiting

OpenFEC API limits:

| API Key | Rate Limit |
|---------|------------|
| `DEMO_KEY` | 30 requests/hour |
| Registered key | 1,000 requests/hour |

Our implementation includes automatic rate limiting (0.2s between requests).

## Privacy & Ethics

**Important Considerations**:

1. **Public Data**: FEC contributions are public record
2. **Correlation ≠ Causation**: Political donations don't prove influence
3. **Context Matters**: Contributions may be personal, not institutional
4. **Transparency**: Be clear about limitations in your analysis
5. **Fairness**: Present data without partisan bias

**Best Practices**:
- Focus on patterns, not individual actors
- Provide full context for findings
- Acknowledge limitations of correlation analysis
- Use for transparency, not to imply wrongdoing

## Next Steps

1. **Get API Key**: https://api.data.gov/signup/
2. **Test Integration**:
   ```bash
   python scripts/discovery/fec_integration.py --api-key YOUR_KEY --state MA --employer "Health"
   ```
3. **Match to Your Data**:
   - Link FEC contributions to nonprofit officers
   - Compare with grant awards
   - Analyze political patterns
4. **Build Dashboard**:
   - "Political Connections" widget
   - Transparency reporting
   - Influence analysis visualizations

## Related Integrations

- **[Grants.gov API](grants-gov-api.md)**: Federal grant opportunities
- **IRS Form 990** (your existing data): Nonprofit finances
- **Voter Data**: Jurisdiction political demographics
- **OpenStates**: State legislator information

## Additional Resources

- [OpenFEC API Documentation](https://api.open.fec.gov/developers/)
- [FEC Bulk Data Downloads](https://www.fec.gov/data/browse-data/?tab=bulk-data)
- [FEC File Format Documentation](https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/)
- [OpenSecrets.org](https://www.opensecrets.org/): Campaign finance research
- [FollowTheMoney.org](https://www.followthemoney.org/): State-level money tracking
