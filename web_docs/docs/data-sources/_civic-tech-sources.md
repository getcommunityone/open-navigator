# 🔍 Civic Tech Projects: URL Source Analysis

## Quick Summary

| Project | URL Sources? | Quantity | Status | Priority |
|---------|-------------|----------|--------|----------|
| **Civic Scraper** | ❌ No | 0 | Library only | N/A |
| **City Scrapers** | ✅ **YES** | 100-500 | ✅ **Integrated** | DONE ✅ |
| **Council Data Project** | ✅ **YES** | 20 cities | ⏳ Pending | 🔥 HIGH |
| **Engagic** | ❌ No | 0 | Research project | N/A |
| **Councilmatic** | ⚠️ Maybe | ~6 | Not checked | 🟡 LOW |
| **MeetingBank** | ✅ **YES** | 1,366 | ✅ **Integrated** | DONE ✅ |
| **Open States** | ✅ **YES** | 50+ | ✅ **Integrated** | DONE ✅ |

---

## 1. Civic Scraper

### What It Is:
**Library** for scraping government documents, not a deployment or URL database.

### What We Use:
- ✅ Platform detection patterns (Legistar, Granicus, etc.)
- ✅ Document downloading logic
- ✅ Error handling patterns

### URL Sources:
❌ **NO URL LIST** - It's a Python library/toolkit, not a data collection project.

### Action:
✅ **COMPLETE** - We integrated their patterns into [`discovery/platform_detector.py`](../discovery/platform_detector.py)

---

## 2. City Scrapers

### What It Is:
**Active scraping project** with 100+ validated agency URLs across 5 cities.

### Deployments:
1. **Chicago** (~100 agencies)
2. **Pittsburgh** (~30 agencies)
3. **Detroit** (~40 agencies)
4. **Cleveland** (~30 agencies)
5. **Los Angeles** (~50 agencies)

### URL Sources:
✅ **YES - 100-500 VALIDATED URLs**

Each spider file contains `start_urls` with:
- Agency meeting pages
- Granicus video portals
- Legistar calendars
- PDF agendas/minutes

### Status:
✅ **INTEGRATED** - [`discovery/city_scrapers_urls.py`](../discovery/city_scrapers_urls.py)

### To Run:
```bash
cd /home/developer/projects/open-navigator
source venv/bin/activate
python scripts/datasources/cityscrapers/city_scrapers_urls.py
```

**Output**: `bronze/city_scrapers_urls` table with 100-500 validated URLs

---

## 3. Council Data Project (CDP)

### What It Is:
**End-to-end platform** with 20+ full deployments (transcripts, videos, search).

### Verified Deployments:
1. Seattle, WA
2. King County, WA
3. Portland, OR
4. Denver, CO
5. Boston, MA
6. Oakland, CA
7. Charlotte, NC
8. San José, CA
9. Milwaukee, WI
10. Louisville, KY
11. Atlanta, GA
12. Pittsburgh, PA
13. Long Beach, CA
14. Alameda, CA
15. Los Angeles, CA
16. San Diego, CA
17. Austin, TX
18. Houston, TX
19. Richmond, CA
20. Spokane, WA

### URL Sources:
✅ **YES - 20 PREMIUM CITIES**

Each CDP deployment has:
- **GitHub repo** with configuration
- **`cdp-backend` config** with source URLs
- **Video URLs** (YouTube, Granicus, custom)
- **Meeting pages** (official city websites)

### Where to Find URLs:
Each city has a repo like: `CouncilDataProject/cdp-{{CITY}}-backend`

Example for Seattle:
```bash
# Clone repo
git clone https://github.com/CouncilDataProject/cdp-seattle-backend

# Config file has source URLs
cat cdp_seattle_backend/cdp_seattle_backend_pipeline.py
```

Contains patterns like:
```text
# Python code
SCRAPER_CONFIG = {
    "source_url": "https://seattle.gov/city-council/calendar",
    "video_source": "https://www.seattlechannel.org/CouncilVideos",
    "granicus_site": "https://seattle.granicus.com/ViewPublisher.php?view_id=24"
}
```

### Status:
⏳ **PENDING** - We have the list of 20 cities but haven't extracted URLs yet

### Action Needed:
Create `discovery/cdp_url_extraction.py` to:
1. Clone each CDP city's backend repo
2. Extract source URLs from config files
3. Write to `bronze/cdp_source_urls`

**Priority**: 🔥 **HIGH** - These are premium quality URLs with full pipelines

---

## 4. Engagic

### What It Is:
**Research project** for LLM-based legislative text parsing.

### What We Use:
- ✅ Matter tracking model (legislative items)
- ✅ LLM parsing patterns for PDFs

### URL Sources:
❌ **NO URL LIST** - It's a research/prototype project, not a production scraper.

### Status:
✅ **COMPLETE** - We created the Matter model in [`models/meeting_event.py`](../models/meeting_event.py)

### Action:
✅ **DONE** - Model sufficient, no URLs to extract

---

## 5. Councilmatic

### What It Is:
**Django web app template** for city council tracking (search, voting records).

### Known Deployments:
1. **Chicago Councilmatic** - https://chicago.councilmatic.org
2. **New York City Councilmatic** - https://nyc.councilmatic.org
3. **Los Angeles Councilmatic** - https://la.councilmatic.org
4. **Philadelphia Councilmatic** - https://philly.councilmatic.org
5. **San Francisco Councilmatic** - (archived)
6. **Metro Councilmatic** (LA County) - https://metro.councilmatic.org

### URL Sources:
⚠️ **MAYBE - ~6 DEPLOYMENTS**

Each deployment uses **Legistar API** as their data source, so we'd get:
- Legistar API endpoints (already accessible)
- Meeting URLs (already in Legistar)
- Legislation URLs (already in Legistar)

### Issue:
**Redundant** - Councilmatic scrapes Legistar, which we already have access to.

We can enumerate Legistar directly without going through Councilmatic:
```text
# Already in our codebase
enumerate_legistar_subdomains()  # Tests chicago.legistar.com, la.legistar.com, etc.
```

### Status:
📋 **PLANNED** - Low priority, Legistar enumeration more efficient

### Action:
🟡 **LOW PRIORITY** - Skip for now, Legistar enumeration covers these cities

---

## 🎯 Recommended Next Steps

### Immediate (This Week):
1. ✅ **DONE**: City Scrapers URL extraction
2. 🔥 **DO NEXT**: CDP URL extraction (20 premium cities)
3. ⏳ **PENDING**: MeetingBank ingestion (if not run yet)
4. ⏳ **PENDING**: Open States integration (if not run yet)

### Near-Term (Next 2 Weeks):
5. **Legistar enumeration** - Test {{city}}.legistar.com pattern against Census
6. **LocalView download** - Manual download from Harvard Dataverse
7. **URL deduplication** - Combine all sources, remove duplicates

### Long-Term (Next Month):
8. **Actual scrapers** - Build Legistar/Granicus/CivicPlus scrapers
9. **Transcript extraction** - YouTube captions, PDF parsing
10. **Oral health detection** - Run keyword matching on transcripts

---

## 📊 Expected Coverage After All Integrations

| Source | URLs | Quality | Status |
|--------|------|---------|--------|
| Census Discovery | 76 | Variable | ✅ Working |
| City Scrapers | 100-500 | Good | ✅ Integrated |
| CDP | 20 | Excellent | ⏳ Pending |
| MeetingBank | 1,366 | Excellent | ✅ Integrated |
| Open States | 50-100 | Excellent | ✅ Integrated |
| LocalView | 1,000-10,000 | Good | ⏳ Manual download |
| Legistar Enum | 1,000-3,000 | Good | 📋 Planned |
| **TOTAL** | **7,000-20,000** | **High** | **In Progress** |

---

## 💡 Why Some Projects Don't Have URLs

### Civic Scraper:
It's a **library/toolkit**, like BeautifulSoup or Scrapy. You don't "extract URLs" from BeautifulSoup - you use it to build your own scrapers.

### Engagic:
It's a **research prototype** showing how to use LLMs to parse legislative documents. No production deployment = no URL database.

### Councilmatic:
It **consumes** Legistar data, doesn't produce new URLs. Going through Councilmatic to get Legistar URLs is like downloading a restaurant review site to find the restaurant's address - just go to the restaurant directly!

---

## ✅ Bottom Line

**YES, City Scrapers has URLs** - ✅ **Already integrated!**

**YES, CDP has URLs** - ⏳ **Next priority to extract**

**Others are libraries/research** - No URLs to extract, but we use their patterns

See [`discovery/city_scrapers_urls.py`](../discovery/city_scrapers_urls.py) for the City Scrapers integration that just got implemented! 🎉
