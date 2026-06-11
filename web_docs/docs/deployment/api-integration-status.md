---
title: API Integration Status
---

# Civic Data API Integration Status

Status of major civic data APIs in the Open Navigator platform.

## ✅ Fully Integrated APIs

### 1. Open States API ✅
**Status:** INTEGRATED  
**File:** `discovery/openstates_sources.py`  
**API Docs:** https://openstates.org/api/  
**What it provides:**
- 50+ state legislatures
- State-level officials
- Legislative bills and votes
- Committee information
- Video sources (YouTube, Vimeo, Granicus)

**Usage:**
```bash
# Set API key in .env
OPENSTATES_API_KEY=your-key-here

# Run ingestion
python -m discovery.openstates_sources
```

**API Key:** Free tier - 50,000 requests/month  
**Sign up:** https://openstates.org/accounts/signup/

---

### 2. NCES District Search ✅
**Status:** INTEGRATED  
**File:** `discovery/nces_ingestion.py`  
**Data Source:** https://nces.ed.gov/ccd/  
**What it provides:**
- 13,000+ school districts nationwide
- School district boundaries
- Contact information
- Enrollment and demographic data
- Physical addresses

**Usage:**
```bash
# Run ingestion (downloads CSV from NCES)
python -m discovery.nces_ingestion
```

**API Key:** Not required (public CSV downloads)

---

### 3. Wikidata ✅ **NEW!**
**Status:** INTEGRATED  
**File:** `discovery/wikidata_integration.py`  
**API Docs:** https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service  
**What it provides:**
- Structured knowledge base (powers Wikipedia infoboxes)
- Best for connecting people → organizations → locations
- SPARQL queries for complex relationships
- Millions of interconnected entities

**Why it's amazing:**
- ✅ **Completely FREE** - no API key required
- ✅ **Highly interconnected** - find person → see all linked organizations
- ✅ **Structured data** - triples (subject-predicate-object)
- ✅ **Real Wikipedia data** - millions of entities
- ✅ **Perfect for relationships** - "All school board members in Alabama"

**Usage:**
```python
from discovery.wikidata_integration import WikidataQuery

wikidata = WikidataQuery()

# Find school board members
members = await wikidata.find_school_board_members(state="Alabama")

# Find cities in a county
cities = await wikidata.find_cities_in_county("Tuscaloosa County", "Alabama")

# Find organizations a person is affiliated with
orgs = await wikidata.find_person_organizations("Walt Maddox")
```

**API Key:** Not required (completely free)

---

### 4. DBpedia ✅ **NEW!**
**Status:** INTEGRATED  
**File:** `discovery/dbpedia_integration.py`  
**API Docs:** http://lookup.dbpedia.org/api/doc/  
**What it provides:**
- Structured data from Wikipedia infoboxes
- Perfect for autocomplete/type-ahead search
- Every Wikipedia page as a structured "resource"
- Mayor, population, school district info

**Why it's perfect for search:**
- ✅ **Completely FREE** - no API key required
- ✅ **Designed for autocomplete** - Lookup API is type-ahead optimized
- ✅ **Instant context** - Get Mayor, population for "Tuscaloosa"
- ✅ **Rich data** - Structured triples from Wikipedia
- ✅ **Fast** - Optimized for search box suggestions

**Usage:**
```python
from discovery.dbpedia_integration import DBpediaLookup

dbpedia = DBpediaLookup()

# Autocomplete search
results = await dbpedia.search("Tuscaloosa", max_results=10)

# Get detailed info
info = await dbpedia.get_resource_info("Tuscaloosa,_Alabama")

# Search by type
cities = await dbpedia.find_cities(state="Alabama")
people = await dbpedia.find_people("Alabama mayor")
```

**API Key:** Not required (completely free)

---

## � Reference Implementations (Paid Services)

These integrations are provided as reference code but require paid API access.

### Ballotpedia API v3.0 💰
**Status:** REFERENCE ONLY - Paid service  
**File:** `discovery/ballotpedia_integration.py` (reference implementation)  
**Website:** https://ballotpedia.org  
**API Docs:** https://ballotpedia.org/API_documentation  
**API Announcement:** https://ballotpedia.org/Just_launched:_Ballotpedia's_API_Version_3.0  
**Pricing:** Contact Ballotpedia for pricing (not free)  

**What it provides:**
- Elected officials (federal, state, local)
- Ballot measures and initiatives
- Election results
- Candidate information

**Current Implementation:**
- ✅ Official API v3.0 client (BallotpediaAPI class)
- ✅ Web scraping fallback (BallotpediaDiscovery class)
- ✅ Leader search by name
- ✅ City officials discovery
- ✅ Ballot measures by state/year
- ✅ Rate-limited web scraping (2s delays)

**API Key:** Contact Ballotpedia for access  
**Get access:** https://ballotpedia.org/API_documentation

**Usage (Official API - RECOMMENDED):**
```python
from discovery.ballotpedia_integration import BallotpediaAPI

# Set BALLOTPEDIA_API_KEY in .env
api = BallotpediaAPI()

# Get officials via official API
officials = await api.get_officials("Tuscaloosa", state="Alabama")

# Get ballot measures via official API
measures = await api.get_ballot_measures("Alabama", year=2024)
```

**Usage (Web Scraping Fallback):**
```python
from discovery.ballotpedia_integration import BallotpediaDiscovery

discovery = BallotpediaDiscovery()

# Search for a leader (web scraping)
leader = await discovery.search_leader("Walt Maddox", "Alabama")

# Get city officials (web scraping)
officials = await discovery.get_city_officials("Tuscaloosa", "Alabama")

# Get ballot measures (web scraping)
measures = await discovery.get_ballot_measures("Alabama", year=2024)
```

**Notes:**
- ⚠️ **Paid Service** - Ballotpedia API requires payment
- Not recommended for free/open-source projects
- Code provided as reference for those with API access
- Consider alternatives: Google Civic API (free) for officials, Open States (free) for state data
- Web scraping may violate terms of service - use at own risk

**Alternative Free APIs:**
- Google Civic Information API - Free, 25k requests/day
- Open States API - Free, 50k requests/month
- NCES - Free public data for school boards

---

## ❌ Not Yet Integrated

### 3. Google Civic Information API ❌
**Status:** NOT INTEGRATED  
**API Docs:** https://developers.google.com/civic-information  
**What it would provide:**
- Address-to-representative mapping
- Elected officials by address
- Election data
- Polling locations
- Voter information

**Why integrate:**
- Best API for "who represents this address?"
- Official election information
- Comprehensive official contact info
- Free tier: 25,000 requests/day

**API Key Required:** Yes (Google Cloud Console)  
**Free Tier:** 25,000 requests/day  
**Sign up:** https://console.cloud.google.com/

**Next Steps:**
1. Create `discovery/google_civic_integration.py`
2. Add API key to `.env`: `GOOGLE_CIVIC_API_KEY=your-key`
3. Implement endpoints:
   - `representativeInfoByAddress(address)`
   - `elections()`
   - `voterInfoQuery(address)`

---

### Cicero API 💰 (Reference Only)
**Status:** NOT INTEGRATED - Paid service  
**API Docs:** https://cicerodata.com  
**What it would provide:**
- Local district boundaries (very accurate)
- Contact info for local officials
- Non-legislative officials (school boards, water districts, etc.)
- Real-time updates

**Why NOT integrating:**
- ⚠️ **Paid Service** - Enterprise/professional pricing
- Not suitable for free/open-source projects
- Free alternatives available (Google Civic, Open States)

**Free Alternatives:**
- Google Civic Information API - Address-to-representative mapping
- Open States API - State-level officials and districts
- Census TIGER/Line - Free boundary shapefiles

---

## 📊 Integration Summary

| API | Status | Free? | File | Key Required? |
|-----|--------|-------|------|---------------|
| **Wikidata** | ✅ Integrated | Yes | `wikidata_integration.py` | No |
| **DBpedia** | ✅ Integrated | Yes | `dbpedia_integration.py` | No |
| **Open States** | ✅ Integrated | Yes | `openstates_sources.py` | Yes (free) |
| **NCES** | ✅ Integrated | Yes | `nces_ingestion.py` | No |
| **Google Civic** | ❌ Not Yet | Yes | `google_civic_integration.py` | Yes (free) |

**Reference Only (Paid Services):**
- **Ballotpedia API v3.0** - Paid service, code available for reference in `ballotpedia_integration.py`
- **Cicero API** - Enterprise-grade district boundaries (paid)

---

## 🎯 The "Free Stack" for School Boards & Civic Data

Since school board data is the **hardest to find for free**, here's how to combine FREE sources:

| Source | Best Use Case | API Type | File |
|--------|---------------|----------|------|
| **Wikidata** | Relationships (People → Boards) | SPARQL | `wikidata_integration.py` |
| **Google Civic** | Address → Specific Board | REST | `google_civic_integration.py` |
| **NCES** | Official District IDs & Boundaries | CSV | `nces_ingestion.py` |
| **DBpedia** | Autocomplete & Context | Lookup | `dbpedia_integration.py` |
| **Open States** | State-Level Officials & Bills | REST | `openstates_sources.py` |

### How They Work Together:

**1. User enters address in search box:**
- **DBpedia Lookup** → Autocomplete suggestions as they type
- **Google Civic API** → Maps address to exact school board district
- **NCES Data** → Official district ID, boundaries, demographics

**2. User wants to see school board members:**
- **Wikidata SPARQL** → "Find all members of [School Board Name]"
- **Wikidata** → Links each person to their organizations
- **DBpedia** → Rich context from Wikipedia (photos, bio, etc.)

**3. User wants state-level info:**
- **Open States API** → State legislators, bills, committees
- **Wikidata** → State government structure, officials
- **DBpedia** → State context and background

**Example Query Flow:**
```
User types: "Tuscaloosa schools"
  ↓
DBpedia: Autocomplete → "Tuscaloosa City Schools"
  ↓
User enters address: "123 Main St, Tuscaloosa, AL"
  ↓
Google Civic: → Maps to "Tuscaloosa City School District"
  ↓
NCES: → Gets official district ID, enrollment, demographics
  ↓
Wikidata: → Finds all school board members
  ↓
DBpedia: → Gets rich Wikipedia context for each member
```

---

## 🎯 Recommended Integration Priority

### ✅ Already Integrated (Free + High Value)
1. ✅ **Wikidata** - BEST for relationships (people → organizations) - **FREE, no key**
2. ✅ **DBpedia** - BEST for autocomplete/search - **FREE, no key**
3. ✅ **Open States** - State legislature data - **FREE, key required**
4. ✅ **NCES** - School district data - **FREE, no key**

### 🔴 High Priority (Not Yet Integrated)
5. 🔴 **Google Civic API** - Address → officials mapping - **FREE, key required**
   - Code ready in `google_civic_integration.py`
   - Just need API key from Google Cloud Console
   - 25,000 requests/day free tier

### ❌ Not Recommended (Paid Services)
- ❌ **Ballotpedia API** - Paid service, use free alternatives
- ❌ **Cicero API** - Enterprise pricing, use Google Civic + Wikidata instead

---

## 🏆 Why Wikidata + DBpedia are Game-Changers

### **Wikidata = The Relationship Database**
- Find **all school board members** in a state
- See **every organization** a person belongs to
- Link **people → positions → locations**
- Example: "Walt Maddox" → Mayor → Tuscaloosa → School Board connections

### **DBpedia = The Autocomplete Engine**
- **Perfect for search boxes** - Lookup API designed for type-ahead
- Type "Tusc" → Get instant suggestions
- Every Wikipedia page = structured data
- Get Mayor, population, district info instantly

### **Together They're Unbeatable:**
1. **DBpedia** for autocomplete (fast, optimized for search)
2. **Wikidata** for relationships (deep, interconnected data)
3. **Google Civic** for address mapping (precise, official)
4. **NCES** for official IDs (authoritative, complete)
5. **Open States** for state-level (comprehensive, up-to-date)

**All FREE. No paid services needed!** 🎉

---

## 🚀 Quick Start: Adding Google Civic API

The highest-value missing integration is **Google Civic Information API**.

### Step 1: Get API Key
```bash
# Visit Google Cloud Console
open https://console.cloud.google.com/

# Create project
# Enable "Google Civic Information API"
# Create API key
```

### Step 2: Add to Environment
```bash
# Add to .env
echo "GOOGLE_CIVIC_API_KEY=your-key-here" >> .env
```

### Step 3: Create Integration (stub provided below)
See `discovery/google_civic_integration.py` (to be created)

---

## 📝 Example: Google Civic Integration Stub

```python
"""
Google Civic Information API Integration

Best for address-to-representative mapping.

API: https://developers.google.com/civic-information
Free Tier: 25,000 requests/day
"""
import httpx
from typing import Dict, List, Optional
from loguru import logger
from config.settings import settings


class GoogleCivicAPI:
    BASE_URL = "https://www.googleapis.com/civicinfo/v2"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.google_civic_api_key
    
    async def get_representatives(self, address: str) -> Dict:
        """Get elected officials for an address."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/representatives",
                params={"address": address, "key": self.api_key}
            )
            return response.json()
    
    async def get_elections(self) -> Dict:
        """Get upcoming elections."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/elections",
                params={"key": self.api_key}
            )
            return response.json()
```

---

## 🔍 What Each API is Best For

**Open States:** State legislature bills, votes, committees  
**NCES:** School district boundaries and demographics  
**Ballotpedia:** Elected officials, ballot measures, elections  
**Google Civic:** Address → representatives (best for this!)  
**Cicero:** Local district boundaries (enterprise-grade)

---

## 📚 Additional Resources

- **Open States Documentation:** https://docs.openstates.org/
- **NCES Common Core of Data:** https://nces.ed.gov/ccd/files.asp
- **Ballotpedia Sample Pages:** https://ballotpedia.org/Main_Page
- **Google Civic API Guide:** https://developers.google.com/civic-information/docs/using_api
- **Cicero Use Cases:** https://cicerodata.com/use-cases

---

## ✅ Next Steps

1. **Test Ballotpedia integration:**
   ```bash
   cd /home/developer/projects/open-navigator
   source .venv/bin/activate
   python scripts/discovery/ballotpedia_integration.py
   ```

2. **Create Google Civic integration:**
   - Get API key from Google Cloud Console
   - Create `discovery/google_civic_integration.py`
   - Add to API routes in `api/main.py`

3. **Evaluate Cicero:**
   - Contact cicerodata.com for pricing
   - Decide if worth the cost for enterprise deployment

4. **Update frontend:**
   - Add "Find My Representatives" feature using Google Civic
   - Show ballot measures from Ballotpedia
   - Link to school board from NCES data
