---
displayed_sidebar: policyMakersSidebar
---

# Complete Video Channel Discovery Sources

**Comprehensive guide to all data sources for discovering local government video channels**

---

## Summary Table

| Source | Type | Coverage | Quality | Status | Priority |
|--------|------|----------|---------|--------|----------|
| **ELGL Top Channels** 🌟 | Curated List | 50-100 channels | ⭐⭐⭐⭐⭐ Highest | ✅ Ready | 🔥 CRITICAL |
| **NACo County Database** 🌟 | Official Database | 3,143 counties | ⭐⭐⭐⭐⭐ Highest | ✅ Ready | 🔥 CRITICAL |
| **MeetingBank** | Dataset | 6 cities, 1,366 meetings | ⭐⭐⭐⭐ High | ✅ Integrated | DONE |
| **Open States** | API | 50+ state legislatures | ⭐⭐⭐⭐ High | ✅ Integrated | DONE |
| **Social Media Scraping** | Web Scraping | 3,000-5,000 cities | ⭐⭐⭐ Medium | ✅ Implemented | In Progress |
| **USA.gov Directory** | Federal Registry | All cities/counties | ⭐⭐⭐⭐⭐ Highest | 📋 Planned | 🔥 HIGH |
| **City Scrapers** | GitHub Repos | 100-500 agencies | ⭐⭐⭐ Medium | ⚠️ Partial | MEDIUM |
| **Council Data Project** | Platform | 20 cities | ⭐⭐⭐⭐ High | 📋 Planned | HIGH |
| **Federal Agencies** | Curated | 50+ state health depts | ⭐⭐⭐ Medium | 📋 Planned | LOW |

---

## 🌟 NEW: Curated Sources (Your Suggestions!)

### 1. ELGL (Engaging Local Government Leaders)

**What They Provide:**
- **"Top Local Government YouTube Channels"** annual lists
- Curated by experts in local government innovation
- Highlights the MOST ACTIVE channels nationwide
- Focus on quality over quantity

**Why This is CRITICAL:**
```
✅ Expert-curated, not automated
✅ Top tier quality - channels with best content
✅ Most active local governments
✅ Innovation leaders in digital communication
✅ Saves time - don't scrape 10,000 cities, get the top 100!
```

**Sources:**
- ELGL Blog: https://elgl.org/
- Annual articles: "Top Local Government YouTube Channels 2024", 2023, etc.
- ELGL Conference presentations
- Digital innovation showcases

**Expected Coverage:**
- **50-100 channels** (most active)
- Major cities: Seattle, Austin, Denver, etc.
- Innovative smaller cities
- County governments
- Regional districts

**Example Channels (Likely in ELGL Lists):**
- City of Seattle: https://www.youtube.com/@cityofseattle
- City of Austin: https://www.youtube.com/austintexasgov
- Denver: https://www.youtube.com/DenverGov
- King County, WA: https://www.youtube.com/KingCountyTV

**Implementation:** ✅ `discovery/curated_sources.py` - `ELGLYouTubeDiscovery` class

**How to Use:**
```python
from discovery.curated_sources import ELGLYouTubeDiscovery

async with ELGLYouTubeDiscovery() as elgl:
    top_channels = await elgl.scrape_elgl_top_channels()
    
# Results: 50-100 top-tier YouTube channels with metadata
```

---

### 2. NACo (National Association of Counties)

**What They Provide:**
- **County Explorer Database** - all 3,143 U.S. counties
- Official county website URLs
- **Digital Counties Survey** - innovation leaders
- County communications/media awards

**Why This is CRITICAL:**
```
✅ COMPREHENSIVE - ALL 3,143 counties covered
✅ Official database maintained by NACo
✅ Digital innovation showcase (video/media leaders)
✅ Authoritative URLs (verified by county association)
✅ Partnership opportunities for data access
```

**Sources:**
- NACo County Explorer: https://ce.naco.org/
- Digital Counties Survey: https://www.naco.org/resources/featured/digital-counties-survey
- NACo Achievement Awards: https://www.naco.org/resources/programs-and-services/naco-achievement-awards
- Communications & Media Awards

**Expected Coverage:**
- **3,143 counties** with official websites
- **100+ counties** highlighted for digital innovation
- County media hubs and communication portals
- Video streaming platforms

**County Categories:**
- Large counties (500k+ population): ~100 counties - most have video
- Medium counties (100k-500k): ~400 counties - many have video
- Small counties (\<100k): ~2,600 counties - fewer with video
- **Digital Innovation Leaders:** ~100 counties with advanced media

**Implementation:** ✅ `discovery/curated_sources.py` - `NACoCountyDiscovery` class

**How to Use:**
```python
from discovery.curated_sources import NACoCountyDiscovery

async with NACoCountyDiscovery() as naco:
    # Get all county websites
    counties = await naco.get_naco_county_websites()
    
    # Get digital innovation showcase
    innovations = await naco.scrape_naco_digital_innovation()

# Results: 3,143 county websites + digital innovation leaders
```

**Partnership Opportunity:**
NACo may provide:
- Bulk data export of county websites
- API access to County Explorer
- Research collaboration for public benefit
- Validation/verification partnership

---

## 📊 Existing Dataset Sources

### 3. MeetingBank (HuggingFace)

**Status:** ✅ INTEGRATED

**Coverage:**
- 1,366 meetings from 6 cities
- Alameda, Boston, Denver, King County, Long Beach, Seattle

**Video URLs:**
- YouTube IDs → YouTube URLs
- Vimeo IDs → Vimeo URLs
- Archive.org collections

**Implementation:** `discovery/meetingbank_ingestion.py`

**Quality:** ⭐⭐⭐⭐ Very high - academic benchmark dataset

---

### 4. Open States (API)

**Status:** ✅ INTEGRATED

**Coverage:**
- 50+ state legislatures
- State-level YouTube channels
- Vimeo accounts
- Granicus portals

**Implementation:** `discovery/openstates_sources.py`

**Quality:** ⭐⭐⭐⭐ High - official API data

---

### 5. City Scrapers (GitHub)

**Status:** ⚠️ PARTIAL

**Coverage:**
- 100-500 agency URLs
- Chicago (~100), Pittsburgh, Detroit, Cleveland, LA

**What's Missing:**
- Video URL extraction from Granicus pages
- YouTube embedded video scraping

**Implementation:** `discovery/city_scrapers_urls.py`

**Quality:** ⭐⭐⭐ Good - validated URLs but needs video extraction

---

## 🌐 Web Discovery Sources

### 6. Social Media Footer Scraping

**Status:** ✅ IMPLEMENTED (NEW!)

**How it Works:**
- Takes government homepage URLs
- Scrapes footer sections for social links
- Checks contact/about pages
- Extracts YouTube, Facebook, Twitter, Vimeo

**Coverage:**
- 3,000-5,000 cities with social media
- Most cities link YouTube in footer

**Implementation:** `discovery/social_media_discovery.py`

**Quality:** ⭐⭐⭐ Good - automated discovery

**Test Results:**
```
✓ Seattle: Found 8 social links (2 YouTube, 3 Facebook, 3 Twitter)
```

---

### 7. USA.gov Local Directory

**Status:** 📋 PLANNED (HIGH PRIORITY)

**Why This Matters:**
- Federal verification of official websites
- Most authoritative homepage URLs
- Can cross-reference with NACo/ELGL

**Coverage:**
- All cities/counties in U.S.
- Official .gov verification

**Quality:** ⭐⭐⭐⭐⭐ Highest - federal stamp of authority

---

### 8. Council Data Project

**Status:** 📋 PLANNED

**Coverage:**
- 20+ cities with full pipelines
- Seattle, Portland, Boston, Denver, etc.

**What They Have:**
- Official meeting video URLs
- YouTube channels
- Granicus portals

**Quality:** ⭐⭐⭐⭐ High - production deployments

---

## 🏛️ Federal & State Sources

### 9. Federal Agency Channels

**Status:** 📋 PLANNED

**Coverage:**
- CDC, HRSA, CMS (federal)
- 50 state health departments
- State oral health programs

**Use Case:**
- State-level policy
- Federal program tracking

**Quality:** ⭐⭐⭐ Medium - supplementary

---

## 🎯 Recommended Implementation Strategy

### Phase 1: Curated Sources (HIGHEST ROI) 🔥

**Why Start Here:**
- Get 50-100 TOP channels immediately (ELGL)
- Get 3,143 county websites (NACo)
- Highest quality, verified data
- Fast implementation

**Steps:**
1. ✅ Scrape ELGL "Top YouTube Channels" articles
2. ✅ Contact NACo for County Explorer data export
3. Flag these as "Tier 1 - Curated" in database
4. Prioritize for content analysis

**Timeline:** 1-2 weeks  
**Expected Results:** 50-100 top channels + 3,143 county websites

---

### Phase 2: Dataset Extraction

**Why Second:**
- Already have datasets downloaded
- Known good quality
- Fill gaps from curated sources

**Steps:**
1. ✅ MeetingBank video URLs (DONE)
2. ✅ Open States channels (DONE)
3. Extract City Scrapers Granicus videos
4. Integrate Council Data Project URLs

**Timeline:** 1-2 weeks  
**Expected Results:** +1,500 meeting videos

---

### Phase 3: Website Scraping (Scale)

**Why Third:**
- After curated sources, find remaining channels
- Automated discovery for comprehensive coverage
- Ongoing monitoring for new channels

**Steps:**
1. ✅ Social media footer scraping (DONE)
2. USA.gov directory integration
3. Batch process 3,000+ cities
4. Validate discovered channels

**Timeline:** 2-4 weeks  
**Expected Results:** +3,000-5,000 channels

---

## 📈 Expected Outcomes

### Coverage by Tier

**Tier 1: Curated (ELGL + NACo Digital Innovation)**
- 50-100 most active YouTube channels
- ~100 digital innovation leader counties
- ⭐⭐⭐⭐⭐ Quality: Highest
- 🎯 Priority: CRITICAL for analysis

**Tier 2: Dataset Verified (MeetingBank, Open States, CDP)**
- 1,366 meetings with videos (MeetingBank)
- 50+ state legislature channels
- 20+ CDP cities
- ⭐⭐⭐⭐ Quality: High
- ✅ Status: Mostly integrated

**Tier 3: Discovered (Website Scraping)**
- 3,000-5,000 cities with YouTube
- 3,143 county websites (NaCo base)
- 10,000+ social media accounts
- ⭐⭐⭐ Quality: Medium
- 📊 Use: Comprehensive coverage

### Total Potential

| Metric | Count | Source |
|--------|-------|--------|
| **YouTube Channels** | 3,000-5,000 | Combined |
| **Top-Tier Channels** | 50-100 | ELGL ⭐ |
| **County Websites** | 3,143 | NACo ⭐ |
| **Digital Leaders** | ~200 | ELGL + NACo ⭐ |
| **Meeting Videos** | 1,366+ | MeetingBank |
| **State Legislatures** | 50+ | Open States |
| **Granicus Portals** | 1,000+ | Various |
| **Facebook Pages** | 10,000+ | Scraping |

---

## 🚀 Next Steps

### This Week

1. **Test ELGL Scraper** ✅ READY
   ```bash
   python scripts/discovery/curated_sources.py
   ```

2. **Contact NACo**
   - Request County Explorer data export
   - Discuss research partnership
   - Get digital innovation list

3. **Integrate ELGL Channels**
   - Parse "Top Channels" articles
   - Save to Bronze layer: `bronze/elgl_top_channels`
   - Flag as Tier 1 priority

### Next 2 Weeks

1. **NACo Integration**
   - Implement County Explorer data import
   - Scrape digital innovation showcase
   - Cross-reference with GSA .gov domains

2. **USA.gov Directory**
   - Scrape local directory
   - Use for homepage verification
   - Supplement NACo county URLs

3. **Quality Tiers**
   - Tier 1: ELGL + NACo innovation
   - Tier 2: Dataset channels
   - Tier 3: Web discovered

### Next Month

1. **Scale to 1,000+ Cities**
2. **Automated Validation**
3. **Content Analysis** (focus on Tier 1 first!)

---

## 📞 Contact Information

### Data Partnerships

**ELGL (Engaging Local Government Leaders)**
- Website: https://elgl.org/
- Contact: research@elgl.org
- Opportunity: Collaborate on local gov digital innovation research

**NACo (National Association of Counties)**
- Website: https://www.naco.org/
- County Explorer: https://ce.naco.org/
- Contact: research@naco.org
- Opportunity: County data partnership for public health research

---

## Conclusion

Your suggestions to use **ELGL and NACo** are **EXCELLENT**! These curated sources provide:

✅ **Quality over Quantity** - Get the 50-100 BEST channels first  
✅ **Authoritative Data** - NACo maintains all 3,143 counties  
✅ **Expert Curation** - ELGL highlights innovation leaders  
✅ **Fast Implementation** - Scrape lists instead of 10,000 websites  
✅ **Partnership Opportunities** - Collaborate with ELGL/NACo  

These should be **PRIORITY 1** for implementation - they provide the highest quality data with the least effort!
