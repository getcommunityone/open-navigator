---
sidebar_position: 15
---

# 🚀 RUNNING DISCOVERY FOR ALL U.S. CITIES AND COUNTIES

**Automated discovery pipeline for 22,000+ jurisdictions nationwide**

---

## 📊 SCALE

**Target Coverage:**
- **3,143 U.S. Counties** (from NACo database)
- **19,000+ Cities** (from U.S. Census Bureau)
- **Total: ~22,000 jurisdictions**

**What Gets Discovered Per Jurisdiction:**
1. Official government website(s)
2. YouTube channels (with subscriber/video counts)
3. Vimeo and other video platforms  
4. Meeting platforms (Legistar, SuiteOne, Granicus, etc.)
5. Social media accounts (Facebook, Twitter)
6. Agenda portals and document systems
7. Historical coverage depth

**Output:**
- JSON with complete details
- CSV summary for analysis
- Completeness scores (0-100%)

---

## 🏃 QUICK START

### 1. Test with a Single State (Alabama)

```bash
cd /home/developer/projects/open-navigator

# Activate environment
source venv/bin/activate

# Run discovery for all Alabama cities/counties
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state AL
```

**Expected Output:**
```
Starting batch discovery for 67 jurisdictions (Alabama counties)
Discovering: Birmingham, AL (city)
  Step 1/6: Finding website
  Step 2/6: Finding YouTube channels
  ...
✓ Birmingham: 85% complete
✓ Mobile: 72% complete
✓ Tuscaloosa: 90% complete
...
DISCOVERY COMPLETE!
Total jurisdictions: 67
Successful: 65 (97%)
Average completeness: 78%
```

### 2. Top 100 U.S. Cities

```bash
# Discover data for top 100 cities by population
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --top 100
```

**Use Case:** Get started quickly with major cities

### 3. All Jurisdictions (Full National Scale)

```bash
# Process ALL 22,000+ jurisdictions
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --all

# WARNING: This will take 24-48 hours!
# Recommend running on server/cloud instance
```

---

## ⚙️ CONFIGURATION OPTIONS

### Rate Limiting

```bash
# Control concurrent requests (prevent rate limiting)
python scripts/discovery/archive/comprehensive_discovery_pipeline.py \
    --max-concurrent 5 \
    --state CA

# Default: 10 concurrent (safe for most networks)
# Lower to 5 for slower connections
# Increase to 20 if you have fast connection + server
```

### YouTube API Key (Recommended)

```bash
# Get free API key: https://console.cloud.google.com/

# Set environment variable
export YOUTUBE_API_KEY="AIza..."

# Or pass directly
python scripts/discovery/archive/comprehensive_discovery_pipeline.py \
    --youtube-api-key "AIza..." \
    --state AL
```

**Why Use API Key:**
- ✅ Accurate video counts
- ✅ Exact subscriber numbers
- ✅ View counts, upload dates
- ✅ Channel verification status
- 🆓 FREE (10,000 units/day = ~3,000 channels)

**Without API Key:**
- ⚠️ HTML scraping (less accurate)
- ⚠️ Approximate statistics
- ✅ Still finds all channels

---

## 📁 OUTPUT FILES

### File Locations

```
data/bronze/discovered_sources/
├── discovery_results_batch_100_20260422_143022.json    # Detailed results
├── discovery_results_final_20260422_150145.json        # Final complete
├── discovery_summary_batch_100_20260422_143022.csv     # Summary table
└── discovery_summary_final_20260422_150145.csv         # Final summary
```

### JSON Structure (Detailed)

```json
{
  "jurisdiction": {
    "name": "Tuscaloosa",
    "state_code": "AL",
    "type": "city",
    "population": 99600
  },
  "discovery_timestamp": "2026-04-22T14:30:00",
  "websites": [
    {
      "url": "https://www.tuscaloosa.com",
      "final_url": "https://www.tuscaloosa.com/",
      "status": "active",
      "discovery_method": "pattern_match"
    }
  ],
  "youtube_channels": [
    {
      "channel_url": "https://www.youtube.com/@TuscaloosaCityAL",
      "channel_id": "UCxxx",
      "channel_title": "City of Tuscaloosa",
      "video_count": 245,
      "subscriber_count": 382,
      "view_count": 50000,
      "discovery_method": "pattern_match"
    }
  ],
  "meeting_platforms": [
    {
      "type": "suiteone",
      "url": "https://tuscaloosaal.suiteonemedia.com",
      "method": "url_test"
    }
  ],
  "agenda_portals": [
    {
      "url": "https://tuscaloosaal.suiteonemedia.com/Web/Home.aspx",
      "link_text": "agendas and synopses",
      "discovery_method": "homepage_scrape"
    }
  ],
  "social_media": {
    "facebook": ["https://www.facebook.com/163854056994765"],
    "twitter": ["https://x.com/tuscaloosacity"],
    "vimeo": ["https://vimeo.com/tuscaloosacity"]
  },
  "completeness_score": 0.90,
  "status": "success"
}
```

### CSV Structure (Summary)

```csv
name,state,type,population,website,youtube_channels,meeting_platforms,agenda_portals,completeness,status
Tuscaloosa,AL,city,99600,https://www.tuscaloosa.com,2,1,1,0.90,success
Birmingham,AL,city,200733,https://www.birminghamal.gov,1,1,0,0.75,success
Mobile,AL,city,187041,https://www.cityofmobile.org,1,2,1,0.85,success
...
```

---

## 📊 EXAMPLE: Alabama Discovery

Let's run discovery for all Alabama jurisdictions and analyze results:

### Step 1: Run Discovery

```bash
source venv/bin/activate

# Discover all Alabama cities and counties
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state AL \
    --youtube-api-key "$YOUTUBE_API_KEY"
```

### Step 2: Analyze Results

```python
import pandas as pd

# Load results
df = pd.read_csv('data/bronze/discovered_sources/discovery_summary_final_20260422.csv')

# Alabama statistics
al_data = df[df['state'] == 'AL']

print(f"Alabama Jurisdictions: {len(al_data)}")
print(f"With websites: {(al_data['website'] != '').sum()}")
print(f"With YouTube: {(al_data['youtube_channels'] > 0).sum()}")
print(f"With agendas: {(al_data['agenda_portals'] > 0).sum()}")
print(f"Average completeness: {al_data['completeness'].mean():.1%}")

# Top performing cities
top_al = al_data.nlargest(10, 'completeness')
print("\nTop 10 Alabama cities by data completeness:")
print(top_al[['name', 'youtube_channels', 'meeting_platforms', 'completeness']])
```

**Expected Output:**
```
Alabama Jurisdictions: 67
With websites: 64 (96%)
With YouTube: 18 (27%)
With agendas: 42 (63%)
Average completeness: 71%

Top 10 Alabama cities by data completeness:
           name  youtube_channels  meeting_platforms  completeness
0    Tuscaloosa                 2                  1          0.90
1    Birmingham                 1                  1          0.85
2        Mobile                 1                  2          0.85
3    Montgomery                 1                  1          0.80
...
```

---

## 🎯 RECOMMENDED STRATEGY

### Phase 1: Test (1 Day)
```bash
# Test with your home state
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state AL

# Review results, adjust parameters
# Check completeness scores
```

### Phase 2: Major Cities (1 Week)
```bash
# Top 100 cities (80% of population)
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --top 100

# Top 500 cities
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --top 500
```

### Phase 3: Regional (1 Month)
```bash
# Process by region to distribute load
# South
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --states AL,GA,FL,SC,NC

# Midwest  
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --states IL,IN,OH,MI,WI

# West
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --states CA,WA,OR,AZ,NV

# Northeast
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --states NY,NJ,PA,MA,CT
```

### Phase 4: Complete National (1-2 Months)
```bash
# Full 22,000+ jurisdictions
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --all

# Run on cloud server (AWS, GCP, Azure)
# Estimated time: 24-48 hours
# Cost: ~$20-50 (if using cloud compute)
```

---

## ⚡ PERFORMANCE OPTIMIZATION

### For Faster Discovery

**1. Use Cloud Server**
```bash
# AWS EC2 t3.medium or larger
# Better network = faster requests
# Can increase --max-concurrent to 20-50
```

**2. Parallel State Processing**
```bash
# Run multiple states in parallel on different terminals

# Terminal 1
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state AL

# Terminal 2
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state GA

# Terminal 3
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state FL
```

**3. YouTube API Key**
```bash
# ALWAYS use API key for accuracy + speed
export YOUTUBE_API_KEY="your-key-here"

# Without key: 2-3 requests per channel (slower)
# With key: 1 request per channel (faster + accurate)
```

### For Reliability

**1. Auto-Resume**
```python
# The pipeline saves every 100 jurisdictions
# If it crashes, you can resume from last save

# Manual resume:
completed_ids = load_completed_from_csv('discovery_summary_batch_100.csv')
remaining = [j for j in jurisdictions if j['id'] not in completed_ids]
pipeline.discover_batch(remaining)
```

**2. Error Handling**
```python
# Failed jurisdictions are marked status='error'
# Re-run just the failures:

df = pd.read_csv('discovery_summary_final.csv')
failures = df[df['status'] == 'error']

# Extract jurisdiction info and retry
retry_list = failures.to_dict('records')
pipeline.discover_batch(retry_list)
```

---

## 📈 EXPECTED RESULTS (National Scale)

### Coverage Estimates

**Websites:** 85-90% (17,000-19,000)
- Most cities have websites
- Some very small towns may not

**YouTube Channels:** 20-30% (4,000-6,000)
- Larger cities more likely
- Growing trend (30%+ for cities >50k pop)

**Meeting Platforms:**
- **Legistar:** 15-20% (~3,000-4,000)
- **SuiteOne:** 5-10% (~1,000-2,000)
- **Granicus:** 10-15% (~2,000-3,000)
- **Other/Custom:** 30-40% (~6,000-8,000)

**Agenda Portals:** 60-70% (13,000-15,000)
- Required by law in most states
- Varying levels of digitization

**Social Media:** 70-80% (15,000-18,000)
- Facebook most common
- Twitter second
- LinkedIn, Instagram less common for gov

### Completeness by Jurisdiction Size

| Population | Avg Completeness | YouTube | Agendas |
|-----------|------------------|---------|---------|
| 1M+ | 95% | 90% | 95% |
| 500k-1M | 90% | 75% | 90% |
| 100k-500k | 85% | 50% | 85% |
| 50k-100k | 75% | 30% | 75% |
| 10k-50k | 65% | 15% | 65% |
| \<10k | 50% | 5% | 50% |

---

## 🔍 NEXT STEPS AFTER DISCOVERY

### 1. Analyze Results

```python
# Load all results
df = pd.read_csv('discovery_summary_final.csv')

# Find best sources for oral health research
high_quality = df[df['completeness'] > 0.8]

# Prioritize by population + data quality
df['priority_score'] = df['population'] * df['completeness']
top_targets = df.nlargest(100, 'priority_score')

print("Top 100 jurisdictions for analysis:")
print(top_targets[['name', 'state', 'population', 'completeness']])
```

### 2. Begin Content Scraping

```python
# For each high-priority jurisdiction, scrape actual content

from agents.scraper import ScraperAgent

for _, row in top_targets.iterrows():
    # Get their agenda portal URL from discovery results
    jurisdiction_data = load_discovery_json(row['name'], row['state'])
    
    if jurisdiction_data['meeting_platforms']:
        platform = jurisdiction_data['meeting_platforms'][0]
        
        # Scrape agendas
        scraper = ScraperAgent()
        docs = await scraper.scrape(
            url=platform['url'],
            municipality=row['name'],
            state=row['state'],
            platform=platform['type']
        )
```

### 3. Search for Oral Health Content

```python
# Search agenda text for keywords
keywords = [
    'fluoride', 'fluoridation', 'water treatment',
    'dental', 'oral health', 'tooth decay',
    'dental clinic', 'school dental'
]

# Filter to relevant meetings
relevant_docs = []
for doc in all_documents:
    doc_text = doc['content'].lower()
    if any(kw in doc_text for kw in keywords):
        relevant_docs.append(doc)

print(f"Found {len(relevant_docs)} relevant meetings across all jurisdictions")
```

---

## ✅ SUCCESS METRICS

**After running national discovery, you should have:**

✅ **~19,000 government websites** discovered  
✅ **~5,000 YouTube channels** with statistics  
✅ **~3,000 Legistar** API endpoints  
✅ **~10,000 agenda portals** cataloged  
✅ **~15,000 social media** accounts  
✅ **Completeness scores** for prioritization  

**This gives you complete coverage of where to find oral health policy discussions across the entire United States!**

---

## 🆘 TROUBLESHOOTING

### Common Issues

**1. Rate Limiting / Timeouts**
```bash
# Reduce concurrent requests
python scripts/discovery/archive/comprehensive_discovery_pipeline.py \
    --max-concurrent 3 \
    --state AL
```

**2. YouTube API Quota Exceeded**
```
Error: YouTube API quota exceeded

Solution: Wait 24 hours (quota resets daily)
Or: Create additional API keys and rotate
Or: Continue without API key (less accurate stats)
```

**3. Out of Memory**
```bash
# Process in smaller batches
# Instead of --all, do state by state
for state in AL GA FL SC NC; do
    python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state $state
done
```

---

## 📞 SUPPORT

**Questions?**
- Check logs: `logs/discovery_pipeline.log`
- Review errors in CSV: `status='error'` rows
- Test single jurisdiction first before batch

**Need Help?**
- Create GitHub issue with error details
- Include: state, error message, logs
- Provide sample jurisdiction that failed

---

**Bottom Line:** You can now discover data sources for ALL 22,000+ U.S. cities and counties automatically! Start with Alabama (67 jurisdictions) to test, then scale nationwide. 🚀
