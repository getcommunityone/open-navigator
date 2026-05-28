# Political Finance Data Integration - Quick Start

## 🚀 Overview

You now have **3 major data integrations** that work together to reveal political connections in civic engagement:

1. **Grants.gov API** - Federal grant opportunities (FUTURE funding)
2. **FEC Political Contributions** - Campaign donations (POLITICAL connections)
3. **Voter Data** - Political demographics (CONTEXT)

Combined with your existing **IRS Form 990 data** (PAST funding), you have the most comprehensive political-financial tracking system for civic engagement.

## 📊 The Complete Data Ecosystem

```
┌──────────────────────────────────────────────────────────────────┐
│               YOUR COMPLETE DATA ECOSYSTEM                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  EXISTING DATA              NEW INTEGRATIONS                     │
│  ──────────────             ────────────────                     │
│                                                                  │
│  IRS 990                    Grants.gov                          │
│  • 3M+ nonprofits      ───> • Federal grant opportunities       │
│  • $800k grants             • Application deadlines             │
│  • Officers                 • Award amounts                      │
│  • Financials               • Eligibility                        │
│                                   │                              │
│  Jurisdictions                    │     FEC                      │
│  • 90k+ cities          ──────────┴───> • Political donations   │
│  • Meeting minutes                      • Donor employers        │
│  • Contact info                         • Recipients             │
│  • Demographics                         • Amounts & dates        │
│                                               │                  │
│                                               │                  │
│                                         Voter Data               │
│                                         • Party affiliation      │
│                                         • Elected officials      │
│                                         • Turnout                │
│                                                                  │
│  COMBINED ANALYSIS:                                             │
│  ➤ Political influence on grant awards                          │
│  ➤ Donor networks in health policy                              │
│  ➤ Partisan patterns in funding                                 │
│  ➤ Timeline: Donation → Policy → Grant                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## ⚡ Quick Start

### 1. Get API Keys (5 minutes)

**FEC API** (Required for political data):
```bash
# Get free API key at:
https://api.data.gov/signup/

# Enter email → Receive key instantly
# Or use DEMO_KEY for testing (limited)
```

**Other APIs** (Optional):
- OpenStates (state legislators): https://openstates.org/accounts/profile/
- Google Civic (local officials): https://console.cloud.google.com

### 2. Test Integrations

**Test Grants.gov** (no key required):
```bash
python examples/demo_grants_gov.py
```
Output: Federal oral health grant opportunities → `data/gold/grants/`

**Test FEC** (requires API key):
```bash
python examples/demo_political_influence.py --api-key YOUR_FEC_KEY
```
Output: Political contributions from health sector → `data/gold/fec/`

### 3. Run Complete Analysis

```bash
# 1. Generate grant opportunities
python examples/demo_grants_gov.py

# 2. Find political connections
python examples/demo_political_influence.py --api-key YOUR_FEC_KEY

# 3. Match to your nonprofits (if you have officer data)
python scripts/discovery/fec_integration.py \
  --api-key YOUR_FEC_KEY \
  --state MA \
  --employer "health"
```

## 📚 Documentation

### Integration Guides

1. **[Grants.gov API](../website/docs/integrations/grants-gov-api.md)**
   - Federal grant opportunities
   - No API key required
   - Search by keyword, agency, funding category
   - Match to eligible nonprofits

2. **[FEC Political Contributions](../website/docs/integrations/fec-political-contributions.md)**
   - Individual campaign donations
   - Free API key required
   - Link to nonprofit employers
   - Track political influence

3. **Voter Data Integration**
   - Political demographics
   - Elected officials
   - State-specific sources
   - Commercial vendors (L2, Aristotle)

### Example Analyses

- **[Political Influence Integration](POLITICAL_INFLUENCE_INTEGRATION.md)** - Complete analysis examples
- **[Grants.gov Value](GRANTS_GOV_VALUE.md)** - Data comparison and ROI

## 🎯 Use Cases

### 1. Grant Opportunity Alerts

**Before**: Nonprofits miss deadlines

**After**: Automated alerts
```
"NEW Grant Alert: HRSA Oral Health Workforce Development"
• Award: $500k-$2M
• Deadline: Dec 31, 2024
• Your organization is eligible!
• Similar MA orgs received avg $800k from this program
```

### 2. Political Transparency

**Before**: Hidden connections

**After**: Public disclosure
```
Political Connections:
• 2 officers made political donations
• Total: $8,500 (2024 cycle)
• Recipients: Sen. Warren (D), Rep. Kennedy (D)
• Federal grants received: $800,000 (2023)
```

### 3. Influence Analysis

**Before**: Speculation about political influence

**After**: Data-driven analysis
```
Research Finding:
• Nonprofits with politically active leaders: $450k avg grant
• Nonprofits without political activity: $280k avg grant
• Difference: $170k (p < 0.05)
• Context: Many factors influence grants
```

### 4. Partisan Patterns

**Before**: Anecdotal observations

**After**: Quantitative analysis
```
Oral Health Funding by Political Context:
• Democratic-controlled states: $2.1M avg
• Republican-controlled states: $1.8M avg
• Swing states: $2.3M avg
• Analysis: More urban states (often blue) have more nonprofits
```

## 🗂️ File Structure

```
discovery/
├── grants_gov_integration.py       # Grants.gov API client
├── fec_integration.py              # FEC political contributions
└── voter_data_integration.py      # Voter data and elected officials

examples/
├── demo_grants_gov.py              # Grant opportunities demo
├── demo_political_influence.py     # FEC integration demo
├── GRANTS_GOV_VALUE.md            # Grants.gov data comparison
└── POLITICAL_INFLUENCE_INTEGRATION.md  # Complete analysis guide

website/docs/integrations/
├── grants-gov-api.md               # Grants.gov documentation
└── fec-political-contributions.md  # FEC documentation

data/gold/
├── grants/
│   └── oral_health_opportunities.parquet    # Federal grants
├── fec/
│   └── political_contributions.parquet      # Political donations
└── states/MA/
    ├── nonprofits_organizations.parquet     # Organizations
    ├── nonprofits_officers.parquet          # Leadership
    ├── grants_revenue_sources.parquet       # Revenue breakdown
    └── available_grants.parquet             # Matched opportunities
```

## 💡 Analysis Examples

### Find Political Connections

```python
from discovery.fec_integration import OpenFECAPI, PoliticalContributionMatcher
import pandas as pd

# Load your data
officers = pd.read_parquet("data/gold/states/MA/nonprofits_officers.parquet")

# Find political contributions
api = OpenFECAPI(api_key="your_key")
matcher = PoliticalContributionMatcher(api)

contributions = matcher.find_nonprofit_leadership_contributions(
    officers_df=officers,
    state_code="MA",
    min_amount=200
)

print(f"Found {len(contributions):,} political donations")
print(f"Total: ${contributions['contribution_amount'].sum():,.2f}")
```

### Match Grants to Nonprofits

```python
from discovery.grants_gov_integration import GrantsGovAPI, GrantMatcher

# Find oral health grants
api = GrantsGovAPI()
matcher = GrantMatcher(api)

grants = matcher.find_oral_health_grants(opp_statuses="posted")

# Load nonprofits
nonprofits = pd.read_parquet("data/gold/states/MA/nonprofits_organizations.parquet")

# Match grants to eligible MA orgs
matches = matcher.match_grants_to_state(
    state_code="MA",
    grants_df=grants,
    nonprofits_df=nonprofits
)

print(f"{len(matches):,} grant opportunities for MA orgs")
```

### Analyze Influence

```python
from discovery.fec_integration import PoliticalContributionMatcher

# Load all data
grants = pd.read_parquet("data/gold/states/MA/grants_revenue_sources.parquet")
contributions = pd.read_parquet("data/gold/fec/political_contributions.parquet")

# Analyze political influence patterns
matcher = PoliticalContributionMatcher(api)
influence = matcher.analyze_political_influence(
    contributions_df=contributions,
    grants_df=grants
)

# Results
print("Political Activity vs. Grant Awards:")
print(influence[['total_political_donations', 'total_grants_received']])
```

## 🔒 Privacy & Ethics

### Important Guidelines

✅ **DO**:
- Present data transparently
- Provide full context
- Allow verification
- Focus on patterns
- Respect privacy laws

❌ **DON'T**:
- Imply wrongdoing without evidence
- Selectively present data
- Use partisan language
- Target individuals
- Draw unsupported conclusions

### Disclaimers

1. **FEC data is public record** - legal, transparent political participation
2. **Correlation ≠ causation** - many factors influence grant awards
3. **Personal vs. institutional** - officers donate as individuals
4. **Context matters** - civic engagement is protected speech

## 📈 ROI Summary

### Setup Time
- Grants.gov: **0 minutes** (no auth required)
- FEC API: **5 minutes** (free signup)
- Voter data: **Varies** (state-specific or commercial)

### Cost
- Grants.gov: **FREE**
- FEC API: **FREE**
- Voter data: **FREE** (aggregated) or **$-$$$** (individual-level)

### Value
- **Differentiation**: Unique feature no one else has
- **Transparency**: Build trust through openness
- **Insights**: Data-driven political analysis
- **Advocacy**: Strategic engagement tools
- **Impact**: Better informed democracy

### Maintenance
- Grants.gov: Daily automated fetches (5 min setup)
- FEC: Weekly batch updates (cron job)
- Voter data: Monthly updates (varies by source)

## 🚦 Next Steps

### Immediate (Today)

- [ ] Get FEC API key (5 min): https://api.data.gov/signup/
- [ ] Run Grants.gov demo: `python examples/demo_grants_gov.py`
- [ ] Run FEC demo: `python examples/demo_political_influence.py --api-key KEY`
- [ ] Review generated data in `data/gold/`

### Short-term (This Week)

- [ ] Match grants to your nonprofits
- [ ] Find political connections in your officer data
- [ ] Create first analysis: donation → grant timeline
- [ ] Build basic dashboard widget

### Medium-term (This Month)

- [ ] Set up automated daily grant fetching
- [ ] Build email alert system for grant opportunities
- [ ] Create political transparency page
- [ ] Launch "Political Connections" feature

### Long-term (This Quarter)

- [ ] Integrate voter data (state or commercial)
- [ ] Build comprehensive influence analysis
- [ ] Create network visualizations
- [ ] Publish research findings
- [ ] Partner with journalists/researchers

## 🆘 Troubleshooting

### "No contributions found"
- Check API key is valid
- Try broader search parameters
- Use `DEMO_KEY` for testing (limited)
- Verify employer names match exactly

### "File not found"
- Run demos to generate data first
- Check file paths are correct
- Ensure you have MA nonprofit data
- Generate missing data (see commands above)

### "Rate limit exceeded"
- FEC API: 1,000 requests/hour with key
- Use DEMO_KEY sparingly (30/hour)
- Add delays between requests
- Batch operations overnight

### "Empty results"
- Many nonprofits have no political activity (normal!)
- Try different search parameters
- Expand date range
- Lower minimum amount

## 📞 Support

- **Documentation**: See `website/docs/integrations/`
- **Examples**: See `examples/` directory
- **Issues**: Check error messages and API docs
- **Questions**: Review analysis examples in POLITICAL_INFLUENCE_INTEGRATION.md

## 🎉 Success Metrics

You'll know it's working when you can answer:

✅ "Which federal oral health grants are available RIGHT NOW?"
✅ "Which nonprofit leaders made political donations?"
✅ "What's the relationship between donations and grants?"
✅ "Do partisan patterns exist in oral health funding?"
✅ "Which advocacy networks are most politically engaged?"

**You now have the most comprehensive political-financial tracking system for civic engagement. Use it to build transparency, enable advocacy, and strengthen democracy!** 🚀
