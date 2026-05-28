# Political Influence Analysis - Complete Data Integration

## The Complete Picture

This integration combines **4 major data sources** to reveal political connections in civic engagement and grant funding:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA ECOSYSTEM                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. IRS FORM 990           2. FEC CONTRIBUTIONS                    │
│  ───────────────           ───────────────────                     │
│  • Nonprofit orgs          • Political donations                   │
│  • Officer names           • Contributor employer ─────┐           │
│  • Compensation            • Donation amounts          │           │
│  • Revenue sources         • Recipients (candidates)   │           │
│                                                        │           │
│  3. GRANTS.GOV             4. VOTER DATA               │           │
│  ───────────────           ────────────                │           │
│  • Available grants        • Party affiliation         │           │
│  • Deadlines               • Elected officials         │           │
│  • Award amounts           • Turnout patterns          │           │
│  • Eligibility             • Demographics          ────┴───┐       │
│                                                            │       │
│                    ┌───────────────────────┐               │       │
│                    │  ANALYSIS QUESTIONS   │ <─────────────┘       │
│                    └───────────────────────┘                       │
│                                                                     │
│  • Political influence on grant awards?                            │
│  • Partisan patterns in oral health funding?                       │
│  • Advocacy networks and donor circles?                            │
│  • Timeline: Donation → Policy → Grant?                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Source Comparison

### What Each Source Provides

| Data Source | What You Get | Key Value |
|-------------|--------------|-----------|
| **IRS 990** (existing) | Nonprofit finances, officers, grants received | WHO got funded, HOW MUCH |
| **Grants.gov** (new) | Available grant opportunities, deadlines | WHAT'S available NOW |
| **FEC** (new) | Political donations by individuals | WHO donated to WHOM |
| **Voter Data** (new) | Jurisdiction politics, elected officials | POLITICAL CONTEXT |

### Combined Insights

When you integrate all four:

```
EXAMPLE: Massachusetts Dental Health Clinic

IRS 990:
├─ Organization: MA Dental Health Clinic (EIN: 12-3456789)
├─ Executive Director: Dr. Jane Smith
├─ Compensation: $150,000/year
├─ Revenue: $2M total
│  ├─ Government grants: $800,000 (40%)
│  ├─ Program service: $1M (50%)
│  └─ Donations: $200,000 (10%)

FEC Contributions:
├─ Dr. Jane Smith
│  ├─ $2,500 → Senator Elizabeth Warren (D-MA) - 2024-03-15
│  ├─ $1,000 → Rep. Joe Kennedy (D-MA-04) - 2024-06-01
│  └─ Total: $3,500 in 2024 cycle
│
└─ Board Member: Dr. John Doe
   ├─ $5,000 → HCFP PAC (Health Care for People) - 2024-02-10
   └─ Total: $5,000

Grants.gov:
├─ HRSA Oral Health Workforce Grant
│  ├─ Opportunity: HRSA-24-123
│  ├─ Posted: 2024-07-15
│  ├─ Deadline: 2024-12-31
│  ├─ Award: $500k-$2M
│  └─ Eligible: Community health centers (MATCH!)

Voter Data:
├─ Location: Boston, MA (Congressional District 4)
├─ District: D+15 (strong Democratic)
├─ Representative: Joe Kennedy (D) - recipient of Dr. Smith's donation
├─ Senator: Elizabeth Warren (D) - recipient of Dr. Smith's donation
└─ State Legislature: Democratic majority

TIMELINE ANALYSIS:
├─ 2024-03-15: Dr. Smith donates to Sen. Warren
├─ 2024-06-01: Dr. Smith donates to Rep. Kennedy
├─ 2024-07-15: HRSA grant posted (eligible for clinic)
├─ 2024-09-01: Clinic receives $500k HRSA grant (hypothetical)
└─ 2025-03-01: IRS 990 reports $800k government grants

QUESTIONS:
• Correlation or causation?
• Is this normal civic engagement?
• Does political activity predict grant success?
• Are there partisan patterns in health funding?
```

## Analysis Examples

### 1. Political Influence on Grant Awards

**Research Question**: Do nonprofits with politically active leadership receive more federal grants?

```python
# Load all data
nonprofits = pd.read_parquet("data/gold/states/MA/nonprofits_organizations.parquet")
officers = pd.read_parquet("data/gold/states/MA/nonprofits_officers.parquet")
grants = pd.read_parquet("data/gold/states/MA/grants_revenue_sources.parquet")
contributions = pd.read_parquet("data/gold/fec/political_contributions.parquet")

# Merge everything
full_data = (
    nonprofits
    .merge(officers, on='EIN', how='left')
    .merge(grants, on='EIN', how='left')
    .merge(contributions, left_on='person_name', right_on='contributor_name', how='left')
)

# Compare groups
politically_active = full_data[full_data['contribution_amount'].notna()]
not_active = full_data[full_data['contribution_amount'].isna()]

print(f"Politically active orgs: Avg grant = ${politically_active['government_grants'].mean():,.0f}")
print(f"Not active orgs: Avg grant = ${not_active['government_grants'].mean():,.0f}")

# Statistical test
from scipy import stats
t_stat, p_value = stats.ttest_ind(
    politically_active['government_grants'].dropna(),
    not_active['government_grants'].dropna()
)
print(f"p-value: {p_value:.4f}")
```

### 2. Partisan Patterns in Oral Health Funding

**Research Question**: Do Democratic or Republican areas get more oral health grants?

```python
# Enrich nonprofits with political context
from discovery.voter_data_integration import PoliticalContextEnricher

enricher = PoliticalContextEnricher()
enriched = enricher.add_political_context_to_nonprofits(
    nonprofits_df=nonprofits,
    contributions_df=contributions,
    legislators_df=legislators
)

# Group by party control
by_party = enriched.groupby('state_legislature_control').agg({
    'government_grants': 'mean',
    'EIN': 'count'
}).rename(columns={'EIN': 'org_count'})

print("Average Government Grants by State Legislature Control:")
print(by_party)

# Visualization
import matplotlib.pyplot as plt
by_party['government_grants'].plot(kind='bar')
plt.title("Avg Federal Grants: Democratic vs Republican States")
plt.ylabel("Average Grant Amount ($)")
plt.show()
```

### 3. Donor Networks in Health Policy

**Research Question**: Which candidates receive the most from health sector?

```python
# Health sector contributions
health_contribs = contributions[
    contributions['contributor_employer'].str.contains(
        'health|dental|clinic|hospital',
        case=False,
        na=False
    )
]

# Top recipients
top_recipients = health_contribs.groupby('committee_name').agg({
    'contribution_amount': 'sum',
    'contributor_name': 'count'
}).sort_values('contribution_amount', ascending=False).head(10)

print("Top 10 Recipients of Health Sector Donations:")
print(top_recipients)

# Network analysis
import networkx as nx

# Build graph: Donors → Candidates
G = nx.Graph()
for _, row in health_contribs.iterrows():
    donor = row['contributor_name']
    recipient = row['committee_name']
    amount = row['contribution_amount']
    G.add_edge(donor, recipient, weight=amount)

# Find central candidates (most donors)
centrality = nx.degree_centrality(G)
print("\nMost Connected Candidates:")
for candidate, score in sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"  {candidate}: {score:.3f}")
```

### 4. Timeline Analysis: Donation → Grant

**Research Question**: How long between political donation and grant award?

```python
# Merge contributions with grants by EIN
timeline_data = contributions.merge(
    grants,
    left_on='nonprofit_ein',
    right_on='ein',
    how='inner'
)

# Convert dates
timeline_data['contribution_date'] = pd.to_datetime(timeline_data['contribution_date'])
timeline_data['grant_date'] = pd.to_datetime(timeline_data['grant_award_date'])

# Calculate time difference
timeline_data['days_to_grant'] = (
    timeline_data['grant_date'] - timeline_data['contribution_date']
).dt.days

# Filter to positive (donation before grant)
before_grant = timeline_data[timeline_data['days_to_grant'] > 0]

print(f"Donations made BEFORE grant award: {len(before_grant):,}")
print(f"Average time: {before_grant['days_to_grant'].mean():.0f} days")
print(f"Median time: {before_grant['days_to_grant'].median():.0f} days")

# Histogram
before_grant['days_to_grant'].hist(bins=50)
plt.title("Time from Political Donation to Grant Award")
plt.xlabel("Days")
plt.ylabel("Frequency")
plt.show()
```

## Dashboard Features

### Political Connections Widget

Add to nonprofit profile pages:

```
┌────────────────────────────────────────────┐
│  MA Dental Health Clinic                   │
│  EIN: 12-3456789                           │
├────────────────────────────────────────────┤
│  💰 Political Connections                  │
│                                            │
│  Leadership Political Activity:            │
│  • 2 officers made political donations     │
│  • Total: $8,500 (2024 cycle)             │
│                                            │
│  Federal Grant Awards:                     │
│  • $800,000 government grants (2023)      │
│  • HRSA Oral Health Workforce Grant       │
│                                            │
│  Political Context:                        │
│  • District: MA-04 (D+15)                 │
│  • Representative: Joe Kennedy (D)         │
│  • Senator: Elizabeth Warren (D)           │
│                                            │
│  [View Full Disclosure] [Timeline Chart]   │
└────────────────────────────────────────────┘
```

### Transparency Report

Public disclosure page:

```
Political Finance Transparency Report
Massachusetts Oral Health Organizations
─────────────────────────────────────────

Summary:
• 145 health nonprofits in database
• 23 have politically active leadership (16%)
• $456,000 in political donations (2024)
• $45M in federal grants received (2023)

Top Donors (by organization):
1. MA Dental Association - $125,000
2. Community Health Network - $89,500
3. Boston Medical Center - $67,200

Top Recipients (candidates/committees):
1. Elizabeth Warren (D-MA) - $234,000
2. Ed Markey (D-MA) - $156,000
3. Various House candidates - $66,000

Partisan Breakdown:
• Democratic candidates: 78%
• Republican candidates: 18%
• Non-partisan: 4%

[Download Full Data] [Methodology]
```

## Ethical Considerations

### Important Disclaimers

1. **Correlation ≠ Causation**
   - Political donations don't prove quid pro quo
   - Many factors influence grant awards
   - Present data, not conclusions

2. **Personal vs. Institutional**
   - Officers donate as individuals, not on behalf of nonprofits
   - Political views are personal
   - Don't attribute individual actions to organizations

3. **Context is Critical**
   - Civic engagement is protected speech
   - Political donations are legal and transparent
   - Focus on patterns, not individuals

4. **Fairness and Balance**
   - Present all sides
   - Avoid partisan framing
   - Let users draw own conclusions

### Best Practices

✅ **DO**:
- Present data transparently
- Provide full methodology
- Allow users to verify
- Show aggregate patterns
- Respect privacy laws

❌ **DON'T**:
- Imply wrongdoing without evidence
- Selectively present data
- Use partisan language
- Focus on individuals
- Draw unsupported conclusions

## Implementation Checklist

- [ ] Get FEC API key (https://api.data.gov/signup/)
- [ ] Run FEC integration demo
- [ ] Match FEC data to your nonprofit officers
- [ ] Combine with Grants.gov data
- [ ] Add voter/political context
- [ ] Build analysis queries
- [ ] Create dashboard widgets
- [ ] Write transparency methodology
- [ ] Review for ethical concerns
- [ ] Launch with clear disclaimers

## ROI Summary

### Data Collection Effort

| Data Source | Setup Time | Cost | Maintenance |
|-------------|-----------|------|-------------|
| **IRS 990** | ✅ Done | Free | Automatic |
| **Grants.gov** | 5 min | Free | Daily cron |
| **FEC API** | 5 min (signup) | Free | Weekly batch |
| **Voter Data** | Varies | $-$$$ | Monthly |

**Total**: 10-30 minutes + optional vendor costs

### Value Delivered

**For Transparency**:
- Public disclosure of political-financial connections
- Trust through openness
- Accountability for nonprofits and officials

**For Analysis**:
- Understand influence patterns
- Track money in politics
- Identify advocacy networks
- Research civic engagement

**For Advocacy**:
- Strategic political engagement
- Optimize advocacy efforts
- Learn from successful orgs
- Navigate political landscape

**Differentiation**:
- Unique feature - no one else combines these
- Media interest - compelling stories
- Academic value - research partnerships
- Impact - better democracy

## Example Queries

Save these for your analysis toolkit:

```sql
-- 1. Which nonprofits have politically active leaders?
SELECT 
    n.organization_name,
    COUNT(DISTINCT c.contributor_name) as donor_count,
    SUM(c.contribution_amount) as total_donated,
    n.government_grants
FROM nonprofits n
JOIN officers o ON n.ein = o.ein
JOIN contributions c ON o.person_name = c.contributor_name
GROUP BY n.ein
ORDER BY total_donated DESC;

-- 2. Partisan breakdown by state
SELECT 
    state,
    party_lean,
    COUNT(*) as org_count,
    AVG(government_grants) as avg_grants
FROM nonprofits
GROUP BY state, party_lean;

-- 3. Timeline: Donation to grant
SELECT 
    c.contribution_date,
    c.contributor_name,
    c.contribution_amount,
    g.grant_award_date,
    g.grant_amount,
    DATEDIFF(g.grant_award_date, c.contribution_date) as days_between
FROM contributions c
JOIN grants g ON c.nonprofit_ein = g.ein
WHERE g.grant_award_date > c.contribution_date
ORDER BY days_between;
```

## Next Steps

1. **Get API Keys**:
   - FEC: https://api.data.gov/signup/ (instant, free)
   - OpenStates: https://openstates.org/accounts/profile/ (optional)
   - Google Civic: https://console.cloud.google.com (optional)

2. **Run Demos**:
   ```bash
   python examples/demo_political_influence.py --api-key YOUR_FEC_KEY
   ```

3. **Generate Full Dataset**:
   - Match all officers to FEC contributions
   - Combine with Grants.gov opportunities
   - Add voter/political context

4. **Build Features**:
   - Political connections widget
   - Transparency report page
   - Timeline visualizations
   - Network graphs

5. **Launch with Context**:
   - Write clear methodology
   - Add ethical disclaimers
   - Provide full data downloads
   - Allow verification

**The bottom line**: This creates the most comprehensive view of political influence in civic engagement available anywhere. Use it responsibly! 🎯
