---
title: Bulk Downloads vs API
---

# Bulk Downloads vs API: Which to Use?

## TL;DR

**Use Bulk Downloads** for:
- ✅ Historical analysis (analyzing past sessions)
- ✅ Map generation (need all states at once)
- ✅ Research projects (large datasets)
- ✅ Offline processing
- ✅ Multi-issue tracking across all states

**Use API** for:
- ✅ Real-time bill status (same-day updates)
- ✅ Search by specific keywords
- ✅ Individual bill lookups
- ✅ Automated alerts for bill changes

---

## Comparison Table

| Feature | Bulk Download | API |
|---------|--------------|-----|
| **Speed (50 states)** | ⚡ 5-10 minutes | 🐌 2-4 hours |
| **API Key Required** | ❌ No | ✅ Yes |
| **Rate Limits** | ❌ None | ⚠️ 50K/month |
| **Internet Required** | Download once | Always |
| **Data Freshness** | Monthly updates | Real-time |
| **Bill Text** | ✅ Full text (JSON) | ✅ Via API |
| **Complete Sessions** | ✅ All bills | Paginated |
| **Cost** | 💰 Free | 💰 Free (50K limit) |
| **Redistribution** | ✅ Allowed | ⚠️ Varies by state |

---

## Real-World Example

### Task: Create fluoridation legislation map for all 50 states (2024)

#### Method 1: Bulk Download

```bash
# Download all 50 states
python scripts/bulk_legislative_download.py --year 2024 --format csv --merge

# Time: ~5 minutes
# API calls: 0
# Result: 1 CSV file with ALL bills
```

**Result:** One 500MB file with ~100,000 bills from all states

#### Method 2: API

```bash
# Search each state individually
python scripts/legislative_tracker.py --issue fluoridation --year 2024

# Time: ~2-4 hours
# API calls: ~10,000 (search + pagination)
# Result: Filtered bills matching "fluoridation"
```

**Result:** Filtered dataset with ~500 matching bills

---

## When API is Better

### Use Case 1: Real-Time Bill Tracking

**Need:** Alert when a specific bill status changes

```python
# API can check latest status
async def check_bill_status(bill_id):
    response = await client.get(f"{base_url}/bills/{bill_id}")
    return response.json()['latest_action']

# Bulk: Would need to wait for next monthly dump
```

### Use Case 2: Keyword Search

**Need:** Find all bills mentioning "oral health"

```python
# API can search full text
params = {"q": "oral health", "jurisdiction": "AL"}
response = await client.get(f"{base_url}/bills", params=params)

# Bulk: Would need to download all bills, then search locally
```

### Use Case 3: Single Bill Lookup

**Need:** Get details for one specific bill

```python
# API is instant
response = await client.get(f"{base_url}/bills/AL/2024/HB123")

# Bulk: Download entire session just for one bill
```

---

## When Bulk Downloads are Better

### Use Case 1: All-State Analysis

**Need:** Map legislation across all 50 states

**API Approach:**
```python
# 50 states × 100 requests per state = 5,000 API calls
# Time: ~2 hours (with rate limiting)
# Risk: Hit API quota limit
```

**Bulk Approach:**
```python
# Download all 50 state CSV files
# Time: ~5 minutes
# API calls: 0
# No quota concerns
```

**Winner:** Bulk (50x faster)

### Use Case 2: Historical Trends

**Need:** Analyze fluoridation bills from 2010-2024

**API Approach:**
```python
# 50 states × 15 years × 100 requests = 75,000 API calls
# Time: Would exceed free tier quota
# Cost: Need paid plan
```

**Bulk Approach:**
```python
# Download 50 states × 15 years = 750 CSV files
# Time: ~30 minutes
# Cost: Free, no limits
```

**Winner:** Bulk (only viable option)

### Use Case 3: Offline Processing

**Need:** Process data without internet

**API Approach:**
```python
# Must cache all API responses locally
# Complex caching logic needed
# Cache invalidation issues
```

**Bulk Approach:**
```python
# Download once, process forever
# No internet needed after download
# Simple file-based workflow
```

**Winner:** Bulk (simpler)

---

## Hybrid Approach (Best of Both Worlds)

### Strategy: Bulk for foundation, API for updates

```python
# 1. Download complete 2024 session (bulk)
!python scripts/bulk_legislative_download.py --year 2024 --merge

# 2. Load bulk data
df = pd.read_csv('data/cache/legislation_bulk/all_states_2024.csv')
print(f"Loaded {len(df)} bills from bulk download")

# 3. Use API for recent updates (last 7 days)
from datetime import datetime, timedelta
recent_cutoff = datetime.now() - timedelta(days=7)

# API search for bills updated in last week
async def get_recent_updates():
    params = {
        "updated_since": recent_cutoff.isoformat(),
        "jurisdiction": "all"
    }
    return await api_client.get("/bills", params=params)

recent = await get_recent_updates()

# 4. Merge bulk + recent updates
combined = pd.concat([df, recent])
```

**Benefits:**
- Complete historical data (bulk)
- Real-time updates (API)
- Minimal API calls (only recent changes)

---

## Recommendations by Project Type

### Academic Research
→ **Use Bulk Downloads**
- Need complete datasets
- Historical analysis
- No real-time requirements
- May publish/redistribute

### News/Journalism
→ **Use API**
- Need latest bill status
- Breaking news coverage
- Specific bill tracking
- Real-time alerts

### Advocacy Campaigns
→ **Use Hybrid**
- Bulk for initial analysis
- API for monitoring active bills
- Alerts when bills advance
- Historical context + real-time

### Government Dashboards
→ **Use Hybrid**
- Bulk for historical trends
- API for current session
- Daily/weekly refresh
- Public redistribution

---

## Cost Analysis

### Free Tier Limits

**API:**
- 50,000 requests/month free
- ~100 bills per request (pagination)
- = ~5M bill records/month max

**Bulk:**
- Unlimited downloads
- ~100K bills per download
- = Unlimited bill records/month

### Time to Download All States (2024)

**API (50 states):**
```
50 states × 100 API calls = 5,000 requests
5,000 requests × 0.5s rate limit = 2,500 seconds = ~42 minutes
(Not including processing time)
```

**Bulk (50 states):**
```
50 CSV downloads × 5s each = 250 seconds = ~4 minutes
(Includes all data, no processing needed)
```

**Time Saved:** ~38 minutes (10x faster)

### Data Completeness

**API:**
- Must paginate through all results
- Risk of missing data if pagination fails
- Requires careful error handling

**Bulk:**
- Complete session in one file
- Guaranteed completeness
- No pagination errors

---

## PostgreSQL Dump Option

**For power users:**

```bash
# Download complete Open States database
python scripts/bulk_legislative_download.py --postgres --month 2026-04

# Restore to local PostgreSQL
pg_restore -d openstates 2026-04-public.pgdump

# Now use SQL for analysis!
psql openstates -c "
  SELECT state, COUNT(*) as bill_count
  FROM bills
  WHERE session_year = 2024
  GROUP BY state
  ORDER BY bill_count DESC;
"
```

**Benefits:**
- Complete database with relationships
- SQL queries for complex analysis
- No need for Python/pandas
- Can use PostgreSQL extensions
- Best for large-scale research

**Drawbacks:**
- Large file size (~5GB compressed)
- Requires PostgreSQL installation
- More complex setup

---

## Final Recommendation

**Default choice: Bulk Downloads**

Reasons:
1. Faster (10x speed improvement)
2. No API key setup
3. No rate limits
4. Work offline
5. Complete sessions guaranteed

**Switch to API when:**
- Need real-time status
- Tracking specific bills
- Keyword search required
- Small subset of data

**Use Both when:**
- Initial bulk download
- Periodic API updates
- Best of both worlds
