---
sidebar_position: 5
---

# Legislative Tracking Maps

Create interactive choropleth maps showing state-level legislative activity across multiple social issues.

## 🎯 Quick Start

### Recommended: Bulk Download Method

**Faster, easier, no API key needed!**

```bash
# Download all 50 states for 2024 (takes ~5 minutes)
python scripts/bulk_legislative_download.py --year 2024 --format csv --merge

# Output: data/cache/legislation_bulk/all_states_2024.csv
# Contains: ALL bills from ALL 50 states in one file!
```

Then process and visualize:

```python
from scripts.legislative_tracker import LegislativeTracker
import pandas as pd

tracker = LegislativeTracker()

# Load bulk data
df = pd.read_csv('data/cache/legislation_bulk/all_states_2024.csv')

# Categorize and map
categorized = []
for _, bill in df.iterrows():
    cat = tracker.categorize_bill(bill.to_dict(), 'fluoridation')
    categorized.append(cat)

df_cat = pd.DataFrame(categorized)
tracker.create_choropleth_map(df_cat, "fluoridation")
```

**Why bulk downloads?**
- ✅ **No API key** - Public bulk data
- ✅ **No rate limits** - Download encouraged  
- ✅ **Faster** - All 50 states in minutes vs hours
- ✅ **Complete** - Entire legislative sessions
- ✅ **Offline** - Process without internet

---

### Alternative: API Method

For real-time tracking:

### 1. Get Open States API Key (Free)

```bash
# Sign up at https://openstates.org/accounts/signup/
# Add to .env:
OPENSTATES_API_KEY=your-key-here
```

### 2. Run Demo

```bash
# Simple demo - track fluoridation legislation
python scripts/legislative_tracker.py --issue fluoridation --year 2024 --visualize

# Or run comprehensive demo
python examples/legislative_map_demo.py
```

### 3. View Results

Open in browser:
- `data/visualizations/fluoridation_map.html` - Interactive map
- `data/cache/legislation/fluoridation_2024.csv` - Raw data

## 📊 Supported Issues

Pre-configured keywords for:
- **fluoridation** - Water fluoridation bans/mandates
- **abortion** - Abortion restrictions/protections
- **marijuana** - Cannabis legalization
- **voting** - Voting rights legislation
- **lgbtq** - LGBTQ+ protections
- **education** - Education policy (CRT, books, etc.)

## 🗺️ Map Features

**Visualization shows:**
- **Colors:** Bill type (ban/restriction/protection)
- **Shades:** Status (enacted/introduced/failed)
- **Hover:** State details, bill counts
- **Legend:** Explanation of colors/patterns

**Color Coding:**
- 🟤 **Brown** - Ban enacted
- 🟠 **Orange** - Ban introduced
- 🔵 **Blue** - Protection enacted
- 💛 **Yellow** - Restriction

## 📝 Example Usage

```python
from scripts.legislative_tracker import LegislativeTracker
import asyncio

async def track_multiple_issues():
    tracker = LegislativeTracker()
    
    # Track abortion legislation
    df = await tracker.track_issue("abortion", year=2024)
    print(f"Found {len(df)} bills")
    
    # Generate map
    tracker.create_choropleth_map(df, "abortion")
    
asyncio.run(track_multiple_issues())
```

## 🎨 Custom Issues

Add your own keywords:

```python
tracker = LegislativeTracker()

# Add gun control tracking
tracker.issue_keywords["gun_control"] = {
    "ban": ["ban assault weapons", "prohibit firearms"],
    "restriction": ["background check", "waiting period"],
    "protection": ["constitutional carry", "gun rights"]
}

# Track it
df = await tracker.track_issue("gun_control", year=2024)
```

## 📦 Output Files

### CSV Data
**Location:** `data/cache/legislation/{issue}_{year}.csv`

**Columns:**
- `bill_id` - State bill number
- `state_code` - Two-letter code
- `title` - Bill title
- `type` - ban/restriction/protection
- `status` - introduced/enacted/failed
- `url` - Open States URL

### HTML Maps
**Location:** `data/visualizations/{issue}_map.html`

**Features:**
- Interactive choropleth
- Hover tooltips
- Zoom/pan
- Embeddable

## 🔧 Advanced Features

### Filter by States

```python
# Southern states only
southern = ["AL", "AR", "FL", "GA", "KY", "LA", "MS", "NC", "SC", "TN", "TX", "VA", "WV"]
df = await tracker.track_issue("fluoridation", year=2024, states=southern)
```

### Multi-Year Trends

```python
import pandas as pd

dfs = []
for year in range(2020, 2025):
    df = await tracker.track_issue("fluoridation", year=year)
    df['year'] = year
    dfs.append(df)

all_years = pd.concat(dfs)
```

### Export to Excel

```python
# Export with multiple sheets
with pd.ExcelWriter('analysis.xlsx') as writer:
    df.to_excel(writer, sheet_name='All Bills', index=False)
    
    state_summary = tracker.generate_state_summary(df)
    state_summary.to_excel(writer, sheet_name='Summary', index=False)
```

## 📚 Full Documentation

See [Legislative Tracking Maps Guide](legislative-tracking-maps.md) for:
- Detailed API documentation
- Categorization logic
- Color scheme reference
- Use cases and examples
- Troubleshooting

## 🔗 Data Sources

- **Open States API** - 100,000+ state bills (free)
- **Ballotpedia** - Ballot measures (paid API)

## 💡 Tips

1. **Cache results** - API calls are rate-limited
2. **Review categorization** - Check sample bills for accuracy
3. **Customize keywords** - Add issue-specific terms
4. **Update regularly** - Legislation changes daily
5. **Share maps** - Export as images for social media

## ❓ Troubleshooting

**"OPENSTATES_API_KEY not found"**
→ Add key to `.env` file

**"No bills found"**
→ Try broader keywords or different year

**"Plotly not installed"**
→ Already in requirements.txt, run `pip install -r requirements.txt`

## 🚀 Next Steps

- Add legislation to knowledge graph
- Embed maps in React dashboard
- Automate daily updates with cron
- Track committee hearings and votes
- Add email alerts for bill status changes
