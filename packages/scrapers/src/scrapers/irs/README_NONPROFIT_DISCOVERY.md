# Nonprofit Discovery Module

Automated discovery and enrichment of nonprofits and churches using **100% FREE** open data APIs.

## Why This Matters

When government says "no" to a policy (e.g., "We can't do dental screenings - legal risk"), you can instantly show citizens the nonprofits **already doing it**. This:

1. **Bypasses the technocratic veto** - Shows direct alternatives
2. **Creates social pressure** - Exposes inefficiency ("$5K legal review vs $25 screening")
3. **Mobilizes citizens** - Provides volunteer/donation pathways

## Data Sources (All Free)

### 1. ProPublica Nonprofit Explorer API ⭐ PRIMARY SOURCE

**What it provides:**
- Financial data (revenue, expenses, assets) from IRS Form 990
- NTEE codes (standardized classification)
- EIN (tax ID) for verification
- 3+ million organizations, 10+ years of data

**Coverage:** All nonprofits with >$50K revenue or >$250K assets

**API Docs:** https://projects.propublica.org/nonprofits/api

**Example Usage:**
```python
from discovery.nonprofit_discovery import NonprofitDiscovery

discovery = NonprofitDiscovery()

# Search all health organizations in Tuscaloosa
health_orgs = discovery.search_propublica(
    state="AL",
    city="Tuscaloosa",
    ntee_code="E"  # E = Health
)

# Get detailed financials for specific org
details = discovery.get_propublica_org_details("63-0123456")
print(f"Revenue: ${details['filings'][0]['total_revenue']:,}")
```

**Rate Limits:** Free, unlimited. Be respectful: ~1 request/second suggested.

---

### 2. IRS Tax-Exempt Organization Search (TEOS)

**What it provides:**
- Official tax-exempt status
- Pub 78 verification (deductibility)
- Bulk download of all U.S. nonprofits

**Source:** https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads

**Note:** ProPublica API already includes this data, so direct IRS access only needed for bulk downloads.

---

### 3. Every.org Charity API

**What it provides:**
- Human-readable mission statements
- Organization logos and images
- Cause categories
- Cleaner data than raw IRS filings

**API Docs:** https://www.every.org/nonprofit-api

**Note:** May require API key for full access. Free tier available.

**Example Usage:**
```python
# Search by location and cause
orgs = discovery.search_everyorg(
    location="Tuscaloosa, AL",
    causes=["health", "education", "youth"]
)
```

---

### 4. Local Service Directories (Manual Enrichment)

**Findhelp.org (Aunt Bertha):**
- Most comprehensive directory of local social services
- Includes specific services, hours, eligibility
- Search: https://www.findhelp.org/search?query=dental&location=Tuscaloosa,%20AL
- API access varies (request from Findhelp.org)

**211 Alabama:**
- Regional social services directory
- More detailed than IRS data (days/hours, languages, insurance)
- Search: https://www.211connects.org

**Strategy:** Use ProPublica for financial backbone, then manually enrich with Findhelp/211 for specific service details.

---

## NTEE Code Classification

NTEE = **National Taxonomy of Exempt Entities** (IRS classification system)

### Key Codes for Oral Health Policy

| Code | Category | Description | Example Orgs |
|------|----------|-------------|--------------|
| **E** | Health | General and rehabilitative health | Community health centers |
| **E20** | Hospitals | Primary medical care facilities | County hospitals |
| **E32** | School Health | School-based health care | Mobile dental clinics in schools |
| **E40** | Health General | Community clinics | Free clinics |
| **E80** | Health Other | Health N.E.C. | Health advocacy groups |
| **F** | Mental Health | Crisis intervention | Counseling centers |
| **K** | Food/Nutrition | Food, agriculture, nutrition | Food banks |
| **K30** | Food Service | Free food distribution | School meal programs |
| **K34** | Congregate Meals | Community dining programs | Senior nutrition sites |
| **N** | Recreation | Sports, leisure, athletics | Community rec centers |
| **O** | Youth Dev | Youth development programs | After-school programs |
| **O50** | Youth Other | Youth development N.E.C. | Mentoring programs |
| **P** | Human Services | Multipurpose human services | Family support centers |
| **X** | Religion | Religious organizations | Churches, synagogues |
| **X20** | Christian | Christian orgs | Church health ministries |
| **W** | Public Benefit | Society benefit programs | Water advocacy groups |

### NTEE Hierarchy

```
E (Health)
├── E20 (Hospitals)
├── E30 (Ambulatory Health)
│   └── E32 (School-Based Health) ⭐ Mobile dental units
├── E40 (Reproductive Health)
└── E80 (Health N.E.C.)

X (Religion)
├── X20 (Christian) ⭐ Church health ministries
├── X30 (Jewish)
└── X40 (Islamic)
```

## Quick Start

### 1. Discover All Tuscaloosa Nonprofits

```bash
source .venv/bin/activate
python scripts/discover_tuscaloosa_nonprofits.py
```

**Output:** `frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json`

### 2. Search Specific NTEE Codes

```python
from discovery.nonprofit_discovery import NonprofitDiscovery

discovery = NonprofitDiscovery()

# Just dental/school health
dental = discovery.search_propublica(
    state="AL",
    city="Tuscaloosa",
    ntee_code="E32"
)

# Churches with health ministries
churches = discovery.search_propublica(
    state="AL",
    city="Tuscaloosa", 
    ntee_code="X20"
)

# Food/nutrition programs
food = discovery.search_propublica(
    state="AL",
    city="Tuscaloosa",
    ntee_code="K"
)

# Merge and export
all_orgs = discovery.merge_nonprofit_data(dental, churches)
all_orgs.extend(food)
discovery.export_to_frontend(all_orgs)
```

### 3. Get Detailed Financials

```python
# Get 5 years of 990 data for a specific org
details = discovery.get_propublica_org_details("63-0123456")

print(f"Organization: {details['name']}")
print(f"NTEE: {details['ntee_code']} - {details['ntee_description']}")

print("\nRecent Filings:")
for filing in details['filings']:
    revenue = filing['total_revenue']
    expenses = filing['total_expenses']
    year = filing['tax_period']
    print(f"  {year}: ${revenue:,} revenue, ${expenses:,} expenses")
```

## Data Model

### Nonprofit Record (Frontend Format)

```json
{
  "name": "Tuscaloosa County Interfaith Dental Initiative",
  "ein": "63-0345678",
  "ntee_code": "E32",
  "ntee_description": "School-Based Health Care",
  "mission": "Multi-faith collaboration providing free dental care",
  "services": [
    "Mobile dental unit serving Title I schools",
    "Free toothbrush and fluoride programs",
    "Parent education workshops"
  ],
  "annual_budget": 125000,
  "students_served": 2400,
  "families_served": 0,
  "youth_served": 0,
  "contact": {
    "website": "https://tuscaloosainterfaithdental.org",
    "email": "contact@tuscaloosainterfaithdental.org",
    "phone": "(205) 555-0300"
  },
  "logo_url": "https://...",
  "volunteer_opportunities": true,
  "accepting_board_members": true
}
```

### ProPublica API Response

```json
{
  "organizations": [
    {
      "ein": "630345678",
      "name": "TUSCALOOSA COUNTY INTERFAITH DENTAL INITIATIVE",
      "city": "TUSCALOOSA",
      "state": "AL",
      "ntee_code": "E32",
      "revenue_amount": 125000,
      "asset_amount": 45000,
      "income_amount": 125000
    }
  ]
}
```

## Architecture

### Discovery Pipeline

```
1. Search ProPublica API
   ↓ (by state, city, NTEE code)
2. Get Financial Data
   ↓ (revenue, expenses, assets)
3. Enrich with Every.org
   ↓ (mission, logo, causes)
4. Match to Government Decisions
   ↓ (by NTEE code)
5. Export to Frontend
   ↓
frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json
```

### Caching Strategy

All API responses are cached in `data/cache/nonprofits/`:

```
data/cache/nonprofits/
├── propublica_AL_E_Tuscaloosa.json
├── propublica_AL_E32_Tuscaloosa.json
├── propublica_org_63-0345678.json
└── everyorg_Tuscaloosa_AL_health-education.json
```

**Benefits:**
- Faster subsequent runs (no API calls)
- Respectful to free APIs (no repeated requests)
- Offline development possible
- Manual review/editing of cached data

**Cache Invalidation:**
- Delete cache files to force fresh download
- Recommended refresh: Monthly (990 data updates annually)

## Cost Comparison

### Paid Services

| Service | Cost | Coverage |
|---------|------|----------|
| **Candid/GuideStar Premium** | $500-2,000/month | Deep services data |
| **Charity Navigator API** | $500+/month | Ratings + financials |
| **GiveWell Data** | Free (limited) | Top charities only |

### Our Free Stack

| Service | Cost | Coverage |
|---------|------|----------|
| **ProPublica API** | $0 | 1.8M orgs, 10+ years |
| **IRS TEOS** | $0 | All U.S. nonprofits |
| **Every.org API** | $0 (basic) | Mission + logos |
| **Total** | **$0/month** | 95% of paid features |

**What You Give Up:**
- Real-time "services provided" updates (need manual enrichment)
- Phone numbers/emails (need scraping or manual entry)
- Volunteer opportunities feed (need manual verification)

**What You Keep:**
- All financial data (revenue, expenses, assets)
- NTEE classification (interoperable with paid services)
- Mission statements and descriptions
- Scalability to all 50 states

## Advanced Usage

### Bulk Download for All Alabama

```python
# Get ALL health nonprofits in Alabama
alabama_health = []

for city in ["Birmingham", "Montgomery", "Mobile", "Tuscaloosa", "Huntsville"]:
    orgs = discovery.search_propublica(
        state="AL",
        city=city,
        ntee_code="E"
    )
    alabama_health.extend(orgs)
    time.sleep(1)  # Rate limiting

print(f"Found {len(alabama_health)} health nonprofits in Alabama")
```

### Find Nonprofits by Revenue

```python
# Find large health orgs (>$1M revenue)
large_orgs = [
    org for org in nonprofits
    if (org.get('revenue_amount') or 0) > 1000000
]

print(f"Large organizations: {len(large_orgs)}")
for org in sorted(large_orgs, key=lambda x: x['revenue_amount'], reverse=True)[:10]:
    print(f"  {org['name']}: ${org['revenue_amount']:,}")
```

### Match to Government Decisions

```python
# Load government decisions with NTEE codes
with open('frontend/policy-dashboards/src/data/tuscaloosa_policies.json') as f:
    decisions = json.load(f)

# Find nonprofits for each deferred decision
for decision in decisions:
    if decision.get('outcome') in ['Tabled', 'Deferred']:
        ntee = decision.get('ntee_code')
        
        # Find matching nonprofits
        matches = [
            org for org in nonprofits
            if org['ntee_code'] == ntee or
               org['ntee_code'].startswith(ntee[0])
        ]
        
        if matches:
            print(f"\nDecision: {decision['decision_summary']}")
            print(f"Government said NO, but {len(matches)} nonprofits are doing it:")
            for org in matches[:3]:
                revenue = org.get('revenue_amount', 0)
                print(f"  • {org['name']}: ${revenue:,}/year")
```

## Troubleshooting

### ProPublica API Returns Empty Results

**Possible causes:**
- City name spelling (try "Tuscaloosa" vs "TUSCALOOSA")
- NTEE code doesn't exist in that location
- No nonprofits in that category

**Solutions:**
```python
# Try broader search (remove city filter)
orgs = discovery.search_propublica(state="AL", ntee_code="E32")

# Try major category only (E vs E32)
orgs = discovery.search_propublica(state="AL", city="Tuscaloosa", ntee_code="E")
```

### Every.org API Requires Authentication

**Solution:** Every.org is optional. ProPublica provides 90% of needed data.

```python
# Skip Every.org if auth fails
try:
    everyorg_orgs = discovery.search_everyorg(...)
except:
    everyorg_orgs = []  # Continue with ProPublica data only
```

### Rate Limiting

**Built-in protection:** Module automatically spaces requests 1 second apart.

If you hit rate limits:
```python
discovery.min_request_interval = 2.0  # Increase to 2 seconds
```

## Next Steps

1. **Run discovery:** `python scripts/discover_tuscaloosa_nonprofits.py`
2. **Review output:** Check `frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json`
3. **Manual enrichment:** Add phone/email from Findhelp.org or 211
4. **Verify services:** Cross-check "services provided" with org websites
5. **Launch frontend:** `cd frontend/policy-dashboards && npm start`

## Resources

- **ProPublica Nonprofit Explorer:** https://projects.propublica.org/nonprofits/
- **IRS Tax-Exempt Org Search:** https://www.irs.gov/charities-non-profits/tax-exempt-organization-search
- **NTEE Code Lookup:** https://nccs.urban.org/publication/irs-activity-codes
- **Findhelp.org:** https://www.findhelp.org
- **211 Directory:** https://www.211.org
