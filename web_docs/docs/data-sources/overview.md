---
displayed_sidebar: policyMakersSidebar
---

# Data Sources Overview

This document covers the **official, free, public datasets** used by Open Navigator.

:::tip[📚 Full Citations & Academic References]
For complete citations, licenses, and attribution for all data sources, see:

👉 **[Citations & Data Sources](./citations.md)** — Includes BibTeX citations, license information, coverage details, and links to original sources.
:::

## 📊 Data Scale & Coverage

Open Navigator provides comprehensive coverage across the United States:

| Data Type | Count | Coverage |
|-----------|-------|----------|
| **Government Jurisdictions** | 90,000+ | All U.S. local governments |
| **Counties** | 3,144 | 100% of U.S. counties |
| **Municipalities** | 19,500+ | Cities, towns, villages |
| **Townships** | 36,000+ | County subdivisions |
| **School Districts** | 13,000+ | Complete NCES coverage |
| **Nonprofit Organizations** | 3,000,000+ | All IRS-registered 501(c) orgs |
| **Official .gov Domains** | 15,000+ | CISA validated domains |
| **States** | 50 | All U.S. states + DC |
| **Meeting Video Sources** | 1,000+ | Cities with full transcripts |

**Key Insight:** All data sources are **100% free and public** - no subscriptions, no API fees, no paywalls.

---

## 📂 Data Source Categories

Open Navigator integrates data from six main categories:

1. **[Government Jurisdictions](#government-jurisdiction-data)** - Cities, counties, school districts (this page)
2. **[Nonprofit Organizations](./nonprofit-sources.md)** - IRS Form 990s, charity ratings, transparency data
3. **[Ballot Measures & Elections](./ballot-election-sources.md)** - Propositions, referendums, election results
4. **[Public Opinion & Surveys](./polling-survey-sources.md)** - Scientifically validated survey questions, polling data
5. **[Fact-Checking & Verification](./factcheck-sources.md)** - Google Fact Check API, FactCheck.org, PolitiFact claim verification
6. **[Open Source Projects](./open-source-repositories.md)** - Civic tech repositories, community tools, digital public goods

---

## 🏛️ Government Jurisdiction Data

### 1. CISA .gov Domain Master List ⭐ **Most Authoritative**

**Source:** Cybersecurity and Infrastructure Security Agency (CISA)  
**URL:** https://github.com/cisagov/dotgov-data  
**File:** `current-full.csv` (updated daily!)

**What It Contains:**
- **15,000+ registered .gov domains**
- Domain Type: City, County, State, Tribal, School District
- Organization names and locations
- Security contacts and registration dates

**Why We Use It:**
> "The most authoritative source for government URLs is CISA. They maintain a daily-updated repository of every registered .gov domain."

**How We Use It:**
```python
# Direct download from GitHub
from discovery.gsa_domains import GSADomainList

gsa = GSADomainList()
domains_df = await gsa.download_domain_list()
```

**Lakehouse Strategy:**
1. Ingest to **Bronze Layer** (`bronze/gov_domains`)
2. Filter by `Domain Type` for targeted scraping (City, County)
3. Use for **exact matching** (confidence: 0.95-1.0)
4. Use for **fuzzy matching** with 75%+ similarity

---

### 2. U.S. Census Bureau - Government Integrated Directory (GID)

**Source:** U.S. Census Bureau, Government Statistics  
**URL:** https://www.census.gov/programs-surveys/gus.html  
**Dataset:** 2022 Census of Governments

**What It Contains:**
- **90,735 total government units**
  - 3,143 counties
  - 19,495 municipalities (cities/towns)
  - 16,504 townships
  - 13,051 school districts
  - 38,542 special districts
- FIPS codes (standardized IDs)
- Population data
- Geographic hierarchy (state, county, place)

**Why We Use It:**
> "The Census Bureau GID provides a list of all 90,000+ legal government units. You can join this against the CISA list to find 'missing' URLs that your agent needs to hunt for."

**How We Use It:**
```python
from discovery.census_ingestion import CensusGovernmentIngestion

census = CensusGovernmentIngestion()
dfs = await census.ingest_all_jurisdictions()
```

**Lakehouse Strategy:**
1. Ingest to **Bronze Layer** (`bronze/jurisdictions/{{type}}`)
2. Create **unified view** with all jurisdiction types
3. **Join with CISA** to identify missing URLs
4. Prioritize by population for scraping

---

### 3. NCES Common Core of Data (CCD)

**Source:** National Center for Education Statistics (NCES)  
**URL:** https://nces.ed.gov/ccd/  
**Dataset:** Local Education Agency (LEA) Universe Survey

**What It Contains:**
- **13,000+ school districts**
- Official district names and NCES IDs
- Physical addresses and phone numbers
- **Website URLs** (when available)
- Enrollment and demographic data
- District type (Regular, Charter, etc.)

**Why We Use It:**
> "Since one of your goals is tracking school dental screenings, you need a dedicated list of school board domains, as these are often separate from city governments."

**How We Use It:**
```python
from discovery.nces_ingestion import NCESSchoolDistrictIngestion

nces = NCESSchoolDistrictIngestion()
districts_df = await nces.ingest_school_districts()
```

**Lakehouse Strategy:**
1. Ingest to **Bronze Layer** (`bronze/nces_school_districts`)
2. Extract **provided URLs** (many NCES records include website field!)
3. Use district names to **generate URL patterns** for missing sites
4. Common pattern: `{{district}}.k12.{{state}}.us`

---

## 📋 Summary Table: Where to Pull the Lists

| Jurisdiction Type | Primary Free Source | Format | Coverage |
|-------------------|---------------------|--------|----------|
| **All Official .gov** | CISA dotgov-data | CSV / GitHub | 15,000+ domains |
| **School Districts** | NCES CCD Data | CSV | 13,000+ districts |
| **Counties/Cities** | Census Bureau GID | CSV | 22,638 jurisdictions |
| **Townships** | Census Bureau GID | CSV | 16,504 townships |
| **Special Districts** | Census Bureau GID | CSV | 38,542 districts |
| **State Legislatures** | LegiScan API | JSON / API | 50 states |

---

## 🔍 Scraping Strategy (Based on Your Guidance)

### Step 1: Ingest
```bash
python main.py init  # Initialize Delta Lake
python main.py discover-jurisdictions --limit 100  # Test run
```

**Pulls:**
- ✅ `current-full.csv` from CISA → Bronze layer
- ✅ Census GID CSVs → Bronze layer  
- ✅ NCES CCD data → Bronze layer

### Step 2: Filter
```python
# Create Silver layer table
df = spark.read.format("delta").load("bronze/gov_domains")

# Filter for local governments
local_govs = df.filter(
    col("Domain Type").isin(["City", "County", "School District"])
)
```

**Result:** ~8,000-10,000 high-priority targets

### Step 3: Crawl
```bash
python main.py scrape-batch --source discovered --limit 50
```

**Points Scrapy agents at discovered URLs:**
- Homepage URLs from CISA + pattern matching
- Verified with HTTP HEAD/GET requests
- Prioritized by population and domain type

### Step 4: Keyword Hunt
**Agent searches for:**
- "Minutes" pages
- "Agendas" pages  
- "Meetings" pages
- "Water" + "Fluoride" content

**CMS Detection:**
- Granicus
- CivicClerk
- Municode
- Legistar

---

## 🚀 Non-.gov Coverage

**Many smaller municipalities use non-.gov domains:**
- `.org` (e.g., `cityofsomewhere.org`)
- `.us` (e.g., `somewhere.ca.us`)
- `.net` (e.g., `districschools.net`)

**Our URL patterns cover these:**
```python
# Pattern generation includes:
patterns = [
    "https://cityname.gov",       # Primary
    "https://cityname.us",        # Alternative
    "https://cityname.org",       # Non-profit
    "https://cityname.net",       # Legacy
]
```

**Future Enhancement:**
- [State and Local Government on the Net](https://www.statelocalgov.net/)
- Could scrape this directory as fallback for missing URLs
- Manually curated list of non-.gov government sites

---

## 💰 Cost: $0

All data sources are **free and publicly available**:

| Source | Cost | Update Frequency |
|--------|------|------------------|
| CISA dotgov-data | **$0** | Daily |
| Census Bureau GID | **$0** | Annual |
| NCES CCD | **$0** | Annual |
| Pattern Matching | **$0** | On-demand |

**Total API costs:** **$0** 🎉

Compare to deprecated approach:
- ~~Google Custom Search API: $5/1000 queries = ~$150~~
- ~~Bing Search API: $7/1000 queries = ~$90~~

**Savings: $240+ per discovery run** ✅

---

## 📚 References

**Government Jurisdiction Data:**
- **CISA .gov Domains:** https://github.com/cisagov/dotgov-data
- **Census Bureau GID:** https://www.census.gov/programs-surveys/gus.html
- **NCES CCD:** https://nces.ed.gov/ccd/
- **State/Local Gov Directory:** https://www.statelocalgov.net/
- **LegiScan API:** https://legiscan.com/legiscan

**Nonprofit Data:**
**Nonprofit Data:**
- See [Nonprofit Data Sources](./nonprofit-sources.md) for ProPublica, Charity Navigator, Candid/GuideStar, and GiveWell

**Open Source Projects:**
- See [Open Source Repositories](./open-source-repositories.md) for civic tech projects, GitHub data, and community tools

---

## ✅ Credits

**System Architecture:** Medallion Architecture (Bronze → Silver → Gold)  
**Data Engineering Pattern:** Delta Lake + PySpark  
**Sustainable Approach:** No deprecated search APIs  
**Guidance Source:** Professional data engineering best practices

**Thank you for the excellent guidance on official data sources!** 🙏

This system now uses **the exact sources recommended by data engineers** to map the U.S. government landscape. 🦷✨
