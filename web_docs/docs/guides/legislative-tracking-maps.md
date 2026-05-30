---
sidebar_position: 5
sidebar_label: Legislative Tracking Maps
---

# Creating Legislative Tracking Maps

Learn how to download state legislation data and create choropleth maps showing legislative activity across multiple social issues.

## 🎯 What You'll Create

Interactive maps similar to legislative tracking visualizations that show:

- **Type of Legislation:** Outright Ban, Restriction, Protection
- **Status:** Introduced (pending), Enacted (passed), Failed (defeated)
- **Geographic Distribution:** State-by-state view of legislative activity

Example use cases:
- Water fluoridation legislation tracker
- Abortion access legislation map
- Marijuana legalization progress
- Voting rights legislation
- LGBTQ+ protection laws
- Education policy (CRT, book bans, etc.)

---

## 🛠️ Prerequisites

### Choose Your Data Source

**⚡ RECOMMENDED: Bulk Downloads (Faster & Easier)**

Plural Policy offers bulk downloads of ALL state legislation - no API key needed!

```bash
# Download all 2024 legislation for all 50 states (CSV)
python scripts/bulk_legislative_download.py --year 2024 --format csv --merge

# Output: data/cache/legislation_bulk/all_states_2024.csv
# Contains: ALL bills from ALL states in one file!
```

**Advantages:**
- ✅ **No API key required** - Public bulk data
- ✅ **No rate limits** - Download encouraged
- ✅ **Faster** - One download vs thousands of API calls
- ✅ **Complete** - Entire legislative sessions
- ✅ **Offline** - Process locally without internet

**Alternative: Open States API (Real-time)**

For real-time bill tracking and search:

```bash
# Sign up: https://openstates.org/accounts/signup/
# Add to .env:
OPENSTATES_API_KEY=your-key-here
```

Use API when you need:
- Latest bill status (same-day updates)
- Search by specific keywords
- Subset of bills (not entire sessions)

---

### 1. Install Required Packages

```bash
# Core dependencies
pip install httpx pandas loguru python-dotenv

# Visualization libraries
pip install plotly matplotlib
```

### 2. Get Open States API Key (Free)

Open States provides state legislation data for all 50 states.

1. **Sign up:** https://openstates.org/accounts/signup/
2. **Get API key:** https://openstates.org/accounts/profile/
3. **Add to `.env`:**
   ```bash
   OPENSTATES_API_KEY=your-key-here
   ```

**Free Tier:**
- 50,000 requests per month
- Access to all 50 states
- Bill text, voting records, legislators

---

## 📊 Quick Start

### Method 1: Bulk Download (Recommended)

**Step 1: Download all 2024 legislation**
```bash
# Download CSV files for all 50 states
python scripts/bulk_legislative_download.py --year 2024 --format csv --merge
```

**Step 2: Process and categorize**
```python
from scripts.legislative_tracker import LegislativeTracker
import pandas as pd

tracker = LegislativeTracker()

# Load bulk downloaded data
df = pd.read_csv('data/cache/legislation_bulk/all_states_2024.csv')

# Categorize bills for fluoridation tracking
categorized = []
for _, bill in df.iterrows():
    cat = tracker.categorize_bill(bill.to_dict(), 'fluoridation')
    categorized.append(cat)

df_categorized = pd.DataFrame(categorized)

# Generate map
tracker.create_choropleth_map(df_categorized, "fluoridation")
```

**Output:**
- **Downloaded:** All 50 states in minutes (not hours)
- **Processed:** Categorized by issue type
- **Map:** `data/visualizations/fluoridation_map.html`

---

### Method 2: Open States API (Real-time)

**Step 1: Get API key**
```bash
# Sign up at https://openstates.org/accounts/signup/
# Add to .env:
OPENSTATES_API_KEY=your-key-here
```

**Step 2: Track issue**

```bash
# Track fluoridation legislation in 2024
python scripts/legislative_tracker.py \
  --issue fluoridation \
  --year 2024 \
  --visualize
```

**Output:**
- `data/cache/legislation/fluoridation_2024.csv` - Raw bill data
- `data/visualizations/fluoridation_map.html` - Interactive map
- `data/visualizations/fluoridation_legend.png` - Color legend

### Track Multiple Issues

```python
from scripts.legislative_tracker import LegislativeTracker
import asyncio

async def track_all_issues():
    tracker = LegislativeTracker()
    
    issues = ["fluoridation", "abortion", "marijuana", "voting", "lgbtq", "education"]
    
    for issue in issues:
        print(f"\n📊 Tracking {issue} legislation...")
        df = await tracker.track_issue(issue, year=2024)
        tracker.create_choropleth_map(df, issue)
        print(f"✅ {issue}: {len(df)} bills tracked")

asyncio.run(track_all_issues())
```

---

## 🔍 How It Works

### 1. Data Collection (Open States API)

The `LegislativeTracker` class searches Open States API for bills matching issue keywords:

```python
tracker = LegislativeTracker()

# Search for fluoridation bills in all states
bills = await tracker.search_bills("fluoridation", year=2024)

# Returns bill metadata:
# - Title, summary, bill number
# - State, session, sponsors
# - Actions, votes, committee assignments
```

### 2. Bill Categorization

Each bill is categorized by **type** and **status**:

#### Bill Types

Determined by keyword matching in title/summary:

| Type | Keywords | Example |
|------|----------|---------|
| **Ban** | "prohibit", "ban", "criminalize" | "Prohibit Water Fluoridation Act" |
| **Restriction** | "limit", "restrict", "regulate", "parental consent" | "Fluoride Disclosure Requirements" |
| **Protection** | "require", "mandate", "protect", "expand" | "Community Water Fluoridation Mandate" |

#### Bill Status

Determined by latest legislative action:

| Status | Action Keywords | Meaning |
|--------|----------------|---------|
| **Enacted** | "signed", "enacted", "passed", "approved" | Bill became law |
| **Introduced** | "introduced", "referred", "committee" | Bill is pending |
| **Failed** | "failed", "defeated", "vetoed", "withdrawn" | Bill did not pass |

**Categorization Logic:**

```python
def categorize_bill(bill, issue):
    text = f"{bill['title']} {bill['summary']}".lower()
    
    # Check for ban keywords
    if any(kw in text for kw in ["prohibit fluoride", "ban fluoridation"]):
        bill_type = "ban"
    # Check for restriction keywords
    elif any(kw in text for kw in ["restrict fluoride", "limit fluoridation"]):
        bill_type = "restriction"
    # Check for protection keywords
    elif any(kw in text for kw in ["require fluoride", "mandate fluoridation"]):
        bill_type = "protection"
    
    return bill_type
```

### 3. State-Level Aggregation

Bills are grouped by state to determine:
- **Dominant legislation type** (ban/restriction/protection)
- **Dominant status** (enacted/introduced/failed)
- **Bill counts** per category

```python
# Example state summary
{
  "state_code": "AL",
  "dominant_type": "ban",
  "dominant_status": "introduced",
  "total_bills": 3,
  "ban_count": 2,
  "restriction_count": 1,
  "protection_count": 0
}
```

### 4. Map Visualization

**Color Coding:**

| Color | Bill Type | Status | Example |
|-------|-----------|--------|---------|
| 🟤 Dark Brown | Ban | Enacted | Fluoridation ban passed into law |
| 🟠 Orange | Ban | Introduced | Fluoridation ban pending |
| 🟡 Light Yellow | Ban | Failed | Fluoridation ban defeated |
| 🟨 Goldenrod | Restriction | Enacted | Disclosure law passed |
| 💛 Gold | Restriction | Introduced | Restriction pending |
| 🟡 Pale Yellow | Restriction | Failed | Restriction defeated |
| 🔵 Dark Blue | Protection | Enacted | Fluoridation mandate passed |
| 🔷 Royal Blue | Protection | Introduced | Protection bill pending |
| ☁️ Sky Blue | Protection | Failed | Protection defeated |

**Visual Patterns:**
- Solid colors = bills passed into law
- Lighter shades = bills introduced but pending
- Palest shades = bills failed/defeated

---

## 📈 Example: Fluoridation Legislation Map

### Step 1: Search for Bills

```python
import asyncio
from scripts.legislative_tracker import LegislativeTracker

async def main():
    tracker = LegislativeTracker()
    
    # Track fluoridation bills in 2024
    df = await tracker.track_issue("fluoridation", year=2024)
    
    # View results
    print(df[['state_code', 'title', 'type', 'status']])

asyncio.run(main())
```

**Output:**
```
state_code  title                              type        status
AL          Prohibit Water Fluoridation        ban         introduced
CA          Community Fluoridation Mandate     protection  enacted
TX          Fluoride Disclosure Requirements   restriction introduced
```

### Step 2: Generate Map

```python
# Create interactive choropleth map
tracker.create_choropleth_map(df, "fluoridation")
```

**Output:** `data/visualizations/fluoridation_map.html`

### Step 3: View Map

Open `fluoridation_map.html` in a browser to see:
- Color-coded states by legislation type/status
- Hover over states for bill details
- Interactive zoom and pan
- Legend showing color meanings

---

## 🎨 Customizing Issue Keywords

Add your own issue keywords to track new topics:

```python
tracker = LegislativeTracker()

# Add custom issue keywords
tracker.issue_keywords["gun_control"] = {
    "ban": ["ban assault weapons", "prohibit firearms", "gun ban"],
    "restriction": ["background check", "waiting period", "permit requirement"],
    "protection": ["constitutional carry", "second amendment protection", "gun rights"]
}

# Track the new issue
df = await tracker.track_issue("gun_control", year=2024)
```

---

## 📊 Data Sources

### Plural Policy Bulk Downloads ⭐ **Recommended**

**What it provides:**
- **Complete legislative sessions** - All bills, votes, sponsors
- **CSV format** - Easy to process with pandas
- **JSON format** - Includes full bill text
- **PostgreSQL dumps** - Entire database (monthly snapshots)
- **No rate limits** - Bulk downloads encouraged
- **No API key** - Public domain data

**Coverage:**
- ✅ All 50 states + DC, PR
- ✅ Historical sessions (2010+)
- ✅ Current sessions (monthly updates)
- ✅ Complete bill lifecycle

**Bulk Download URLs:**
- **CSV per session:** https://data.openstates.org/session/csv/{state}/{session_id}.csv
- **JSON per session:** https://data.openstates.org/session/json/{state}/{session_id}.json.zip
- **PostgreSQL dump:** https://data.openstates.org/postgres/monthly/YYYY-MM-public.pgdump
- **Documentation:** https://open.pluralpolicy.com/data/

**Download Options:**

```bash
# Option 1: All states as CSV (fast, ~500MB total)
python scripts/bulk_legislative_download.py --year 2024 --format csv --merge

# Option 2: Specific states as JSON (includes full text)
python scripts/bulk_legislative_download.py --year 2024 --states CA,TX,NY --format json

# Option 3: PostgreSQL dump (complete database, ~5GB)
python scripts/bulk_legislative_download.py --postgres --month 2026-04
```

**Why use bulk downloads?**

| Feature | Bulk Download | API |
|---------|--------------|-----|
| **Speed** | ✅ Minutes for all states | ❌ Hours (50K API calls) |
| **Rate Limits** | ✅ None | ⚠️ 50K/month |
| **API Key** | ✅ Not required | ❌ Required |
| **Offline** | ✅ Process locally | ❌ Needs internet |
| **Complete Sessions** | ✅ All bills at once | ⚠️ Must paginate |
| **Real-time** | ⚠️ Monthly updates | ✅ Same-day updates |

**Recommendation:** Use bulk downloads for historical analysis and map generation. Use API for real-time bill tracking.

---

### Open States API (Real-time Updates)

**What it provides:**
- 100,000+ state bills from all 50 states
- Bill text, summaries, sponsors
- Legislative actions and votes
- Committee assignments
- Real-time updates

**Coverage:**
- ✅ All 50 states + DC, PR, territories
- ✅ Current and historical sessions
- ✅ Multiple bill types (HB, SB, HR, SR, etc.)
- ✅ Standardized OCD-ID format

**API Documentation:** https://docs.openstates.org/api-v3/

**Free Tier:**
- 50,000 requests/month
- No credit card required
- Commercial and non-commercial use

### Ballotpedia (Optional)

For ballot measures and referendums (not just legislation):

```python
from discovery.ballotpedia_integration import BallotpediaDiscovery

discovery = BallotpediaDiscovery()
measures = await discovery.get_ballot_measures("Alabama", year=2024)
```

**Note:** Ballotpedia API is paid. Web scraping fallback available.

---

## 🗂️ Output Files

### CSV Data Files

**Location:** `data/cache/legislation/{issue}_{year}.csv`

**Columns:**
- `bill_id` - State bill number (e.g., "HB 123")
- `state` - State name (e.g., "Alabama")
- `state_code` - Two-letter code (e.g., "AL")
- `title` - Bill title
- `type` - Categorization (ban/restriction/protection)
- `status` - Legislative status (introduced/enacted/failed)
- `url` - Open States bill page URL
- `session` - Legislative session
- `latest_action` - Most recent action
- `latest_action_date` - Date of action

**Example:**
```csv
bill_id,state,state_code,title,type,status,url
HB 123,Alabama,AL,Prohibit Water Fluoridation,ban,introduced,https://openstates.org/al/bills/2024/HB123/
SB 456,California,CA,Community Fluoridation Mandate,protection,enacted,https://openstates.org/ca/bills/2024/SB456/
```

### HTML Map Files

**Location:** `data/visualizations/{issue}_map.html`

**Features:**
- Interactive choropleth map
- Hover tooltips with bill details
- Zoom/pan controls
- Responsive design
- Embeddable in websites

### Legend Images

**Location:** `data/visualizations/{issue}_legend.png`

**Contains:**
- Color key for bill types
- Status indicators
- Pattern explanations

---

## 🔧 Advanced Usage

### Track Specific States Only

```python
# Track only southern states
southern_states = ["AL", "AR", "FL", "GA", "KY", "LA", "MS", "NC", "SC", "TN", "TX", "VA", "WV"]

df = await tracker.track_issue("fluoridation", year=2024, states=southern_states)
```

### Multi-Year Trends

```python
import pandas as pd

dfs = []
for year in range(2020, 2025):
    df = await tracker.track_issue("fluoridation", year=year)
    df['year'] = year
    dfs.append(df)

# Combine all years
all_years = pd.concat(dfs, ignore_index=True)

# Analyze trends
trend = all_years.groupby(['year', 'type']).size().reset_index(name='count')
print(trend)
```

**Output:**
```
year  type         count
2020  ban          12
2020  restriction   8
2020  protection    5
2021  ban          15
2021  restriction  10
...
```

### Export for Further Analysis

```python
# Export to Excel with multiple sheets
with pd.ExcelWriter('fluoridation_analysis.xlsx') as writer:
    df.to_excel(writer, sheet_name='All Bills', index=False)
    
    # Summary by state
    state_summary = tracker.generate_state_summary(df)
    state_summary.to_excel(writer, sheet_name='State Summary', index=False)
    
    # Enacted bills only
    enacted = df[df['status'] == 'enacted']
    enacted.to_excel(writer, sheet_name='Enacted Bills', index=False)
```

---

## 🎯 Use Cases

### 1. Advocacy Campaign Planning

**Goal:** Identify states with active legislation for targeted campaigns

```python
# Find states with pending ban legislation
df = await tracker.track_issue("fluoridation", year=2024)
pending_bans = df[(df['type'] == 'ban') & (df['status'] == 'introduced')]

print(f"States with pending fluoridation bans: {pending_bans['state_code'].unique()}")
# Output: ['AL', 'TX', 'FL', ...]
```

**Use for:**
- Email campaigns to state legislators
- Social media targeting by state
- Coalition building in key states

### 2. Policy Research

**Goal:** Track legislative trends over time

```python
# Compare ban vs protection bills over 5 years
for year in range(2020, 2025):
    df = await tracker.track_issue("fluoridation", year=year)
    
    bans = len(df[df['type'] == 'ban'])
    protections = len(df[df['type'] == 'protection'])
    
    print(f"{year}: {bans} bans, {protections} protections")
```

### 3. Media and Journalism

**Goal:** Create data-driven stories on legislative activity

```python
# Generate map for publication
df = await tracker.track_issue("fluoridation", year=2024)
tracker.create_choropleth_map(df, "fluoridation", output_file="public/fluoride_map.html")

# Embed in article with <iframe>
```

### 4. Academic Research

**Goal:** Analyze correlation between legislation and demographics

```python
# Merge with Census data
import geopandas as gpd

df = await tracker.track_issue("fluoridation", year=2024)
state_summary = tracker.generate_state_summary(df)

# Join with state-level Census data
census = pd.read_csv("census_state_demographics.csv")
merged = state_summary.merge(census, on='state_code')

# Analyze correlations
correlation = merged[['ban_count', 'median_income', 'college_educated_pct']].corr()
```

---

## 🚀 Next Steps

### Integrate with Knowledge Graph

Add legislation to the jurisdiction knowledge graph:

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687")

with driver.session() as session:
    for _, bill in df.iterrows():
        session.run("""
            MATCH (j:Jurisdiction {state_code: $state_code})
            CREATE (b:Bill {
                bill_id: $bill_id,
                title: $title,
                type: $type,
                status: $status,
                url: $url
            })
            CREATE (j)-[:HAS_LEGISLATION]->(b)
        """, bill.to_dict())
```

### Add to Dashboard

Embed map in React frontend:

```tsx
// frontend/src/pages/LegislationTracker.tsx
import React from 'react';

export function LegislationMap({ issue }: { issue: string }) {
  return (
    <iframe
      src={`/data/visualizations/${issue}_map.html`}
      width="100%"
      height="600px"
      frameBorder="0"
    />
  );
}
```

### Automate Daily Updates

Create cron job to update data:

```bash
# crontab -e
# Run daily at 6am
0 6 * * * cd /path/to/project && python scripts/legislative_tracker.py --issue fluoridation --year 2024 --visualize
```

---

## 📚 Related Documentation

- [Open States API Documentation](https://docs.openstates.org/)
- [Ballotpedia Integration](../data-sources/ballot-election-sources.md)
- [Data Model ERD](../data-sources/data-model-erd.md)
- [Jurisdiction Discovery](../data-sources/jurisdiction-discovery.md)

---

## ❓ Troubleshooting

### Error: "OPENSTATES_API_KEY not found"

**Solution:** Add API key to `.env`:
```bash
OPENSTATES_API_KEY=your-key-here
```

### Error: "Plotly not installed"

**Solution:** Install visualization libraries:
```bash
pip install plotly matplotlib
```

### Error: "No bills found for issue"

**Possible causes:**
1. **Issue keyword too specific** - Broaden search terms
2. **No legislation in that year** - Try different year
3. **API quota exceeded** - Wait for next month or upgrade

**Solution:** Customize keywords:
```python
tracker.issue_keywords["fluoridation"]["ban"].append("anti-fluoride")
```

### Map shows no data

**Check:**
1. CSV file was created: `data/cache/legislation/{issue}_{year}.csv`
2. CSV has rows with state_code values
3. Categorization logic matched bills correctly

---

## 💡 Tips & Best Practices

1. **Start broad, then refine** - Use general keywords first, then add specific terms
2. **Cache aggressively** - API calls are rate-limited, save results locally
3. **Update regularly** - Legislation changes daily during session
4. **Verify categorization** - Review sample bills to ensure accuracy
5. **Document keywords** - Keep track of which keywords work best
6. **Share visualizations** - Export maps as images for social media

---

## 🎨 Color Scheme Reference

### Default Colors (Customizable)

```python
color_map = {
    ('ban', 'enacted'): '#D2691E',       # Brown
    ('ban', 'introduced'): '#FFA500',    # Orange
    ('ban', 'failed'): '#FFE4B5',        # Moccasin
    ('restriction', 'enacted'): '#DAA520',  # Goldenrod
    ('restriction', 'introduced'): '#FFD700', # Gold
    ('restriction', 'failed'): '#FFFFE0',    # Light Yellow
    ('protection', 'enacted'): '#00008B',    # Dark Blue
    ('protection', 'introduced'): '#4169E1', # Royal Blue
    ('protection', 'failed'): '#87CEEB',     # Sky Blue
}
```

### Custom Color Scheme

```python
# Update colors for your brand
tracker.color_map = {
    ('ban', 'enacted'): '#FF0000',  # Red for enacted bans
    ('protection', 'enacted'): '#00FF00',  # Green for enacted protections
}
```
