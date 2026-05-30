---
displayed_sidebar: developersSidebar
---

# Open Source Repository Data Sources

Open Navigator treats **open source community projects as first-class citizens** alongside government jurisdictions and nonprofit organizations. This document lists civic tech and community infrastructure repositories related to public engagement.

---

## 🌐 Why Open Source Matters for Civic Engagement

Open source projects are critical infrastructure for:
- **Transparency Tools** - Code that powers government data platforms
- **Civic Tech Solutions** - Community-built tools for local engagement
- **Digital Public Goods** - Shared resources for common challenges
- **Collaboration Networks** - Where maintainers and contributors work together

**Mapping to Open Navigator Concepts:**
- **Repositories** → "Jurisdictions" (each repo is a community)
- **Maintainers/Contributors** → "Decision Makers" (people who merge PRs)
- **Issues/Pull Requests** → "Causes" (opportunities to contribute)
- **Sponsors/Funding** → "Financial Documents" (GitHub Sponsors, grants)

---

## 📦 Primary Data Source: GitHub

### GitHub REST API ⭐

**Source:** GitHub  
**URL:** https://docs.github.com/en/rest  
**Authentication:** Personal Access Token (free tier: 5,000 requests/hour)

**What It Provides:**
- Repository metadata (stars, forks, topics, languages)
- Issue and pull request data
- Contributor information and commit activity
- Organization/team structure
- Sponsorship information (via GraphQL)
- Release and version history

**Coverage:**
- ✅ **Volume:** Millions of public repositories
- ✅ **Free API:** 5,000 requests/hour with authentication
- ✅ **Rich Metadata:** Topics, tags, descriptions
- ✅ **Community Metrics:** Stars, forks, contributors

---

## 🏛️ Curated Civic Tech Repository Lists

### 1. Code for America Brigade Projects

**Source:** Code for America  
**URL:** https://brigade.codeforamerica.org/  
**GitHub:** https://github.com/codeforamerica

**Focus:** Civic technology projects from local brigades

**Notable Projects by Category:**

**Housing:**
- **housing-data-hub** - Centralized housing data platform
- **affordable-housing-finder** - Search tool for affordable units
- **eviction-tracker** - Monitor eviction filings and trends

**Transport:**
- **transitland** - Open transit data aggregator
- **OpenTripPlanner** - Multi-modal trip planning
- **shared-mobility-metrics** - Bike/scooter share analytics

**Budget:**
- **openbudgetoakland** - Oakland's budget visualization
- **budget-visualizations** - Interactive budget explorers
- **participatory-budgeting** - Community budget voting tools

**Health:**
- **health-equity-tracker** - Health outcome disparities
- **food-oasis** - Food access mapping
- **vaccine-finder** - Vaccination location search

---

### 2. U.S. Digital Response

**Source:** U.S. Digital Response  
**URL:** https://www.usdigitalresponse.org/  
**GitHub:** https://github.com/usdigitalresponse

**Focus:** Rapid-response civic tech for government needs

**Key Projects:**
- **unemployment-insurance-modernization** - UI claim processing
- **covid-digital-communication** - Public health messaging
- **grants-ingest** - Grant opportunity aggregation

---

### 3. Civic Tech Field Guide

**Source:** Civic Tech Field Guide  
**URL:** https://civictech.guide/  
**GitHub:** https://github.com/compilerla/civic-tech-taxonomy

**What It Provides:**
- Taxonomy of civic tech projects (~1,000+ catalogued)
- Categorization by issue area (housing, health, etc.)
- Project status and sustainability indicators
- Links to repositories and live sites

---

### 4. Digital Public Goods Alliance

**Source:** Digital Public Goods Alliance  
**URL:** https://digitalpublicgoods.net/  
**Registry:** https://github.com/DPGAlliance/DPG-Standard

**Focus:** Open source projects meeting DPG standard

**Relevant Projects:**
- **OpenStreetMap** - Community mapping infrastructure
- **DHIS2** - Health information system
- **Open Food Network** - Food supply chain platform

---

## 🔍 GitHub Topic-Based Discovery

Use GitHub's topic search to find civic projects:

### Housing & Community Development
```
topic:affordable-housing
topic:housing-data
topic:community-land-trust
topic:gentrification
topic:rent-control
```

### Transportation & Mobility
```
topic:transit-data
topic:gtfs
topic:bike-share
topic:mobility-data
topic:traffic-analysis
```

### Budget & Finance
```
topic:open-budget
topic:participatory-budgeting
topic:government-spending
topic:financial-transparency
```

### Health & Equity
```
topic:health-equity
topic:food-access
topic:covid-data
topic:health-outcomes
```

### People & Governance
```
topic:civic-engagement
topic:election-data
topic:voter-registration
topic:campaign-finance
topic:government-accountability
```

---

## 📊 Data Collection Strategy

### Step 1: Curated Lists (High Quality)
**Sources:**
- Code for America brigade index
- U.S. Digital Response portfolio
- Civic Tech Field Guide registry
- Digital Public Goods catalog

**Method:**
```python
# Ingest curated project lists
from discovery.github_civic_projects import CivicTechIngestion

civic = CivicTechIngestion()
repos = await civic.ingest_curated_lists([
    'codeforamerica',
    'usdigitalresponse',
    'civic-tech-field-guide'
])
```

### Step 2: Topic-Based Discovery (Broader Coverage)
**Sources:**
- GitHub topic search API
- Repository recommendations
- Network analysis (forks, stars from civic repos)

**Method:**
```python
# Search by civic tech topics
topics = [
    'civic-tech',
    'open-government',
    'public-data',
    'community-organizing'
]

for topic in topics:
    repos = await github_api.search_repositories(
        query=f"topic:{topic}",
        sort='stars',
        order='desc'
    )
```

### Step 3: Metadata Enrichment
**Collect:**
- ✅ Repository description and README
- ✅ Primary language and tech stack
- ✅ Active contributors and maintainers
- ✅ Open issues (potential "causes")
- ✅ Sponsorship/funding information
- ✅ License type (must be open source)

---

## 🎯 Integration with Open Navigator

### People Finder
**Add maintainers and core contributors:**
- Name and GitHub profile
- Role: "Open Source Maintainer" or "Core Contributor"
- Organization: Repository name
- Contact: GitHub username, email (if public)

**Example:**
```
Name: Jane Developer
Role: Core Maintainer
Organization: openbudgetoakland/openbudget
Contact: @janedev on GitHub
```

### Causes
**Map GitHub issues to advocacy opportunities:**
- Issue title → Cause name
- Labels → Topic tags
- "good first issue" → Entry-level causes
- Issue comments → Community engagement level

**Example:**
```
Cause: Add Spanish translation to budget tool
Repository: openbudgetoakland/openbudget
Urgency: Medium (15 community reactions)
How to Help: PR accepted, translation guide provided
```

### Budget/Funding
**Track project sustainability:**
- GitHub Sponsors monthly revenue
- Grant funding (from README or website)
- OpenCollective/Patreon backing
- Corporate sponsorships

---

## 🔗 Reference APIs

### GitHub REST API
**Documentation:** https://docs.github.com/en/rest  
**Rate Limits:** 5,000/hour (authenticated)  
**Key Endpoints:**
- `GET /repos/{{owner}}/{{repo}}` - Repository metadata
- `GET /repos/{{owner}}/{{repo}}/issues` - Issues and PRs
- `GET /repos/{{owner}}/{{repo}}/contributors` - Contributors
- `GET /orgs/{{org}}/repos` - Organization repositories

### GitHub GraphQL API
**Documentation:** https://docs.github.com/en/graphql  
**Use Cases:**
- Sponsorship data
- Complex queries (fewer API calls)
- Repository network analysis

### Civic Tech Registries
- **Civic Tech Field Guide API:** (planned, currently CSV export)
- **DPG Registry:** JSON files on GitHub
- **Code for America Index:** Web scraping + API (unofficial)

---

## 📈 Integration Roadmap

### Phase 1: ✅ **Documentation**
- Document open source as a data source
- Define mapping to existing concepts
- List curated civic tech projects

### Phase 2: 🔄 **Proof of Concept**
- Ingest 50-100 curated civic tech repos
- Display in "People Finder" (maintainers)
- Show in "Causes" (good first issues)

### Phase 3: 📋 **Full Integration**
- GitHub API integration module
- Automated topic-based discovery
- Funding/sponsorship tracking
- Contribution opportunity matching

### Phase 4: 🔮 **Advanced Features**
- Recommend repos based on user interests
- Track project health metrics
- Connect contributors with causes
- Cross-reference: "This nonprofit uses this open source tool"

---

## 🎯 Example Use Cases

### For Civic Hackers:
> "I want to contribute to budget transparency. Show me open source projects I can help with."

**Result:** List of budget-related repos with "good first issue" tags

### For Nonprofits:
> "Are there open source tools that can help us track housing data?"

**Result:** Housing-focused civic tech projects with demos and docs

### For Advocates:
> "Who maintains the eviction tracking tool? I want to suggest a feature."

**Result:** Maintainer contact info + open issues they're prioritizing

### For Funders:
> "Which civic tech projects need financial support?"

**Result:** Projects with active GitHub Sponsors or OpenCollective

---

## ✅ Data Quality & Updates

- **Repository metadata:** Updated via GitHub API (real-time)
- **Curated lists:** Refreshed monthly (Code for America, USDR)
- **Topic discovery:** Quarterly scans for new projects
- **Contribution data:** Weekly refresh (issues, PRs, commits)

All data sources listed are **free and publicly accessible**. GitHub API requires authentication (free) for higher rate limits.

---

## 📞 Contact & Support

**GitHub API Support:**  
- Documentation: https://docs.github.com/en/rest/support

**Civic Tech Communities:**  
- Code for America: https://brigade.codeforamerica.org/
- Civic Tech Chat: https://civictech.chat/
- U.S. Digital Response: https://www.usdigitalresponse.org/

**Registry Maintainers:**  
- Civic Tech Field Guide: https://civictech.guide/
- Digital Public Goods: https://digitalpublicgoods.net/
