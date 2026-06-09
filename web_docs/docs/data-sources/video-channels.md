---
displayed_sidebar: developersSidebar
---

# Video Channel Discovery: Current State & Enhancement Plan

## Executive Summary

**Question:** Does this repo look at local government websites and attempt to discover their YouTube, Facebook, or other video channels?

**Answer:** 
- ❌ **Currently NO** - The repo does NOT scrape government websites for social media links
- ✅ **Partially YES** - It extracts video URLs from pre-existing datasets (MeetingBank, Open States)
- ✅ **NEW** - We've created `social_media_discovery.py` to implement your suggestion

---

## Current State: What Exists

### ✅ Video Discovery from Datasets (Offline Sources)

**1. MeetingBank (HuggingFace)**
- **File:** `discovery/meetingbank_ingestion.py`
- **Status:** ✅ **Working** - Video URLs ARE being extracted
- **Coverage:** 1,366 meetings from 6 cities
- **Video Sources:**
  - YouTube URLs (extracted from `urls['youtube_id']`)
  - Vimeo URLs (extracted from `urls['vimeo_id']`)
  - Archive.org collections (alameda, boston, denver, king-county, long-beach, seattle)

**2. Open States (API)**
- **File:** [`scrapers/openstates/openstates_sources.py`](https://github.com/getcommunityone/open-navigator/blob/main/packages/scrapers/src/scrapers/openstates/openstates_sources.py)
- **Status:** ✅ Working
- **Coverage:** 50+ state legislatures
- **Extracts:** YouTube channels, Vimeo accounts, Granicus portals from jurisdiction metadata

**3. City Scrapers (GitHub)**
- **File:** `discovery/city_scrapers_urls.py`
- **Status:** ⚠️ Partial - extracts start_urls but not video links yet
- **Coverage:** 100-500 agencies from Chicago, Pittsburgh, Detroit, Cleveland, LA
- **Note:** Granicus video pages with embedded YouTube, but extraction not fully implemented

### ❌ What's Missing: Website Scraping for Social Media

**Current Gap:**
The repo discovers government homepage URLs but does NOT:
1. ❌ Scrape those websites for social media links
2. ❌ Extract YouTube/Facebook channels from footers
3. ❌ Check "Contact Us" or "About" pages
4. ❌ Use USA.gov or federal aggregators

**Existing Homepage Discovery:**
- **File:** [`scripts/discovery/url_discovery_agent.py`](https://github.com/getcommunityone/open-navigator/blob/main/scripts/discovery/url_discovery_agent.py)
- **What it does:**
  - ✅ Finds government homepage URLs using GSA .gov registry
  - ✅ Tests URL patterns (cityname.gov, etc.)
  - ✅ Crawls to find minutes/agenda pages
  - ❌ **But does NOT look for social media links**

---

## Your Suggestion: Federal Aggregators & Website Scraping

### Excellent Ideas!

#### 1. USA.gov Local Directory
```
✅ Most accurate way to verify channels are legitimate
✅ Provides official website for every city/county
✅ Most governments link social media in footer/contact sections
```

**Implementation:** See section below on how to integrate.

#### 2. USA.gov/archive (Federal Videos)
```
⚠️ Good for federal agencies
⚠️ Limited local government coverage
✅ Could supplement state-level sources
```

**Use Case:** State agencies and federal programs that touch local policy.

---

## NEW Implementation: Social Media Discovery

We've created a new module to implement your suggestion!

### File: `discovery/social_media_discovery.py`

**What it does:**
1. ✅ Takes government homepage URLs (from existing discovery)
2. ✅ Scrapes footer sections for social media links
3. ✅ Checks common contact/about pages
4. ✅ Extracts YouTube, Facebook, Vimeo, Archive.org, Granicus
5. ✅ Validates and cleans URLs
6. ✅ Batch processing for hundreds of jurisdictions

**Example Usage:**
```python
from discovery.social_media_discovery import SocialMediaDiscovery

jurisdictions = [
    {
        'jurisdiction_id': 'seattle-wa',
        'homepage_url': 'https://www.seattle.gov',
        'jurisdiction_name': 'Seattle',
        'state': 'WA'
    }
]

async with SocialMediaDiscovery() as discovery:
    results = await discovery.discover_batch(jurisdictions)

# Results:
# [
#   {
#     'jurisdiction_name': 'Seattle',
#     'social_media': {
#       'youtube': ['https://www.youtube.com/@cityofseattle'],
#       'facebook': ['https://www.facebook.com/CityofSeattle'],
#       'twitter': ['https://twitter.com/CityofSeattle']
#     },
#     'platform_count': 3,
#     'total_urls': 3
#   }
# ]
```

**Detection Strategy:**
- Focus on footer sections (most reliable)
- Common CSS selectors: `footer`, `[class*="footer"]`, `[class*="social"]`
- Pattern matching for platform URLs
- Validates against known domain patterns

---

## Integration with Existing Pipeline

### How Social Media Discovery Fits In

```
1. URL Discovery Agent (EXISTING)
   └─> Finds government homepage URLs
        └─> Uses GSA .gov registry
        └─> Pattern matching (cityname.gov)
        └─> Validates URLs

2. Social Media Discovery (NEW) ⬅️ Add this step
   └─> Scrapes homepages for social links
        └─> Checks footer sections
        └─> Checks contact/about pages
        └─> Extracts YouTube, Facebook, etc.

3. Meeting Scraper (EXISTING)
   └─> Uses discovered URLs to scrape meetings
```

### Integration Code Example

```python
from discovery.url_discovery_agent import URLDiscoveryAgent
from discovery.social_media_discovery import SocialMediaDiscovery
from discovery.gsa_domains import load_gsa_domains

# Step 1: Discover government websites
gsa_domains = load_gsa_domains()
url_agent = URLDiscoveryAgent(gsa_domains)

jurisdictions = [...]  # From Census data
discovered_urls = await url_agent.discover_batch(jurisdictions)

# Step 2: NEW - Discover social media from those websites
social_discovery = SocialMediaDiscovery()
social_results = await social_discovery.discover_batch(discovered_urls)

# Step 3: Save to Bronze layer
save_to_bronze_layer(social_results, "social_media_channels")
```

---

## USA.gov Integration Guide

### Approach 1: Use USA.gov Local Directory as Homepage Source

**What USA.gov Provides:**
- Official .gov website for every city/county
- Most authoritative source for homepage URLs
- Can replace/supplement GSA domain matching

**Implementation:**
```python
# discovery/usa_gov_directory.py (NEW FILE TO CREATE)

import httpx
from bs4 import BeautifulSoup

async def get_usa_gov_local_directory():
    """
    Scrape USA.gov local directory for official city/county websites.
    
    USA.gov maintains a directory at:
    https://www.usa.gov/local-governments
    
    Each state page lists cities/counties with official websites.
    """
    base_url = "https://www.usa.gov/local-governments"
    
    # 1. Get list of states
    # 2. For each state, get list of cities/counties
    # 3. Extract official website URLs
    # 4. Return structured data
    
    pass  # Implementation details


# Then use in url_discovery_agent.py:
def _match_usa_gov_directory(jurisdiction_name, state):
    """
    Match jurisdiction to USA.gov directory entry.
    
    Higher confidence than pattern matching because it's
    verified by federal government.
    """
    usa_gov_url = lookup_usa_gov_directory(jurisdiction_name, state)
    if usa_gov_url:
        return (usa_gov_url, 0.98)  # Very high confidence
    return None
```

### Approach 2: USA.gov/archive for Federal Video Content

**Use Case:** State health departments, federal programs

```python
# discovery/federal_video_sources.py (NEW FILE TO CREATE)

FEDERAL_VIDEO_CHANNELS = {
    "cdc": {
        "youtube": "https://www.youtube.com/@CDCgov",
        "topics": ["public_health", "oral_health"]
    },
    "hrsa": {
        "youtube": "https://www.youtube.com/@HRSAgov",
        "topics": ["health_centers", "dental_programs"]
    },
    "state_health_depts": {
        # Each state's health department
        "CA": "https://www.youtube.com/@CAPublicHealth",
        "TX": "https://www.youtube.com/@TXHealthHumanServices",
        # ... all 50 states
    }
}

def get_federal_video_sources():
    """
    Get federal agency video channels relevant to oral health policy.
    
    Sources:
    - usa.gov/archive featured channels
    - State health departments
    - CDC, HRSA, CMS channels
    """
    pass
```

### Approach 3: ELGL Top YouTube Channels (NEW - HIGHLY RECOMMENDED!)

**What:** ELGL (Engaging Local Government Leaders) publishes curated "Top Local Government YouTube Channels" lists

**Why This is Excellent:**
```
✅ Curated by experts (not automated scraping)
✅ Highlights MOST ACTIVE channels
✅ Quality > Quantity approach
✅ Updated annually
✅ Covers innovative local governments nationwide
```

**Sources:**
- ELGL Blog: https://elgl.org/
- Annual "Top Local Gov YouTube Channels" articles
- Digital innovation showcases

**Expected Coverage:** 50-100 top-tier channels (most active, highest quality)

**Implementation:** See `discovery/curated_sources.py`

### Approach 4: NACo County Database (NEW - COMPREHENSIVE!)

**What:** National Association of Counties maintains database of all 3,143 U.S. counties

**Why This is Excellent:**
```
✅ Complete county coverage (all 3,143 counties)
✅ Official website URLs verified by NACo
✅ Digital innovation showcase
✅ Authoritative source for county data
✅ Partnership opportunities
```

**Sources:**
- NACo County Explorer: https://ce.naco.org/
- Digital Counties Survey
- NACo Communications Awards

**Expected Coverage:** 3,143 counties with official websites

**Implementation:** See `discovery/curated_sources.py`

---

## Complete Implementation Plan

### Phase 1: Enhance Existing Dataset Extraction (✅ DONE)

- [x] MeetingBank video URLs (already working)
- [x] Open States channels (already working)
- [ ] City Scrapers Granicus video extraction (TODO)

### Phase 2: Website Social Media Discovery (✅ NEW MODULE CREATED)

**Implementation:**
1. [x] Create `social_media_discovery.py` module
2. [ ] Test on sample cities (Seattle, Chicago, Austin)
3. [ ] Integrate with URL discovery pipeline
4. [ ] Write to Bronze layer: `bronze/social_media_channels`

**Tasks:**
```bash
# Test the new module
cd discovery
python social_media_discovery.py

# Expected output: YouTube, Facebook, Vimeo URLs for test cities
```

### Phase 3: USA.gov Integration (RECOMMENDED)

**Priority: HIGH** - Most authoritative source

**Tasks:**
1. [ ] Create `discovery/usa_gov_directory.py`
2. [ ] Scrape USA.gov local directory for official URLs
3. [ ] Use as primary source (confidence 0.98)
4. [ ] Fallback to pattern matching for missing entries

**Estimated URLs:** 
- ~3,000 cities/counties with verified .gov URLs
- ~10,000+ municipalities (including .org, .us domains)

### Phase 4: ELGL Curated Channels (NEW - HIGH PRIORITY!)

**Priority: HIGH** - Quality over quantity

**Tasks:**
1. [x] Create `discovery/curated_sources.py` ✅
2. [ ] Scrape ELGL "Top YouTube Channels" articles
3. [ ] Parse channel URLs and metadata
4. [ ] Flag as "top-ranked" in database

**Expected Results:**
- 50-100 most active local government channels
- High-quality, verified content
- Innovative digital communication examples

**Why This Matters:**
These are the channels with the MOST meeting videos and BEST production quality!

### Phase 5: NACo County Database (NEW - HIGH PRIORITY!)

**Priority: HIGH** - Comprehensive county coverage

**Tasks:**
1. [x] Create `discovery/curated_sources.py` ✅
2. [ ] Contact NACo for data partnership/export
3. [ ] Integrate NACo County Explorer data
4. [ ] Scrape digital innovation showcase
5. [ ] Cross-reference with GSA .gov domains

**Expected Results:**
- All 3,143 U.S. counties with official websites
- Digital innovation leaders identified
- County media hub URLs

**Partnership Opportunity:**
NACo may provide bulk data export or API access for research/public benefit projects.

### Phase 6: Federal Video Aggregators (OPTIONAL)

**Priority: MEDIUM** - Supplementary source

**Tasks:**
1. [ ] Create `discovery/federal_video_sources.py`
2. [ ] Compile federal agency channels (CDC, HRSA, etc.)
3. [ ] Compile state health department channels (all 50 states)
4. [ ] Add to video sources table

**Use Case:** State-level policy analysis, federal program tracking

---

## Testing & Validation

### Test the New Social Media Discovery

```bash
# 1. Install dependencies
pip install httpx beautifulsoup4

# 2. Run standalone test
cd /home/developer/projects/open-navigator
python scripts/discovery/social_media_discovery.py

# Expected output:
# ✓ Found 3 social media links for Seattle
#   youtube: 1 URLs
#   facebook: 1 URLs
#   twitter: 1 URLs
# ✓ Found 2 social media links for Chicago
#   youtube: 1 URLs
#   facebook: 1 URLs
```

### Integration Test

```python
# Full pipeline test
from discovery.discovery_pipeline import DiscoveryPipeline

pipeline = DiscoveryPipeline()

# 1. Discover jurisdictions (Census data)
# 2. Discover homepage URLs (GSA + patterns)
# 3. NEW: Discover social media (footer scraping)
# 4. Write all to Bronze layer

results = await pipeline.run_full_pipeline(
    limit=100,
    include_social_media=True  # NEW FLAG
)
```

---

## Performance & Scalability

### Current Approach (Dataset-Only)
- ✅ Fast (no web requests)
- ✅ Reliable (static datasets)
- ❌ Limited coverage (only cities in datasets)
- ❌ Stale data (datasets not updated frequently)

### New Approach (Website Scraping)
- ⚠️ Slower (requires web requests)
- ⚠️ Less reliable (websites change)
- ✅ Comprehensive coverage (all cities with websites)
- ✅ Fresh data (real-time discovery)

### Hybrid Strategy (RECOMMENDED)
1. **Start with datasets** (MeetingBank, Open States)
   - Get 1,366 meetings with videos immediately
   - High confidence, validated data
   
2. **Supplement with website scraping**
   - Fill gaps for cities not in datasets
   - Discover newly created channels
   - Verify dataset URLs are still valid

3. **Use USA.gov for verification**
   - Highest confidence for homepage URLs
  Curated Lists (NEW - YOUR SUGGESTIONS!):**
- ELGL Top Channels: 50-100 most active channels 🔥
- NACo Counties: 3,143 counties with official websites 🔥
- NACo Digital Innovation: ~100 innovative counties

**Website Scraping Discovery (NEW):**
- Major cities (100+ population): ~300 cities with YouTube
- Medium cities (50k-100k): ~500 cities with social media
- All municipalities: ~3,000-5,000 with public video channels

**Total Potential:**
- **3,000-5,000 YouTube channels** for meeting videos
- **50-100 TOP-TIER channels** (ELGL curated) 🌟
- **3,143 county websites** (NACo database) 🌟
- **1,000+ Granicus portals** with embedded videos
- **500+ Vimeo accounts**
- **10,000+ Facebook pages** (may have video links)

**Quality Tiers:**
1. **Tier 1 (Highest):** ELGL Top Channels - most active, best quality
2. **Tier 2 (High):** NACo Digital Innovation - county leaders
3. **Tier 3 (Good):** MeetingBank/Dataset channels - verified content
4. **Tier 4 (Discovery):** Website scraping - newly discoveredideo URLs

# Priority 2: USA.gov verified (high confidence)
usa_gov_cities = [...]  # ~3,000 verified .gov sites

# Priority 3: Website scraping (for gaps)
remaining_cities = [...]  # ~87,000 jurisdictions

# Parallel processing
async def process_batch(cities, batch_size=50):
    for i in range(0, len(cities), batch_size):
        batch = cities[i:i+batch_size]
        results = await social_discovery.discover_batch(batch)
        save_to_bronze(results)
        await asyncio.sleep(5)  # Rate limiting
```

---

## Expected Outcomes

### Coverage Estimates

**Dataset-Based Discovery:**
- MeetingBank: 6 cities ✅
- Open States: 50+ state legislatures ✅
- City Scrapers: 100-500 agencies ⚠️ (need to extract video links)

**Website Scraping Discovery (NEW):**
- Major cities (100+ population): ~300 cities with YouTube
- Medium cities (50k-100k): ~500 cities with social media
- All municipalities: ~3,000-5,000 with public video channels

**Total Potential:**
- **3,000-5,000 YouTube channels** for meeting videos
- **1,000+ Granicus portals** with embedded videos
- **500+ Vimeo accounts**
- **10,000+ Facebook pages** (may have video links)

---

## Next Steps

### Immediate Actions (This Week)

1. **Test Social Media Discovery** ✅ READY TO RUN
   ```bash
   python scripts/discovery/social_media_discovery.py
   ```

2. **Integrate with Pipeline**
   - Add to `discovery_pipeline.py`
   - Write results to Bronze layer
   - Create `bronze/social_media_channels` table

3. **Document Integration**
   - Update README with social media discovery
   - Add examples to documentation

### Short-term (Next 2 Weeks)

1. **USA.gov Integration**
   - Create `usa_gov_directory.py`
   - Scrape local directory
   - Use as primary URL source

2. **Enhanced MeetingBank Extraction**
   - Extract all video URLs from `urls` dictionary
   - Test on all 1,366 meetings
   - Validate YouTube links are still active

3. **City Scrapers Video Links**
   - Update `city_scrapers_urls.py`
   - Extract Granicus video URLs
   - Crawl Granicus pages for embedded YouTube

### Long-term (Next Month)

1. **Federal Aggregators**
   - USA.gov/archive integration
   - State health department channels
   - CDC/HRSA video collections

2. **Automated Validation**
   - Check if discovered channels still exist
   - Verify channels have meeting content
   - Score channels by video count and relevance

3. **Scale to 1,000+ Cities**
   - Batch processing framework
   - Parallel scraping with rate limiting
   - Delta Lake storage for discovered channels

---

## Conclusion

### Summary

**Current State:**
- ✅ Video URLs extracted from datasets (1,366 meetings)
- ❌ No website scraping for social media links
- ❌ No USA.gov integration

**Your Suggestion:**
- ✅ **Excellent idea!** Website scraping is the missing piece
- ✅ USA.gov provides most authoritative homepage URLs
- ✅ Footer/contact page scraping will find channels

**Implementation:**
- ✅ Created `social_media_discovery.py` module
- ✅ Ready to test and integrate
- ✅ USA.gov integration guide provided
- ✅ Full roadmap for 1,000+ city coverage

**Impact:**
Going from 6 cities with video URLs to **3,000-5,000 cities with YouTube channels** will dramatically increase the reach of the CommunityOne Open Navigator system!
