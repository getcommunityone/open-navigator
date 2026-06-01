# Citations and Acknowledgments

This project uses several open datasets and research contributions. Please cite the following works when using or referencing this project.

## 📚 **Datasets**

### **MeetingBank Dataset**

We use the MeetingBank benchmark dataset for meeting summarization and analysis.

**Citation:**
```
Yebowen Hu, Tim Ganter, Hanieh Deilamsalehy, Franck Dernoncourt, Hassan Foroosh, Fei Liu.
"MeetingBank: A Benchmark Dataset for Meeting Summarization"
In Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL),
July 2023, Toronto, Canada.
```

**BibTeX:**
```bibtex
@inproceedings{hu-etal-2023-meetingbank,
    title = "MeetingBank: A Benchmark Dataset for Meeting Summarization",
    author = "Yebowen Hu and Tim Ganter and Hanieh Deilamsalehy and Franck Dernoncourt and Hassan Foroosh and Fei Liu",
    booktitle = "Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL)",
    month = July,
    year = "2023",
    address = "Toronto, Canada",
    publisher = "Association for Computational Linguistics",
}
```

**Resources:**
- Paper: https://arxiv.org/abs/2305.17529
- Dataset: https://huggingface.co/datasets/huuuyeah/meetingbank
- Zenodo: https://zenodo.org/record/7989108

**What we use:**
- 1,366 city council meetings from 6 U.S. cities
- Meeting transcripts and summaries
- Used for: Meeting discovery, transcript analysis, summarization benchmarking

---

### **CivicSearch (School Board Meeting Platform)**

We use CivicSearch's aggregated school board meeting transcripts, agendas, and videos for tracking education policy and local governance.

**Organization:** Datamuse, Inc.

**BibTeX:**
```bibtex
@misc{civicsearch_datamuse,
  author = {{Datamuse, Inc.}},
  title = {CivicSearch: School Board Meeting Platform},
  year = {2026},
  url = {https://schools.civicsearch.org/},
  note = {AI-indexed school board meeting transcripts and agendas}
}
```

**Resources:**
- Website: https://schools.civicsearch.org/
- Example: https://schools.civicsearch.org/tuscaloosa-city-alabama

**Attribution:**
```
Data source: CivicSearch (Datamuse, Inc.)
https://schools.civicsearch.org/
School board meeting transcripts and agendas
```

**What we use:**
- School board meeting transcripts (AI-indexed), agendas, and minutes
- Meeting videos and dates across school districts nationwide
- Used for: Education policy tracking, school board decision analysis, community engagement

**License:** Free public access for search; bulk/API access requires case-by-case approval. No automated scraping — use the official API where available and attribute back to CivicSearch.

---

### **LocalView Dataset (Harvard Dataverse)**

We use the LocalView dataset of municipal meeting videos and automated transcripts for large-scale civic data analysis.

**Organization:** Harvard University Mellon Urbanism Lab

**BibTeX:**
```bibtex
@dataset{localview_2024,
  author = {{Harvard Mellon Urbanism Lab}},
  title = {LocalView: Municipal Meeting Videos and Transcripts},
  year = {2024},
  publisher = {Harvard Dataverse},
  doi = {10.7910/DVN/NJTBEM},
  url = {https://www.localview.net/}
}
```

**Resources:**
- Website: https://www.localview.net/
- Dataverse: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM
- GitHub: https://mellonurbanism.harvard.edu/localview

**What we use:**
- 1,000+ municipalities with meeting videos (YouTube URLs) and automated transcripts
- Metadata (meeting dates, agencies, agendas) and per-jurisdiction quality tracking
- Used for: Large-scale civic data analysis and meeting discovery

**License:** Research use (Harvard Dataverse).

---

### **Datamuse API (Word-Finding Engine)**

We use the Datamuse API for natural-language tooling — word associations, semantic search, and text analysis over meeting transcripts and policy documents.

**Organization:** Datamuse, Inc.

**BibTeX:**
```bibtex
@misc{datamuse_api,
  author = {{Datamuse, Inc.}},
  title = {Datamuse API: Word-Finding Query Engine},
  year = {2026},
  url = {https://www.datamuse.com/api/},
  note = {Free tier: 100,000 requests/day. Commercial use allowed.}
}
```

**Resources:**
- API Documentation: https://www.datamuse.com/api/
- Developer Site: https://www.datamuse.com/

**Attribution:**
```
Powered by Datamuse API
https://www.datamuse.com/api/
```

**What we use:**
- `/words` and `/sug` endpoints for synonyms, related terms, and autocomplete
- Used for: Search enhancement, topic modeling, and transcript text analysis

**License:** Free tier (100,000 requests/day, commercial use allowed, no API key); paid tier for high-volume use. Caching allowed; no scraping of the web interface. Note: Datamuse.ai is a separate SaaS product with its own pricing.

---

## 🗂️ **Other Data Sources**

### **U.S. Census Bureau**
- Geographic boundaries and demographic data
- Source: https://www.census.gov/
- License: Public Domain (U.S. Government)

### **OpenAddresses Project** ⭐
- Crowdsourced, developer-focused index of the exact URLs, API endpoints, and FTP servers where local governments host public address, parcel, and appraisal data — structured as raw JSON/YAML source files rather than a clickable UI.
- Site: https://openaddresses.io/
- Repository: https://github.com/openaddresses/openaddresses
- Data layout: per-country / per-state / per-county source files under `sources/` describing the upstream URL, format (Shapefile, CSV, GeoJSON, ArcGIS REST), licensing, and conform/transform rules.
- License: BSD-3-Clause for the code; per-source licenses (mostly public-domain or open) declared in each YAML file.
- Coverage: 1,000+ jurisdictions across the U.S. (county GIS / assessor systems) and many other countries.
- Used for: discovering the canonical upstream data URLs for county and city parcel / address systems; complements CISA `.gov` and Census GID by providing the actual *data endpoint* (not just the website).
- **Use:** Cite the project repository and the specific source file(s) you consume (e.g. `sources/us/al/jefferson.json`).

### **Opportunity Insights** (reference)
- Non-partisan research on economic mobility, neighborhoods, and education; public tools such as the Opportunity Atlas ([https://opportunityinsights.org/](https://opportunityinsights.org/))
- **Use:** Cite their papers, datasets, or tool pages directly when you use their materials; see [website/docs/data-sources/citations.md](website/docs/data-sources/citations.md#opportunity-insights)

### **PolicyMap** (reference)
- Commercial platform for U.S. community mapping, analytics, and licensed socio-economic data ([https://www.policymap.com/](https://www.policymap.com/))
- **Use:** Follow PolicyMap’s **Citing Us** / terms when you use their data or maps; see [website/docs/data-sources/citations.md](website/docs/data-sources/citations.md#policymap)

### **Reason Foundation** (reference)
- Nonprofit policy research organization ([https://reason.org/](https://reason.org/)); transportation, infrastructure, and governance are among its topic areas (for example the Annual Highway Report and related publications).
- **Use:** Cite specific Reason reports or pages when you use their materials; see [website/docs/data-sources/citations.md](website/docs/data-sources/citations.md#reason-foundation)

### **State Symbols USA** (reference)
- Curated state colors and civic identity reference material (third-party educational site, not a government primary source)
- Colors category: https://statesymbolsusa.org/categories/colors
- Site: https://statesymbolsusa.org/
- **Use:** Reference and attribution only; site content is copyrighted—link to the live site in published materials.
- **Local asset mirror (flags + license plates):** `scripts/wikicommons/download_wikicommons_assets.sh` pulls **Wikimedia Commons** SVG state flags and U.S. license-plate imagery into `data/cache/wikicommons/` (see [website/docs/data-sources/citations.md](website/docs/data-sources/citations.md#wikimedia-commons-reference-assets)).

### **Open States / Plural Policy** ⭐
- Comprehensive state and local legislative information
- Organization: Plural Policy (formerly Open States Foundation)
- Source: https://openstates.org/
- API: https://openstates.org/api/
- Data Downloads: https://open.pluralpolicy.com/data/
- License: Various (check per state)
- API Key: Required for access (free tier: 50,000 requests/month)

**Coverage:**
- All 50 states + DC + Puerto Rico
- 7,300+ state legislators
- Millions of bills, votes, and legislative sessions
- Monthly PostgreSQL database dumps (9.8GB+)

**What we use:**
- Bulk legislative session downloads (CSV/JSON/PostgreSQL)
- State legislator data with committee assignments
- Bill tracking and voting records
- Legislative video sources (YouTube channels, Granicus portals)

**Resources:**
- Open Data: https://open.pluralpolicy.com/data/
- Scrapers Repository: https://github.com/openstates/openstates-scrapers
- Local Database Setup: https://docs.openstates.org/contributing/local-database/
- Code of Conduct: https://docs.openstates.org/code-of-conduct/
- Schema Documentation: https://github.com/openstates/people/blob/master/schema.md

**BibTeX:**
```bibtex
@software{openstates,
    title = {Open States},
    author = {{Plural Policy}},
    year = {2024},
    url = {https://openstates.org/},
    note = {Comprehensive state legislative data for all 50 U.S. states}
}
```

**Potential Contributions:**
- Our scraper patterns could be contributed to openstates-scrapers
- Video source discovery could enhance their data
- We follow their Code of Conduct for all contributions

**State-Specific Scraper Requirements:**

Some states require special setup or API credentials to access their legislative data. Below are the documented requirements:

**California (MySQL Database):**
- California provides MySQL dumps of their legislative data
- Requires local MySQL instance to read data
- Setup process:
  ```bash
  # Download data for current session
  docker-compose run --rm ca-download
  
  # Or download specific year
  docker-compose run --rm ca-download --year YYYY
  
  # Run scraper (MySQL container must be running)
  docker-compose run --rm ca-scrape ca bills --fast
  ```
- Documentation: https://docs.openstates.org/contributing/scrapers/

**New York (API Key Required):**
- API Documentation: http://legislation.nysenate.gov/static/docs/html/index.html
- Request Form: http://legislation.nysenate.gov/
- Environment Variable: `NEW_YORK_API_KEY`
- Usage: Set environment variable before running scrape

**Indiana (API Key Required):**
- API Documentation: http://docs.api.iga.in.gov/api.html
- Terms of Service: https://docs.api.iga.in.gov/usage.html
- Request Process: Email Office of Technology Services Team (apitoken.request@iga.in.gov)
  - Include: Name, address, phone, email, company name
  - Confirm you have read the terms of service
- Environment Variables:
  - `INDIANA_API_KEY`: API token from IGA
  - `USER_AGENT`: User agent string (required by Indiana)

**Virginia (FTP Credentials Required):**
- FTP Documentation: https://lis.virginia.gov/SiteInformation/ftp.html
- Request Process: Contact Virginia Legislative Information System help desk at (804) 786-9631
- Environment Variables:
  - `VIRGINIA_FTP_USER`: FTP username
  - `VIRGINIA_FTP_PASSWORD`: FTP password

**District of Columbia (API Key Required):**
- API Documentation: https://lims.dccouncil.us/api/help/index.html
- Request Form: https://lims.dccouncil.us/developerRegistration
- Environment Variable: `DC_API_KEY`

**Open States Credential Policy:**
- Two sets of credentials maintained (development and production) when possible
- Developers encouraged to obtain their own API keys
- Test credentials available in limited circumstances for contributors
- Helps ensure best possible data quality despite access barriers

### **LegiScan** ⭐
- Comprehensive legislative tracking and bill text database
- Organization: LegiScan LLC
- Source: https://legiscan.com/
- API: https://legiscan.com/legiscan
- License: API access requires subscription (free tier available with limitations)
- Coverage: All 50 states + U.S. Congress + Washington D.C.
- API Key: Required for access (free tier: limited requests)

**Coverage:**
- Real-time legislative tracking for all U.S. states and Congress
- Full bill text, amendments, and legislative documents
- Roll call votes and voting records
- Committee assignments and hearings
- Bill status tracking and history
- Sponsor and co-sponsor information
- Bill text in PDF, HTML, and plain text formats

**What we use:**
- Bill text downloads and full-text search
- Legislative document archives
- Bill status and tracking data
- Voting records and roll calls
- Supplement to Open States data for missing jurisdictions
- Historical legislative data back to 2011

**API Features:**
- GetBillText: Retrieve full bill text in multiple formats
- GetBill: Detailed bill metadata and status
- GetRollCall: Voting records with legislator positions
- GetSponsor: Sponsor and co-sponsor information
- Search: Full-text search across all bills
- GetDatasetList: Bulk dataset downloads

**Resources:**
- API Documentation: https://legiscan.com/legiscan
- Dataset Downloads: https://legiscan.com/datasets
- Search Interface: https://legiscan.com/gaits/search
- State Coverage: https://legiscan.com/legiscan/states

**BibTeX:**
```bibtex
@software{legiscan,
    title = {LegiScan},
    author = {{LegiScan LLC}},
    year = {2024},
    url = {https://legiscan.com/},
    note = {Comprehensive legislative tracking and bill text database covering all 50 U.S. states and Congress}
}
```

**Complementary to Open States:**
- LegiScan provides bill text in multiple formats (PDF, HTML, plain text)
- Historical data back to 2011 for all states
- Real-time updates and notifications
- More comprehensive document archives
- Paid API provides higher rate limits and bulk downloads
- Use LegiScan for bill text analysis, Open States for structured legislative data

### **GovTrack.us** ⭐
- Congressional bill tracking, categorization, and civic engagement platform
- Organization: Civic Impulse LLC
- Source: https://www.govtrack.us/
- API: https://www.govtrack.us/developers/api
- GitHub: https://github.com/govtrack/govtrack.us-web
- License: Open data (public domain for U.S. government data); code is open source
- Coverage: U.S. Congress (House and Senate)

**Coverage:**
- All congressional bills since 1973
- Bill text, status tracking, and legislative history
- Congressional voting records
- Legislator information and committee assignments
- Bill categorization and topic classification (20+ policy areas)
- Bill summaries and plain-language explanations

**What we use:**
- Bill topic classification methodology (inspiration for state-level topic extraction)
- Congressional bill categorization approach (health, education, defense, etc.)
- Legislative data analysis patterns
- Bill similarity and tracking techniques

**Features:**
- Automatic bill categorization into policy areas
- Plain-language bill summaries
- Legislator voting records and analysis
- Committee tracking and hearing schedules
- Email alerts for bill tracking
- Open data downloads (JSON, XML, CSV)

**Resources:**
- Website: https://www.govtrack.us/
- API Documentation: https://www.govtrack.us/developers/api
- Data Downloads: https://www.govtrack.us/developers/data
- GitHub Repository: https://github.com/govtrack/govtrack.us-web
- Blog: https://govtrackinsider.com/

**BibTeX:**
```bibtex
@software{govtrack,
    title = {GovTrack.us},
    author = {{Civic Impulse LLC}},
    year = {2024},
    url = {https://www.govtrack.us/},
    note = {Congressional bill tracking and civic engagement platform with automatic topic categorization and legislative analysis}
}
```

**Relevance to Open Navigator:**
- Their bill categorization methodology informs our state-level topic extraction
- Proven approach to making complex legislation accessible
- Open source codebase provides technical patterns for legislative data processing
- Topic taxonomy (health, education, infrastructure, etc.) adapted for state bills

### **Harvard Dataverse**
- Meeting datasets and civic engagement research
- Source: https://dataverse.harvard.edu/
- License: Varies by dataset

### **City Scrapers** ⭐
- Open source civic tech project for scraping local government meetings
- Organization: Documenters.org / City Bureau
- Source: https://cityscrapers.org/
- GitHub: https://github.com/city-scrapers
- License: MIT License (open source)
- Coverage: Chicago, Pittsburgh, Detroit, Cleveland, Los Angeles (250+ government agencies)
- What we use: Validated meeting URLs, Legistar/Granicus platform endpoints, spider code for scraper patterns
- Used for: Meeting discovery, URL extraction, platform detection, scraper validation

**City Scrapers Repositories:**
- Chicago: https://github.com/city-scrapers/city-scrapers (~100 agencies)
- Pittsburgh: https://github.com/city-scrapers/city-scrapers-pitt (~30 agencies)
- Detroit: https://github.com/city-scrapers/city-scrapers-detroit (~40 agencies)
- Cleveland: https://github.com/city-scrapers/city-scrapers-cle (~30 agencies)
- Los Angeles: https://github.com/city-scrapers/city-scrapers-la (~50 agencies)

**BibTeX:**
```bibtex
@software{city_scrapers,
    title = {City Scrapers},
    author = {{Documenters.org}},
    year = {2024},
    url = {https://cityscrapers.org/},
    note = {Open source civic tech project providing validated scrapers for local government meetings across major U.S. cities}
}
```

### **Google Civic Information API** ⭐
- Government officials, polling locations, and election data
- Organization: Google LLC
- API Documentation: https://developers.google.com/civic-information
- License: Free (with quota limits)
- Rate Limit: 25,000 requests/day (free tier)
- Coverage: U.S. federal, state, and local government officials; polling locations; election data
- What we use: Elected officials by address, representative contact info, voting districts
- Used for: Contact discovery, official verification, civic engagement tools

**API Endpoints Used:**
- Representatives by Address: Get all elected officials for a given address
- Elections: Voter information, polling locations, ballot information
- Divisions: Geographic/political divisions (OCD-IDs)

**BibTeX:**
```bibtex
@misc{google_civic_api,
    title = {Google Civic Information API},
    author = {{Google LLC}},
    year = {2024},
    url = {https://developers.google.com/civic-information},
    note = {API providing government official contact information, election data, and polling locations}
}
```

**Terms of Service:**
- Attribution required when displaying official data
- Caching limited to 30 days
- Must comply with Google API Terms of Service

### **YouTube Data API v3** ⭐
- Video metadata, channel information, and search for government meetings
- Organization: Google LLC
- API Documentation: https://developers.google.com/youtube/v3
- License: Free (with quota limits)
- Rate Limit: 10,000 units/day (free tier), search costs 100 units per request
- Coverage: Global video platform with millions of government channels
- What we use: Government channel discovery, meeting video metadata, transcript availability
- Used for: Video discovery, channel statistics, meeting video archival

**API Features Used:**
- Search: Find government channels by jurisdiction name
- Channels: Get channel metadata, subscriber counts, video counts
- Videos: Metadata including title, description, upload date, duration
- Captions: Check for closed caption/transcript availability

**BibTeX:**
```bibtex
@misc{youtube_data_api,
    title = {YouTube Data API v3},
    author = {{Google LLC}},
    year = {2024},
    url = {https://developers.google.com/youtube/v3},
    note = {API for accessing YouTube video metadata, channel information, and search functionality}
}
```

**Terms of Service:**
- YouTube API Services Terms: https://developers.google.com/youtube/terms/api-services-terms-of-service
- Attribution required with YouTube logo
- Quota limits enforced (10,000 units/day free)
- Video embeds must use official YouTube player

### **Ballotpedia** ⭐
- Ballot measures, referendums, and propositions
- Organization: Lucy Burns Institute
- Source: https://ballotpedia.org/
- API: https://ballotpedia.org/API-documentation
- License: API access is limited at scale (paid tier available)
- Coverage: All 50 states, historical measures back to 1990s
- Used for: Tracking fluoridation votes, school bond measures, health policy propositions

**Our implementation:**
- Scraper core: [scripts/datasources/ballotpedia/ballotpedia_integration.py](scripts/datasources/ballotpedia/ballotpedia_integration.py) — httpx with Playwright fallback; jurisdiction and state ballot-measure page parsers.
- Downloader: [scripts/datasources/ballotpedia/download_ballotpedia_measures.py](scripts/datasources/ballotpedia/download_ballotpedia_measures.py) — bulk-scrapes state and local ballot-measure pages into `data/cache/ballotpedia/`.
- Bronze schema: [packages/hosting/scripts/neon/migrations/057_create_bronze_ballot_measures_ballotpedia.sql](packages/hosting/scripts/neon/migrations/057_create_bronze_ballot_measures_ballotpedia.sql) — NIST-aligned `bronze.bronze_ballot_measures_ballotpedia`.
- Loader: [scripts/datasources/ballotpedia/load_ballotpedia_measures_to_bronze.py](scripts/datasources/ballotpedia/load_ballotpedia_measures_to_bronze.py) — maps cache JSON into bronze, resolves `ocd_division_id`.
- External links bronze: [packages/hosting/scripts/neon/migrations/055_bronze_websites_ballotpedia.sql](packages/hosting/scripts/neon/migrations/055_bronze_websites_ballotpedia.sql) — outbound links from Ballotpedia article pages (`bronze.bronze_websites_ballotpedia`).
- dbt: [dbt_project/models/bronze/bronze_ballot_measures_nist.sql](dbt_project/models/bronze/bronze_ballot_measures_nist.sql) unions Ballotpedia measures with VIP and AI-extracted sources.

### **Power BI Ballot Measures Dashboard** (public embed)
- Public Power BI report aggregating U.S. state and local ballot measures — headline KPI lists **9,670 ballot measures** (card visual); our table scrape loaded **10,000** paginated rows (2026-05-24) because the table grain includes multiple topic tags per measure. We treat ±5% vs the KPI as a pass for pipeline checks.
- Embed URL: https://app.powerbi.com/view?r=eyJrIjoiYjEwNDI2NTctZDFkMy00ZGM4LWFkMTItNTcwYTdkZmMxMGIxIiwidCI6IjM4MmZiOGIwLTRkYzMtNDEwNy04MGJkLTM1OTViMjQzMmZhZSIsImMiOjZ9
- Power BI resource key: `b1042657-d1d3-4dc8-ad12-570a7dfc10b1` (tenant `382fb8b0-4dc3-4107-80bd-3595b2432fae`, cluster 6).
- Publisher / data steward: not named on the public embed. The semantic model uses an **“All Years Table”** entity (state, year, title, measure type, topic, election, pass/fail, vote share). Treat as third-party civic data until the link source confirms attribution; update this entry when the steward is known.
- License: not stated on the embed. Treat as the publisher's intellectual property; we only retain the scraped CSV under `data/cache/ncls/` for derivative analytics, not redistribution.
- Used for: cross-referencing third-party ballot-measure aggregates against our own bronze tables (`bronze.bronze_elections_scraped`, `bronze.bronze_ballot_measures_nist`) and as a count-of-record sanity check.

**Our implementation:**
- Scraper: [scripts/datasources/powerbi_ballot_measures/download_powerbi_ballot_measures.py](scripts/datasources/powerbi_ballot_measures/download_powerbi_ballot_measures.py) — Playwright opens the embed, intercepts every `/public/reports/querydata` XHR, decodes the Power BI DSR (DataShape Result) payload into a CSV, and asserts the row count matches the dashboard KPI (default `--expected-count 9670`).
- Bronze schema: [packages/hosting/scripts/neon/migrations/056_create_bronze_ballot_measures_powerbi.sql](packages/hosting/scripts/neon/migrations/056_create_bronze_ballot_measures_powerbi.sql).
- Loader: [scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py](scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py) — maps scraped columns into denormalized bronze columns, stores the original row as JSONB, and re-verifies post-load count against the same 9,670 KPI.

### **NIST SP 1500-100 — Election Results Reporting Common Data Format (ERR-CDF) / NIST VIP** ⭐
- Formal, gold-standard schema for U.S. election-day data: contests, candidates, ballot measures, precincts, and results
- Organization: National Institute of Standards and Technology (NIST), in collaboration with the Voting Information Project (VIP) and the Election Assistance Commission (EAC)
- Specification (current revision): https://www.nist.gov/itl/voting/interoperability
- Publication landing page: https://csrc.nist.gov/publications/detail/sp/1500-100/final
- Election Results Reporting CDF (SP 1500-100): https://pages.nist.gov/ElectionResultsReporting/
- Schema source (XML/JSON/UML, machine-readable): https://github.com/usnistgov/ElectionResultsReporting
- Voting Information Project (VIP) feeds (consumer of CDF): https://www.votinginfoproject.org/
- License: Public Domain (U.S. Government work)
- Coverage: Federal, state, and local election data — designed for full election-night reporting and pre-election ballot publication
- Used for: Modeling ballot measures (initiatives, referenda, recalls, bond measures), contests, and selections in a vendor-neutral way that joins cleanly to OCD Division IDs

**Why this schema (vs. OCD or Popolo):**
- Unlike the Open Civic Data (OCD) specification — which targets legislative tracking (bills, votes, legislators) — and unlike Popolo (people and organizations), NIST SP 1500-100 explicitly defines an entire **election-day** schema with first-class classes for ballot measures and contests.
- Featured classes used in our bronze + public schemas:
  - `BallotMeasureContest` — the contest wrapper for an initiative, referendum, or bond
  - `BallotMeasureSelection` — the valid voter choices (typically "Yes" / "No")
  - `BallotMeasureType` — enumeration distinguishing `initiative`, `referendum`, `recall`, `other`
  - `Election`, `ElectionAdministration`, `GpUnit` (Geo-Political Unit) — election + jurisdiction container, joined to OCD Division IDs via `ExternalIdentifier`
  - `ContestResults`, `BallotMeasureSelectionResults` — vote totals when results are available
- `GpUnit.ExternalIdentifier` allows direct linkage to `ocd-division/country:us/...` IDs, so our NIST-shaped ballot tables join to OCD-keyed jurisdiction tables without lossy crosswalks.

**Companion VIP specification:**
- VIP CDF (NIST SP 1500-101): pre-election ballot information (polling places, contests, candidates, ballot measures) — same modeling primitives as SP 1500-100, scoped to *before* the election.
- VIP spec: https://vip-specification.readthedocs.io/

**Our implementation:**
- Bronze layer: `dbt_project/models/bronze/bronze_ballot_measures_nist.sql` — landing zone preserving raw NIST `BallotMeasureContest` / `BallotMeasureSelection` shapes from upstream feeds (Ballotpedia, VIP, state SoS XML).
- Public layer: `dbt_project/models/marts/ballot_measures.sql` — analyst-ready table keyed by `ocd_division_id`, with `ballot_measure_type` enum aligned to NIST `BallotMeasureType`.

**BibTeX:**
```bibtex
@techreport{nist_sp1500_100,
    title       = {Election Results Reporting Common Data Format Specification},
    author      = {Wack, John and Kiniry, Joseph and Frincke, Deborah and {National Institute of Standards and Technology}},
    institution = {National Institute of Standards and Technology},
    number      = {NIST Special Publication 1500-100},
    year        = {2019},
    url         = {https://pages.nist.gov/ElectionResultsReporting/},
    note        = {U.S. Government work; public domain. Defines BallotMeasureContest, BallotMeasureSelection, and BallotMeasureType classes used for election-day reporting.}
}

@techreport{nist_sp1500_101_vip,
    title       = {Voting Information Project Common Data Format Specification},
    author      = {{National Institute of Standards and Technology} and {Voting Information Project}},
    institution = {National Institute of Standards and Technology},
    number      = {NIST Special Publication 1500-101},
    year        = {2019},
    url         = {https://vip-specification.readthedocs.io/},
    note        = {Pre-election ballot information CDF; companion to SP 1500-100.}
}
```

**Attribution:** Cite as "National Institute of Standards and Technology, *Election Results Reporting Common Data Format Specification*, NIST SP 1500-100. https://pages.nist.gov/ElectionResultsReporting/".

### **MIT Election Data + Science Lab**
- Presidential, Congressional, and gubernatorial election results
- Organization: Massachusetts Institute of Technology
- Source: https://electionlab.mit.edu/data
- Repository: https://github.com/MEDSL/official-returns
- License: Free for research and commercial use
- Coverage: 1976-present, county-level results
- Used for: Political composition analysis, jurisdiction context

### **OpenElections**
- State-by-state certified election results in standardized CSV format
- Source: https://openelections.net/
- GitHub: https://github.com/openelections
- License: Open source (various by state)
- Coverage: All 50 states (various completion levels), precinct-level data
- Used for: Detailed election results, local race outcomes, advocacy targeting

### **Open Civic Data (OCD) Standards**
- Division identifiers and civic data standards
- Specification: https://open-civic-data.readthedocs.io/en/latest/proposals/0002.html
- Repository: https://github.com/opencivicdata/ocd-division-ids
- License: Open source
- Used for: Standardized jurisdiction identifiers, cross-platform compatibility

### **Popolo Project**
- International open government data specification for people, organizations, and elected positions
- Specification: https://www.popoloproject.com/
- GitHub: https://github.com/popolo-project/popolo-spec
- Documentation: http://www.popoloproject.com/specs/
- License: Creative Commons Attribution 4.0 International

### **BillMap** ⭐
- Tracks bill text similarity across all 50 U.S. states to identify copy-paste legislation and model bill influence
- Organization: Sunlight Foundation / @unitedstates community
- Repository: https://github.com/unitedstates/BillMap
- Research: Anderson et al., "Detecting Policy Influence in Legislatures" (2019)
- Paper: https://arxiv.org/abs/1906.03699
- Live Demo: https://billmap.cs.princeton.edu/
- License: Open source
- Coverage: All 50 states, tracks legislative text diffusion across jurisdictions
- Used for: Identifying model legislation, tracking policy influence, finding similar bills across states
- Method: Text similarity analysis, n-gram matching, bill text alignment

**What we use:**
- Bill similarity detection algorithms
- Model legislation tracking methodology
- Cross-state policy diffusion analysis
- Legislative text comparison techniques

**BibTeX:**
```bibtex
@article{anderson2019billmap,
    title = {Detecting Policy Influence in Legislatures},
    author = {Anderson, Evan and Fowler, Anthony and Grossmann, Matt and Sahn, Alexander and Shiraito, Yuki},
    journal = {arXiv preprint arXiv:1906.03699},
    year = {2019},
    url = {https://arxiv.org/abs/1906.03699}
}
```

### **@unitedstates Images Repository** ⭐
- High-resolution photos of all U.S. Congress members (past and present)
- Organization: @unitedstates community (Sunlight Foundation legacy project)
- Repository: https://github.com/unitedstates/images
- CDN: https://theunitedstates.io/images/congress/
- License: Public domain (government photos)
- Coverage: All U.S. Senators and Representatives (1789-present), updated regularly
- Image Format: JPEG, multiple resolutions (original, 450x550, 225x275)
- Used for: Legislator profile photos, visual identification, representative directories

**Image URL Format:**
```
https://theunitedstates.io/images/congress/original/[bioguide_id].jpg
https://theunitedstates.io/images/congress/450x550/[bioguide_id].jpg
https://theunitedstates.io/images/congress/225x275/[bioguide_id].jpg
```

**Example:**
```
https://theunitedstates.io/images/congress/original/P000197.jpg
(Nancy Pelosi, bioguide_id: P000197)
```

**What we use:**
- Legislator profile photos for federal representatives
- Visual identification in advocacy tools
- Representative directories and contact pages
- Cross-referenced with Open States data using bioguide IDs

**Related Projects:**
- **congress-legislators**: https://github.com/unitedstates/congress-legislators (YAML data files)
- **congress**: https://github.com/unitedstates/congress (scraping tools)
- **districts**: https://github.com/unitedstates/districts (GeoJSON boundaries)

---

## 💰 **Nonprofit Financial Data**

### **GivingTuesday 990 Data Infrastructure** ⭐

We use the GivingTuesday 990 Data Lake for detailed nonprofit financial data from IRS Form 990 XML filings.

**Organization:** GivingTuesday  
**Website:** https://990data.givingtuesday.org/  
**Data Lake:** `s3://gt990datalake-rawdata` (AWS S3, us-east-1 Virginia, Public Access)  
**Console:** https://us-east-1.console.aws.amazon.com/s3/buckets/gt990datalake-rawdata  
**License:** Public domain (IRS data) + Open source tools  
**Access:** Free, no AWS credentials required (anonymous access via `--no-sign-request`)

**What we use:**
- **Raw 990 XMLs**: Individual e-filed Form 990 returns in XML format (1-2 MB each)
- **Indices**: CSV/Parquet files listing all available 990s with metadata
- **Coverage**: 5.4M+ e-filed Form 990s (2011-present, ~300K new filings/year)
- **Scale**: ~10 TB of raw XML data
- **Data extracted**: Revenue, expenses, assets, liabilities, grants, programs, officer compensation, mission statements, website URLs

**Data Lake Structure:**
```
s3://gt990datalake-rawdata/
├── EfileData/
│   ├── XmlFiles/              # Individual 990 XMLs (~5.4M files, ~10 TB)
│   │   └── [OBJECT_ID]_public.xml  (e.g., 202233259349300703_public.xml)
│   └── XmlZips/               # ZIP archives (97 files, ~38 GB → ~95 GB uncompressed)
│       └── YYYY_TEOS_XML_*.zip     (e.g., 2023_TEOS_XML_01A.zip ~400 MB)
└── Indices/
    └── 990xmls/               # CSV indices with metadata
        └── index_all_years_efiledata_xmls_created_on_2023-10-29.csv (~925 MB)
```

**Download Strategies:**

| Approach | Best For | Time | Bandwidth | Storage |
|----------|----------|------|-----------|---------|
| **Individual XMLs** | Single state or targeted download | ~2 hrs (22K orgs) | 32 GB | 32 GB |
| **ZIP Archives** | All states / nationwide | ~6 hrs total | 38 GB | 95 GB |

**Choose Individual XMLs when:**
- You need data for 1-5 states only
- You want to download only specific EINs
- Storage space is limited
- You want incremental caching (download as needed)

**Choose ZIP Archives when:**
- You need all 50 states
- You're building a comprehensive nonprofit database
- You have 100+ GB storage
- You want offline access to all filings

**S3 Access Examples:**

**Individual XMLs (for single state or targeted download):**
```bash
# List index files (no credentials needed)
aws s3 ls s3://gt990datalake-rawdata/Indices/990xmls/ --no-sign-request

# Download index (~925 MB)
aws s3 cp s3://gt990datalake-rawdata/Indices/990xmls/index_all_years_efiledata_xmls_created_on_2023-10-29.csv . --no-sign-request

# Download specific XML
aws s3 cp s3://gt990datalake-rawdata/EfileData/XmlFiles/202233259349300703_public.xml . --no-sign-request

# Batch download for single state (using our script)
python scripts/batch_download_990s.py --state MA --health-only --concurrent 1000
```

**ZIP Archives (for all states / nationwide):**
```bash
# Download all 97 ZIPs (~38 GB) to local directory
./scripts/download_990_zips.sh

# Extract all ZIPs to get ~384K XMLs (~95 GB)
./scripts/extract_990_zips.sh

# Build local index for fast lookup
python scripts/build_990_local_index.py

# Now enrich from local files (no network needed!)
python scripts/enrich_all_states_990.py
```

**Index Schema:**
The CSV index contains columns: `EIN`, `TaxPeriod`, `ObjectId`, `URL`, `FormType`, `OrganizationName`, `DLN`, `SubmittedOn`

**Python Access:**
```python
import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure anonymous S3 client
s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))

# Download XML
xml_obj = s3.get_object(
    Bucket='gt990datalake-rawdata',
    Key='EfileData/XmlFiles/202233259349300703_public.xml'
)
xml_content = xml_obj['Body'].read()
```

**BibTeX:**
```bibtex
@misc{givingtuesday990data,
    title = {GivingTuesday 990 Data Infrastructure},
    author = {{GivingTuesday}},
    year = {2023},
    url = {https://990data.givingtuesday.org/},
    note = {Collaborative data lake of standardized IRS Form 990 XML filings}
}
```

**Attribution:** When publishing analyses using this data, please cite both:
1. GivingTuesday 990 Data Infrastructure: https://990data.givingtuesday.org/
2. Our enrichment tools: https://github.com/getcommunityone/open-navigator-for-engagement

---

### **Google Cloud Public Datasets: IRS 990** ⭐

Google hosts the complete IRS Form 990 dataset in BigQuery for fast SQL-based querying.

**Platform:** Google Cloud BigQuery  
**Dataset:** `bigquery-public-data.irs_990`  
**Table:** `bigquery-public-data.irs_990.irs_990_xml`  
**Documentation:** https://console.cloud.google.com/marketplace/product/internal-revenue-service/irs-990  
**Cost:** First 1 TB of queries per month is **FREE**  
**Coverage:** All e-filed Form 990s (2011-present, 5M+ records)

**What we use:**
- **Mission statements**: Extracted from `return_header` or `part_i_mission_desc` fields
- **Website URLs**: Found in `website_address_txt` field
- **Financial data**: All Form 990 fields accessible via SQL
- **Fast bulk queries**: Extract data for 1M+ orgs in seconds (vs hours downloading XMLs)

**Advantages:**
- ✅ No local XML downloads needed
- ✅ Single SQL query to bulk-extract fields
- ✅ Serverless (no infrastructure to manage)
- ✅ Fast (queries complete in seconds)
- ✅ Free tier covers most research use cases

**Example Query:**
```sql
SELECT 
  ein,
  org_name,
  website_address_txt,
  part_i_mission_desc,
  total_revenue_current_year,
  total_expenses_current_year
FROM `bigquery-public-data.irs_990.irs_990_2023`
WHERE state = 'AL'
  AND ntee_code LIKE 'E%'
LIMIT 1000;
```

**BibTeX:**
```bibtex
@misc{googlecloud_irs990,
    title = {IRS 990 Public Dataset},
    author = {{Google Cloud Public Datasets}},
    year = {2024},
    publisher = {Google Cloud Platform},
    url = {https://console.cloud.google.com/marketplace/product/internal-revenue-service/irs-990},
    note = {BigQuery public dataset of IRS Form 990 e-file data}
}
```

**Attribution:** When using BigQuery 990 data, cite:
1. IRS 990 Public Dataset (Google Cloud)
2. Internal Revenue Service (original data source)

---

### **National Center for Charitable Statistics (NCCS) Unified BMF** ⭐

The NCCS Unified BMF is a longitudinal nonprofit dataset specifically designed for AI and "Lakehouse" projects with pre-geocoded locations and Census integration.

**Organization:** National Center for Charitable Statistics (NCCS), Urban Institute  
**Website:** https://nccs.urban.org/  
**Dataset:** Unified BMF (Business Master File)  
**Documentation:** https://nccs.urban.org/project/irs-exempt-organizations-business-master-file  
**License:** Public domain (IRS data) + Urban Institute terms  
**Released:** Late 2025/Early 2026  
**Coverage:** 1989 through mid-2025 (update pending)

**What we use:**
- **Longitudinal tracking**: Single file with one row per organization that has ever held tax-exempt status
- **Pre-geocoded addresses**: Most recent address geocoded to Census block level
- **Geographic codes**: FIPS codes at block, tract, county, and state levels
- **Metropolitan area codes**: Current CBSA (Core Based Statistical Area) definitions
- **Temporal tracking**: `ORG_YEAR_FIRST` and `ORG_YEAR_LAST` variables for organization lifecycle
- **Census integration**: Ready for merging with Census demographic and economic data

**Key Features:**
- ✅ **Eliminates annual file merging**: Consolidates all historical BMF releases into single file
- ✅ **AI/Lakehouse optimized**: Designed for modern data infrastructure
- ✅ **Census-ready**: FIPS codes enable direct joins with Census data
- ✅ **Metropolitan vs Rural**: CBSA codes identify urban/rural areas
- ✅ **Historical analysis**: Track organizations over time without complex ETL
- ✅ **Geographic analysis**: Pre-geocoded to Census block granularity

**Use Cases:**
- Longitudinal analysis of nonprofit sector
- Building historical sampling frames
- Linking nonprofit data to Census demographics
- Metropolitan vs rural nonprofit analysis
- Policy research requiring geographic precision
- Time-series analysis of organizational entry/exit

**Geographic Levels Available:**
- Census Block (finest granularity)
- Census Tract
- County (FIPS codes)
- State (FIPS codes)
- CBSA (Core Based Statistical Area)

**Related Resources:**
- NCCS Census Crosswalk: For aggregating to additional geographic levels
- BMF Overview: https://nccs.urban.org/project/irs-exempt-organizations-business-master-file
- NCCS Data Archive: https://nccs.urban.org/nccs-data-archive

**BibTeX:**
```bibtex
@dataset{nccs_unified_bmf,
    title = {Unified Business Master File (BMF)},
    author = {{National Center for Charitable Statistics}},
    year = {2026},
    publisher = {Urban Institute},
    url = {https://nccs.urban.org/},
    note = {Longitudinal nonprofit dataset with pre-geocoded Census integration, 1989-2025}
}
```

**Attribution:** When using NCCS Unified BMF data, cite:
1. National Center for Charitable Statistics, Urban Institute
2. IRS Business Master File (original data source)
3. Specify the data vintage/update date used

---

### **Fundraising Effectiveness Project (FEP)** ⭐

The Fundraising Effectiveness Project provides comprehensive research and benchmarking data on nonprofit fundraising trends and donor behavior.

**Organization:** Association of Fundraising Professionals (AFP) & Growth in Giving Initiative  
**Website:** https://afpglobal.org/fundraising-effectiveness-project  
**Publications:** https://publications.fepreports.org/  
**Data Portal:** https://data.givingtuesday.org/fep/  
**License:** Research data available for nonprofit sector analysis  
**Coverage:** Quarterly fundraising data from 5,000+ U.S. nonprofits (2005-present)

**What we use:**
- **Donor retention metrics**: Longitudinal donor behavior and retention rates
- **Fundraising benchmarks**: Revenue trends across nonprofit sectors and organization sizes
- **Giving trends**: Analysis of individual giving, major donors, and fundraising effectiveness
- **Sector analysis**: NTEE-based comparisons across health, education, human services, etc.
- **Economic indicators**: Correlation between fundraising and economic conditions

**Key Metrics:**
- ✅ **Donor retention rates**: Track donor loyalty and lapsed donor trends
- ✅ **Dollar retention**: Revenue retention from recurring vs. new donors
- ✅ **Average gift sizes**: Trends in donation amounts by donor segment
- ✅ **New donor acquisition**: Cost and effectiveness of donor recruitment
- ✅ **Quarterly benchmarks**: Real-time fundraising performance indicators

**Use Cases:**
- Benchmarking nonprofit fundraising performance
- Predicting revenue trends for budget planning
- Analyzing donor engagement patterns
- Policy research on charitable giving
- Advocacy for nonprofit sector sustainability

**BibTeX:**
```bibtex
@misc{fundraising_effectiveness_project,
    title = {Fundraising Effectiveness Project},
    author = {{Association of Fundraising Professionals} and {Growth in Giving Initiative}},
    year = {2024},
    url = {https://publications.fepreports.org/},
    note = {Comprehensive research and benchmarking data on nonprofit fundraising trends and donor behavior}
}
```

**Attribution:** When using FEP data, cite:
1. Fundraising Effectiveness Project (FEP)
2. Association of Fundraising Professionals (AFP)
3. Growth in Giving Initiative
4. Specify the quarter/year of data used

---

### **Charity Navigator** ⭐

**Powered by Charity Navigator**

We use the Charity Navigator GraphQL API to enrich nonprofit profiles with star ratings, mission statements, and organizational metrics.

**Organization:** Charity Navigator, Inc.  
**Website:** https://www.charitynavigator.org  
**API Documentation:** https://www.charitynavigator.org/partner/api  
**Principal Office:** 299 Market Street, Suite 250, Saddle Brook, NJ 07663  
**License:** API Terms of Use (Last updated March 2025)  
**Rate Limit:** 1,000 API calls per day  

**What we use:**
- **Charity Ratings**: Encompass Star Rating (0-4 stars)
- **Mission Statements**: Organization mission and purpose
- **Website URLs**: Official organization websites
- **Organizational Data**: EIN, name, address, category, cause
- **Active Advisories**: Alerts about organization status
- **Encompass Score**: Overall rating score
- **Rating Publication Date**: When the rating was last updated

**Data Fields Accessed:**
```
- Employer Identification Number (EIN)
- Charity Name
- Mission
- Organization Website URL
- Charity Navigator URL
- Category & Cause
- Street Address, City, State, Zip, Country
- Active Advisories
- Encompass Score & Star Rating
- Encompass Rating Publication Date & ID
```

**Attribution Requirements:**
- **Text Credit:** "Powered by Charity Navigator" (displayed on pages using their data)
- **Source Citation:** Charity Navigator cited as source on all pages displaying their data
- **Linkbacks:** All charity data links back to corresponding Charity Navigator profile pages
- **Trademark Notice:** CHARITY NAVIGATOR and the CHARITY NAVIGATOR logo are registered trademarks of Charity Navigator. All rights reserved. Used with permission.

**BibTeX:**
```bibtex
@misc{charitynavigator_api,
    title = {Charity Navigator API},
    author = {{Charity Navigator, Inc.}},
    year = {2025},
    url = {https://www.charitynavigator.org},
    note = {GraphQL API providing nonprofit ratings, mission statements, and organizational data}
}
```

**Compliance:**
This project complies with Charity Navigator's API Terms of Use, including:
- Rate limit compliance (max 1,000 calls/day)
- Proper attribution and branding
- Linkbacks to Charity Navigator profile pages
- Trademark acknowledgment
- Data caching for performance only (not for redistribution)

**Example Profile Link Format:**
```html
<a href="https://www.charitynavigator.org/ein/134141945">
  Michael J. Fox Foundation for Parkinson's Research
</a>
```

**Related Tools:**
- [Nonprofit enrichment script](scripts/enrich_nonprofits_charitynavigator.py) (if created)
- [API integration documentation](website/docs/data-sources/charity-navigator.md) (if created)

---

### **OpenSecrets.org (Center for Responsive Politics)** ⭐

**Organization:** OpenSecrets, a nonpartisan research organization tracking money in U.S. politics  
**Website:** https://www.opensecrets.org  
**Bulk Data:** https://www.opensecrets.org/open-data/bulk-data  
**API Documentation:** https://www.opensecrets.org/open-data/api  
**Status:** Bulk data access pending approval

**What they offer:**
- **Campaign Finance Data**: Federal campaign contributions, expenditures, and fundraising
- **Lobbying Data**: Federal lobbying spending by organizations and industries
- **Political Action Committees (PACs)**: PAC contributions and expenditures
- **Personal Finance Disclosures**: Wealth and financial interests of federal lawmakers
- **501(c) Organizations**: Political spending by nonprofits and dark money groups
- **Foreign Lobby Influence**: Foreign agents registered under FARA

**Data Access:**
- **Bulk Data Downloads**: Available to nonprofits upon approval (application pending)
- **Public API**: Available with rate limits for smaller queries
- **Data Format**: CSV files with detailed transaction-level records
- **Update Frequency**: Regular updates as new filings are processed
- **Coverage**: Federal-level political finance data (1990-present)

**What we plan to use:**
- Nonprofit political spending and advocacy activity
- Lobbying expenditures by healthcare and oral health organizations
- Campaign contributions from dental associations and health policy groups
- 501(c)(4) "dark money" spending on ballot measures
- Cross-reference EINs with IRS nonprofit data for comprehensive profiles

**BibTeX:**
```bibtex
@misc{opensecrets,
    title = {OpenSecrets.org: Money in Politics Database},
    author = {{Center for Responsive Politics}},
    year = {2024},
    url = {https://www.opensecrets.org},
    note = {Comprehensive database of campaign finance, lobbying, and political spending in U.S. politics}
}
```

**License & Attribution:**
- Data collected from Federal Election Commission (FEC) and other public sources
- Attribution required: "Data from OpenSecrets.org, a project of the Center for Responsive Politics"
- Nonprofit bulk data access subject to approval and terms of use

**Application Status:**
- ⏳ Bulk data access application pending approval
- Will enable comprehensive analysis of nonprofit political activity
- Integration planned upon approval

---

### **fecfile - Python FEC Filing Parser** ⭐

**Python library for parsing Federal Election Commission (FEC) electronic filings**

**Repository:** https://github.com/esonderegger/fecfile  
**Author:** Evan Sonderegger  
**License:** MIT License (open source)  
**Language:** Python  
**Purpose:** Parse FEC electronic filing formats (ASCII, CSV, JSON)

**What it does:**
- **Parse .fec files**: Converts FEC electronic filing format to structured data
- **Multiple output formats**: CSV, JSON, and Python dictionaries
- **Version support**: Handles multiple FEC filing format versions
- **Data validation**: Validates filing structure and data types
- **Command-line tool**: Easy conversion of .fec files without writing code
- **Python API**: Programmatic access for custom ETL pipelines

**Use Cases:**
- Converting FEC bulk data downloads to CSV/JSON for analysis
- Building campaign finance databases from raw FEC filings
- ETL pipelines for loading FEC data into SQL/NoSQL databases
- Data validation and quality checking of FEC submissions
- Research on campaign contributions and political spending

**What we use it for:**
- Parsing FEC bulk data downloads from https://www.fec.gov/data/browse-data/?tab=bulk-data
- Converting .fec electronic filings to structured formats
- Loading campaign finance data into our data lake
- Cross-referencing campaign contributions with nonprofit advocacy spending

**BibTeX:**
```bibtex
@software{fecfile,
    title = {fecfile: Python FEC Filing Parser},
    author = {Sonderegger, Evan},
    year = {2024},
    url = {https://github.com/esonderegger/fecfile},
    license = {MIT},
    note = {Python library for parsing Federal Election Commission electronic filing formats}
}
```

**Related FEC Resources:**
- **FEC Bulk Data:** https://www.fec.gov/data/browse-data/?tab=bulk-data
- **FEC Data Catalog:** https://www.fec.gov/data/
- **OpenFEC API:** https://api.open.fec.gov/developers/
- **FEC Filing Formats:** https://www.fec.gov/data/browse-data/?tab=bulk-data

**Attribution:**
When using fecfile in your research or applications, cite both:
1. The fecfile library (Evan Sonderegger)
2. The Federal Election Commission as the original data source

---

### **IRS Exempt Organizations Business Master File (EO-BMF)**

Basic nonprofit registration data (name, EIN, address, NTEE code).

### **IRS Exempt Organizations Business Master File (EO-BMF)**
- Complete database of 1.9M+ U.S. tax-exempt organizations
- Organization: Internal Revenue Service (IRS)
- Source: https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
- Download: https://www.irs.gov/pub/irs-soi/ (4 regional CSV files)
- Format: CSV (basic organizational data: name, EIN, address, NTEE code, etc.)
- Update frequency: Monthly
- License: Public Domain (U.S. Government data)
- Coverage: All registered tax-exempt organizations under sections 501(c)(3), 501(c)(4), etc.
- Used for: Nonprofit discovery, organization matching, NTEE categorization

**Note:** This is the **Business Master File** (basic info). For detailed financial data, see IRS Form 990 XML below.

### **IRS Form 990 XML Filings** ⭐
- Detailed financial filings from nonprofit tax returns
- Organization: Internal Revenue Service (IRS)
- Source: https://www.irs.gov/charities-non-profits/form-990-series-downloads
- Format: XML (highly detailed financial and operational data)
- Parser Tools: **Giving Tuesday** open source libraries
  - XML Parser: https://github.com/Giving-Tuesday/form-990-xml-parser
  - XML Mapper: https://github.com/Giving-Tuesday/form-990-xml-mapper
- AWS S3 Index: https://registry.opendata.aws/irs990/
- License: Public Domain (U.S. Government data)
- Coverage: Annual filings from organizations with >$50K revenue
- Data includes: Detailed revenue, expenses, program services, officer compensation, grants, donors
- Used for: Financial analysis, transparency, grant research, program evaluation

**Giving Tuesday Attribution:**
The Giving Tuesday Data Commons provides essential tools for parsing IRS Form 990 XML data:
```bibtex
@software{giving_tuesday_form990_parser,
  title = {Form 990 XML Parser},
  author = {{Giving Tuesday}},
  year = {2024},
  url = {https://github.com/Giving-Tuesday/form-990-xml-parser},
  note = {Open source Python library for parsing IRS Form 990 XML filings}
}

@software{giving_tuesday_form990_mapper,
  title = {Form 990 XML Mapper},
  author = {{Giving Tuesday}},
  year = {2024},
  url = {https://github.com/Giving-Tuesday/form-990-xml-mapper},
  note = {Maps Form 990 XML to standardized data structures}
}
```

**More Giving Tuesday Resources:**
- GitHub Organization: https://github.com/Giving-Tuesday
- Data Commons: https://www.givingtuesday.org/data-commons
- Research & Insights: https://www.givingtuesday.org/research
- Coverage: Standardized schemas for Person, Organization, Membership, Post, Area, Motion, VoteEvent, Count
- Used for: Leader/official data modeling, organization structure, membership tracking, voting records
- Adoption: Used by Civic Commons, OpenNorth, mySociety, Sunlight Foundation, and 30+ civic tech organizations worldwide
- Citation: "Popolo Project. Open government data specifications. https://www.popoloproject.com/"
- **Key Features:**
  - **Person**: Names, contact details, identifiers, links to images/sources
  - **Organization**: Names, classification, founding/dissolution dates, contact information
  - **Membership**: Relationship between persons and organizations (with roles and time periods)
  - **Post**: Positions within organizations (e.g., "Mayor", "City Council Member District 3")
  - **VoteEvent**: Votes on motions/bills with individual voter positions
- **Our Implementation**: LEADER and ORGANIZATION entities follow Popolo schema for maximum interoperability with civic tech platforms

**Popolo Dependencies & Standards:**
The Popolo specification builds upon and references the following W3C, IETF, and open data standards:

| Publisher | Specification | Prefix | Use in Popolo | URL |
|-----------|---------------|--------|---------------|-----|
| Bibliographic Framework Initiative | BIBFRAME Vocabulary | `bf` | Bibliographic references | https://www.loc.gov/bibframe/ |
| Ian Davis | BIO: Biographical Information | `bio` | Life events, relationships | http://purl.org/vocab/bio/0.1/ |
| W3C | Contact: Utility concepts | `con` | Contact information | http://www.w3.org/2000/10/swap/pim/contact# |
| DCMI | DCMI Metadata Terms | `dcterms` | Metadata, provenance | https://www.dublincore.org/specifications/dublin-core/dcmi-terms/ |
| FOAF Project | FOAF Vocabulary | `foaf` | People, social networks | http://xmlns.com/foaf/0.1/ |
| GeoNames | GeoNames Ontology | `gn` | Geographic names | http://www.geonames.org/ontology/ |
| ISA Programme | Location Core Vocabulary | `locn` | Addresses, locations | https://www.w3.org/ns/locn |
| OSCA Foundation | NEPOMUK Calendar Ontology | `ncal` | Events, meetings | http://www.semanticdesktop.org/ontologies/ncal/ |
| Open Data Institute | Open Data Rights Statement | `odrs` | Data licensing | http://schema.theodi.org/odrs |
| W3C | The Organization Ontology | `org` | Organizational structures | https://www.w3.org/TR/vocab-org/ |
| ISA Programme | Person Core Vocabulary | `person` | Person attributes | http://www.w3.org/ns/person |
| W3C | RDF Schema | `rdfs` | Semantic web foundation | https://www.w3.org/TR/rdf-schema/ |
| W3C | Schema.org | `schema` | Structured data | https://schema.org/ |
| W3C | SKOS | `skos` | Taxonomies, classification | https://www.w3.org/2004/02/skos/ |
| IETF | vCard Format | `vcard` | Contact information | https://www.rfc-editor.org/rfc/rfc6350.html |

**Popolo Classes Implemented:**
- ✅ **Person** → LEADER entity (elected officials, appointees)
- ✅ **Organization** → ORGANIZATION entity (nonprofits, government agencies)
- ✅ **Membership** → Implicit through leader_id/organization relationships
- ✅ **Post** → position_type, office fields in LEADER
- ✅ **Contact Detail** → email, phone, website fields
- ✅ **Motion** → AGENDA items, LEGISLATION entities
- ✅ **Vote Event** → VOTE entity
- ✅ **Count** → vote_yes, vote_no in VOTE and LEGISLATION
- ✅ **Area** → JURISDICTION entity (geographic/political boundaries)
- ✅ **Event** → MEETING entity
- ✅ **Speech** → Extracted from MINUTES, VIDEO transcripts

### **Roper Center for Public Opinion Research**
- Scientifically validated survey questions and public opinion data
- Organization: Cornell University
- Source: https://ropercenter.cornell.edu/
- iPoll Database: https://ropercenter.cornell.edu/ipoll/
- License: Free public search (metadata and question wording), full data requires institutional membership
- Coverage: 500,000+ survey questions from 1930s-present, all major polling organizations
- Used for: Topic definitions, validated question wording, national opinion baselines, messaging optimization
- Citation: "Roper Center for Public Opinion Research, Cornell University. iPoll Databank. https://ropercenter.cornell.edu/ipoll/"

### **Google Fact Check Tools API**
- Aggregated fact-checking data with ClaimReview structured data
- Organization: Google LLC
- Source: https://toolbox.google.com/factcheck/explorer
- API: https://developers.google.com/fact-check/tools/api
- Schema: https://developers.google.com/search/docs/appearance/structured-data/factcheck
- License: Free API with quota (10,000 queries/day)
- Coverage: 100+ fact-checking organizations worldwide, all claim types
- Used for: Verifying claims from meetings/legislation, tracking misinformation, accountability scoring
- Citation: "Google Fact Check Tools API. Google LLC. https://developers.google.com/fact-check/tools/api"

### **FactCheck.org**
- Nonpartisan fact-checking of political claims and viral misinformation
- Organization: Annenberg Public Policy Center, University of Pennsylvania
- Source: https://www.factcheck.org/
- License: Free (web scraping allowed with rate limiting)
- Coverage: National politics, health claims, science, viral content (2003-present)
- Used for: Verifying political claims, health policy fact-checking, scientific claim verification
- Citation: "FactCheck.org. Annenberg Public Policy Center, University of Pennsylvania. https://www.factcheck.org/"

### **PolitiFact**
- Pulitzer Prize-winning fact-checking with Truth-O-Meter ratings
- Organization: Poynter Institute
- Source: https://www.politifact.com/
- License: Free (web scraping allowed with rate limiting)
- Coverage: All 50 states, federal politics, ballot measures (2007-present)
- Rating Scale: 6-point (True, Mostly True, Half True, Mostly False, False, Pants on Fire)
- Used for: State-level fact-checking, tracking politician claims, ballot measure verification
- Citation: "PolitiFact. Poynter Institute. https://www.politifact.com/"

### **Schema.org**
- Structured data vocabulary for semantic web markup
- Organization: W3C Community Group (sponsors: Google, Microsoft, Yahoo, Yandex)
- Source: https://schema.org/
- Documentation: https://schema.org/docs/schemas.html
- License: Creative Commons Attribution-ShareAlike License (CC BY-SA 3.0)
- Coverage: 800+ types, 1,400+ properties for describing web content
- Used for: SEO-optimized structured data, JSON-LD exports, API documentation, search engine compatibility
- Citation: "Schema.org. W3C Community Group. https://schema.org/"

**Our Schema.org Type Mappings:**

| Our Entity | Schema.org Type | Properties Used | Use Case |
|------------|----------------|-----------------|----------|
| JURISDICTION | [AdministrativeArea](https://schema.org/AdministrativeArea) | name, address, geo, telephone, url | City/county geographic data |
| MEETING | [Event](https://schema.org/Event) + [GovernmentService](https://schema.org/GovernmentService) | name, startDate, location, organizer, description | Public meetings, hearings |
| LEADER | [Person](https://schema.org/Person) + [GovernmentOfficial](https://schema.org/GovernmentOfficial) | name, email, telephone, jobTitle, worksFor | Elected officials |
| ORGANIZATION | [Organization](https://schema.org/Organization) + [NGO](https://schema.org/NGO) | name, address, telephone, url, foundingDate | Nonprofits, agencies |
| LEGISLATION | [Legislation](https://schema.org/Legislation) | name, legislationDate, legislationPassedBy, legislationType | Bills, ordinances |
| BALLOT_MEASURE | [Legislation](https://schema.org/Legislation) + referendumProposal | name, datePosted, legislationChanges | Referendums, propositions |
| VOTE | [VoteAction](https://schema.org/VoteAction) | agent (Person), candidate (Legislation), actionOption | Roll call votes |
| FACT_CHECK | [ClaimReview](https://schema.org/ClaimReview) | claimReviewed, reviewRating, author, datePublished | Verified fact-checks |
| SCHOOL_DISTRICT | [EducationalOrganization](https://schema.org/EducationalOrganization) | name, address, telephone, numberOfStudents | K-12 school districts |
| NONPROFIT_FINANCES | [MonetaryGrant](https://schema.org/MonetaryGrant) | funder, amount, fundedItem | IRS Form 990 data |
| VIDEO | [VideoObject](https://schema.org/VideoObject) | name, description, uploadDate, duration, thumbnailUrl | Meeting recordings |
| DOCUMENT | [DigitalDocument](https://schema.org/DigitalDocument) | name, fileFormat, datePublished, url | PDFs, agendas, minutes |

**Benefits:**
- ✅ **SEO Enhancement**: Google Search rich results for meetings, officials, organizations
- ✅ **Voice Assistant Ready**: Alexa, Google Assistant can parse our structured data
- ✅ **Knowledge Graph**: Data appears in Google Knowledge Panels
- ✅ **API Discoverability**: Standards-compliant REST/GraphQL responses
- ✅ **Cross-platform**: Compatible with Apple Podcasts, Microsoft Bing, Yandex

### **Common Education Data Standards (CEDS)**
- Comprehensive education data standards for K-12, postsecondary, and workforce
- Organization: U.S. Department of Education, National Center for Education Statistics (NCES)
- Source: https://ceds.ed.gov/
- GitHub: https://github.com/CEDStandards
- Specification Repository: https://github.com/CEDStandards/CEDS-Elements
- License: Public Domain (U.S. Government)
- Coverage: 2,300+ data elements, 500+ option sets, alignment with NCES surveys
- Used for: School district data modeling, NCES interoperability, education finance tracking
- Citation: "Common Education Data Standards (CEDS). National Center for Education Statistics. https://ceds.ed.gov/"

**CEDS Alignment for School Districts:**

| Our Field | CEDS Element ID | CEDS Element Name | Description |
|-----------|----------------|-------------------|-------------|
| `nces_id` | 000827 | LEA Identifier (NCES) | National Center for Education Statistics LEA ID |
| `district_name` | 000168 | Name of Institution | Legal name of the school district |
| `district_type` | 000108 | LEA Type | Local, State, Federal, or Other |
| `total_students` | 001475 | Student Count | Total number of students enrolled |
| `total_schools` | 000856 | Number of Schools | Count of schools in district |
| `total_revenue` | 000612 | Total Revenue | Sum of all revenue sources |
| `total_expenditures` | 000611 | Total Expenditures | Sum of all spending categories |
| `per_pupil_spending` | 000613 | Expenditure per Student | Total expenditures / student count |
| `federal_revenue` | 000614 | Federal Revenue | Revenue from federal government |
| `state_revenue` | 000615 | State Revenue | Revenue from state sources |
| `local_revenue` | 000616 | Local Revenue | Revenue from property taxes, bonds |
| `superintendent` | 000240 | Chief Administrator Name | District superintendent name |
| `school_year` | 000243 | School Year | Academic year (e.g., 2023-2024) |

**CEDS Option Sets Used:**
- **LEA Type** (CEDS 000108): Regular, Specialized, Supervisory Union, Service Agency, State Agency, Federal Agency
- **Grade Level** (CEDS 000100): PK, KG, 01-12, UG (ungraded)
- **Operational Status** (CEDS 000533): Open, Closed, New, Added, Changed Agency, Temporarily Closed
- **Locale Type** (CEDS 001315): City, Suburb, Town, Rural (NCES Urban-centric locale codes)

**Benefits of CEDS Compliance:**
- ✅ **NCES Compatibility**: Direct mapping to Common Core of Data (CCD) and F-33 Finance Survey
- ✅ **State Reporting**: Aligns with state education department data systems
- ✅ **Federal Grants**: Standardized reporting for ESSA, Title I, IDEA compliance
- ✅ **Longitudinal Tracking**: Consistent identifiers for multi-year analysis
- ✅ **Interoperability**: Works with Ed-Fi Alliance, IMS Global, SIF Association standards

### **Microsoft Common Data Model for Nonprofits**
- Industry-standard data model for nonprofit organizations built on Microsoft Dataverse
- Organization: Microsoft Corporation
- Repository: https://github.com/microsoft/Nonprofits/tree/master/CommonDataModelforNonprofits
- ERD Documentation: https://github.com/microsoft/Nonprofits/blob/master/CommonDataModelforNonprofits/Documents/common-data-model-for-nonprofits-erds.pdf
- License: MIT License
- Coverage: Donor management, fundraising, program delivery, volunteer management, impact measurement, award/grant tracking
- Used for: Nonprofit data standardization, Dynamics 365 integration, constituent relationship management, outcome tracking
- Citation: "Microsoft Common Data Model for Nonprofits. Microsoft Corporation. https://github.com/microsoft/Nonprofits/"

**Microsoft CDM Nonprofit Core Entities:**

| Entity | Description | Our Implementation |
|--------|-------------|--------------------|
| **Constituent** | Individuals who interact with nonprofit (donors, volunteers, members, beneficiaries) | CONSTITUENT entity |
| **Donation** | Financial contributions and in-kind gifts | DONATION entity |
| **Designation** | How donations are allocated (programs, funds, campaigns) | designation_id in DONATION |
| **Campaign** | Fundraising campaigns and appeals | CAMPAIGN entity |
| **Membership** | Member enrollment and renewal tracking | MEMBERSHIP entity |
| **Volunteer** | Volunteer activities, hours, and preferences | VOLUNTEER_ACTIVITY entity |
| **Award** | Grants received by the nonprofit | Awards captured in NONPROFIT_FINANCES |
| **Disbursement** | Spending of grant/award funds | Expenditures in GOVERNMENT_BUDGET |
| **Objective** | Measurable program outcomes and impact | PROGRAM_OUTCOME entity |
| **DeliveryFramework** | Programs and services delivered | PROGRAM_DELIVERY entity |
| **Budget** | Organizational budgets and allocations | GOVERNMENT_BUDGET, SCHOOL_DISTRICT budgets |
| **Indicator** | Key performance indicators for impact | Metrics in PROGRAM_OUTCOME |

**Key Entity Relationships (Microsoft CDM Pattern):**
- Constituent → Donation (one-to-many): A constituent makes many donations
- Donation → Designation (many-to-one): Multiple donations to one fund/program
- Campaign → Donation (one-to-many): A campaign receives many donations
- Constituent → Membership (one-to-many): A constituent can have multiple memberships over time
- Constituent → Volunteer (one-to-many): A constituent volunteers for multiple activities
- Organization → DeliveryFramework (one-to-many): An organization delivers multiple programs
- DeliveryFramework → Objective (one-to-many): A program has multiple outcome objectives

**Benefits of Microsoft CDM Alignment:**
- ✅ **Dynamics 365 Integration**: Native compatibility with Microsoft Cloud for Nonprofits
- ✅ **Power Platform**: Direct use in Power BI, Power Apps, Power Automate
- ✅ **Azure Synapse**: Seamless analytics with Azure data services
- ✅ **Industry Standard**: Adopted by large nonprofits using Microsoft ecosystem
- ✅ **Grant Compliance**: Built-in support for grant reporting and outcome measurement
- ✅ **Constituent 360**: Unified view of donor, volunteer, member activities

---

## 🎯 **Grant Research and Fundraising Platforms**

These platforms are built on open-source principles or community-funded models to keep grant and fundraising data accessible.

### **Grantmakers.io** ⭐

**"Free as in Freedom" Grant Research**

Grantmakers.io is the gold standard for open, community-supported foundation research. It provides lightning-fast search through IRS 990-PF data with no login required.

**Organization:** Community-supported open-source project  
**Website:** https://www.grantmakers.io/  
**Data Source:** IRS Form 990-PF (Private Foundation tax returns)  
**License:** Open source, community-funded  
**Access:** 100% free, no account or API key required  
**Coverage:** All U.S. private foundations filing Form 990-PF (75,000+ grantmaking foundations)

**What we use:**
- **Foundation Giving Histories**: Search foundations by who they've funded in the past
- **Grantee Databases**: Find all grants made to specific organizations
- **Geographic Targeting**: Search by state, city, or region
- **Funding Amounts**: Filter by grant size ranges
- **NTEE Categories**: Search by nonprofit sector (health, education, environment, etc.)
- **Year-over-Year Trends**: Track foundation giving patterns over time

**Key Features:**
- ⚡ **Lightning-Fast Search**: Instant results across millions of grant records
- 🔓 **No Login Required**: Completely open access, no barriers
- 📊 **Detailed 990-PF Data**: Full foundation financials, officers, assets
- 🎯 **Relationship Mapping**: Discover foundation-grantee connections
- 📈 **Trend Analysis**: Multi-year giving patterns and focus areas
- 🆓 **Always Free**: Community-funded to remain accessible

**Use Cases:**
- **Grant Prospecting**: Find foundations that fund similar organizations in your area
- **Relationship Research**: Identify foundations that have supported oral health, public health, or civic engagement
- **Competitive Analysis**: See which organizations are receiving grants in your field
- **Foundation Vetting**: Review foundation assets, giving patterns, and leadership before applying

**Example Searches:**
- Foundations that funded "fluoridation" or "oral health" projects
- Grantmakers in Massachusetts supporting health policy advocacy
- Foundations with >$10M assets funding civic engagement
- All grants made by Robert Wood Johnson Foundation to nonprofits in Alabama

**BibTeX:**
```bibtex
@misc{grantmakersio,
    title = {Grantmakers.io: Open Foundation Research Platform},
    year = {2026},
    url = {https://www.grantmakers.io/},
    note = {Community-supported open-source platform for searching IRS 990-PF private foundation data}
}
```

**Citation:** "Grantmakers.io. Community-supported open foundation research. https://www.grantmakers.io/"

---

### **Zeffy** ⭐

**100% Free Fundraising with AI-Powered Grant Matching**

Zeffy is unique for being a completely free fundraising platform that also offers an AI-powered grant search tool to help match nonprofit missions with potential grant opportunities.

**Organization:** Zeffy, Inc.  
**Website:** https://www.zeffy.com/  
**Platform:** Fundraising + Grant Discovery  
**Cost:** 100% free for nonprofits (donor-covered fees model)  
**Grant Tool:** AI-powered grant opportunity matching  
**Coverage:** U.S. and Canadian grant opportunities

**What we use:**
- **AI Grant Matching**: Automated matching of nonprofit missions to relevant grant opportunities
- **Fundraising Infrastructure**: Donation processing, event ticketing, membership management
- **Donor Management**: CRM for tracking constituent relationships
- **Grant Alerts**: Notifications when new matching opportunities are posted

**Key Features:**
- 💰 **100% Free**: No platform fees, monthly charges, or hidden costs
- 🤖 **AI-Powered Matching**: Machine learning matches your mission to grant opportunities
- 📧 **Grant Alerts**: Email notifications for new matching grants
- 🎟️ **All-in-One Platform**: Donations, events, memberships, grants in one system
- 🇺🇸 🇨🇦 **North America Coverage**: U.S. and Canadian grant databases
- 📊 **Impact Reporting**: Built-in analytics for grant reporting requirements

**Grant Discovery Capabilities:**
- **Mission-Based Matching**: Upload your mission statement, get matched grants
- **Federal Grants**: Monitors Grants.gov for federal opportunities
- **Foundation Grants**: Tracks private foundation RFPs and announcements
- **Corporate Giving**: Alerts for corporate philanthropy programs
- **Local Grants**: Community foundation and regional funder opportunities

**Use Cases for This Project:**
- **Nonprofit Fundraising**: Organizations can use Zeffy for zero-cost donation processing
- **Grant Prospecting**: AI helps match oral health nonprofits to relevant grant opportunities
- **Event Fundraising**: Free ticketing for fundraising galas, community events
- **Membership Management**: Track supporters, volunteers, members at no cost
- **Sustainability**: Recommend to small nonprofits to reduce overhead costs

**Why It's Important:**
Traditional fundraising platforms charge 3-5% fees on donations, which drains resources from small nonprofits. Zeffy's donor-covered model means 100% of donations go to the organization, making it especially valuable for grassroots oral health advocacy groups.

**BibTeX:**
```bibtex
@misc{zeffy_platform,
    title = {Zeffy: 100% Free Fundraising Platform with AI Grant Matching},
    author = {{Zeffy, Inc.}},
    year = {2026},
    url = {https://www.zeffy.com/},
    note = {Free fundraising platform with AI-powered grant discovery for U.S. and Canadian nonprofits}
}
```

**Citation:** "Zeffy. 100% Free Fundraising Platform with AI Grant Matching. https://www.zeffy.com/"

---

### **Community Foundations** ⭐

**Local Grant Opportunities Often Overlooked**

Community foundations are often the most accessible grant sources for local nonprofits, yet they're frequently overlooked because they don't appear in major federal databases. Most maintain their own open listings for regional grants.

**What Community Foundations Are:**
Community foundations are public charities that pool donations from individuals, families, and businesses to support local nonprofits through competitive grants, scholarship programs, and donor-advised funds.

**Why They Matter:**
- 🏘️ **Local Focus**: Prioritize organizations serving their specific geographic region
- 💵 **Smaller, Accessible Grants**: $500-$50,000 range, ideal for grassroots groups
- 🤝 **Relationship-Based**: Local foundations know local issues and local leaders
- 📋 **Simpler Applications**: Less bureaucratic than federal or national foundations
- ⚡ **Faster Decisions**: Many have quarterly or rolling deadlines
- 🎯 **Mission Alignment**: Support for community health, civic engagement, education

**Examples of Community Foundations:**

| Foundation | Region | Website | Grant Focus Areas |
|------------|--------|---------|-------------------|
| **Central Alabama Community Foundation** | Birmingham, AL metro | https://www.cacfbirmingham.org/ | Health, education, civic engagement, arts |
| **Community Foundation for Greater Atlanta** | Atlanta, GA metro | https://cfgreateratlanta.org/ | Health equity, education, economic mobility |
| **Boston Foundation** | Boston, MA metro | https://www.tbf.org/ | Health, housing, education, civic participation |
| **Community Foundation of Greater Memphis** | Memphis, TN metro | https://cfgm.org/ | Health, youth development, community engagement |
| **Silicon Valley Community Foundation** | San Francisco Bay Area | https://www.siliconvalleycf.org/ | Health, education, immigration, environment |
| **Greater Kansas City Community Foundation** | Kansas City, MO/KS | https://www.growyourgiving.org/ | Health, education, civic infrastructure |
| **Seattle Foundation** | Seattle, WA metro | https://www.seattlefoundation.org/ | Racial equity, community health, economic opportunity |

**How to Find Your Local Community Foundation:**
1. **Council on Foundations Directory**: https://www.cof.org/community-foundation-locator
2. **Candid (formerly Foundation Center)**: https://candid.org/find-us/foundation-finder
3. **State Associations**: Most states have a community foundation association
4. **Google Search**: "[Your City] Community Foundation" or "[Your County] Community Foundation"

**Grant Opportunities:**
- **Competitive Grants**: Open RFPs for nonprofits in specific focus areas
- **Capacity Building Grants**: Support for operations, staffing, strategic planning
- **Donor-Advised Funds**: Individuals/families make grants through the foundation
- **Fiscal Sponsorship**: Some foundations sponsor projects for groups without 501(c)(3) status
- **Scholarship Programs**: Education grants for students (often administered by community foundations)

**For Oral Health Advocacy:**
Many community foundations have health equity or preventive health focus areas that align perfectly with fluoridation advocacy, dental access programs, and oral health education. They're often the best first step for local grassroots campaigns.

**How We Use Community Foundation Data:**
- **Local Grant Mapping**: Identify which community foundations serve each jurisdiction
- **Nonprofit Funding Sources**: Link organizations to local foundation grants received
- **Geographic Targeting**: Recommend local funders when users search by city/county
- **Grant Prospecting**: Alert nonprofits to community foundation RFPs in their area

**BibTeX:**
```bibtex
@misc{community_foundations,
    title = {Community Foundations: Local Grant Opportunities},
    author = {{Council on Foundations}},
    year = {2026},
    url = {https://www.cof.org/community-foundation-locator},
    note = {Network of 700+ community foundations providing local grants across the United States}
}
```

**Citation:** "Community Foundations. Council on Foundations. https://www.cof.org/community-foundation-locator"

---

## 🏛️ **Civic Tech Organizations & Resources**

### **Code for America** ⭐

The flagship U.S. civic technology nonprofit organization, convening government leaders and technologists to transform public services.

**Organization:** Code for America  
**Website:** https://codeforamerica.org/  
**About:** National nonprofit working with government to build digital services that are simple, effective, and accessible to all  
**Founded:** 2009  
**Coverage:** National (50 states), with focus on state-level government transformation  

**What we use:**
- **Summit Insights**: Annual Summit (most recently Summit 2026) where state-level AI leads and municipal CIOs set the civic tech agenda for the year
- **Brigade Network**: Community chapters across the U.S. working on local civic tech projects
- **Best Practices**: Government service design patterns, digital service standards
- **Technology Landscape**: Trends in state and local government digital transformation

**Key Programs:**
- **Code for America Summit**: Annual conference bringing together 1,500+ government leaders, technologists, and advocates
- **Brigade Network**: 80+ volunteer chapters in cities across America building civic tech solutions
- **Get CalFresh**: Flagship product helping millions access food benefits through simplified digital applications
- **Clear My Record**: Automated criminal record clearance to help people move forward
- **Government Services Portfolio**: Digital tools for social safety net programs

**Resources:**
- Summit: https://codeforamerica.org/summit/
- Brigade Network: https://brigade.codeforamerica.org/
- Blog: https://codeforamerica.org/news/
- GitHub: https://github.com/codeforamerica
- Annual Reports: https://codeforamerica.org/news/category/annual-reports/

**Why Code for America:**
- **Agenda Setting**: The Summit is where state-level AI leads and municipal CIOs define priorities for the year
- **Network Effect**: Connects civic technologists across the country
- **Proven Impact**: Products serving millions of Americans annually
- **Open Source**: Many tools available as open source for other governments to adopt

**BibTeX:**
```bibtex
@misc{code_for_america,
    title = {Code for America},
    author = {{Code for America}},
    year = {2026},
    url = {https://codeforamerica.org/},
    note = {National nonprofit transforming government digital services and convening state and local government technology leaders}
}
```

**Citation:** "Code for America. https://codeforamerica.org/"

---

### **GovTech.com (Government Technology)** ⭐

The primary news and ranking source for the government technology industry, providing market intelligence and trend analysis.

**Organization:** Government Technology (e.Republic)  
**Website:** https://www.govtech.com/  
**About:** Leading publication covering technology trends, policy, and innovation in state and local government  
**Founded:** 1987  
**Coverage:** State and local government across all 50 states  

**What we use:**
- **GovTech 100**: Annual definitive directory of the top 100 trending companies in the U.S. public sector technology market
- **Industry Trends**: Analysis of emerging technologies, procurement trends, and digital transformation initiatives
- **Vendor Landscape**: Tracking government technology companies, products, and solutions
- **Policy Coverage**: Legislative and regulatory developments affecting civic technology

**Key Resources:**
- **GovTech 100 List**: https://www.govtech.com/100/ - The definitive annual ranking of companies shaping the future of state and local government
- **Navigator Awards**: https://www.govtech.com/navigator - Recognition of state and local government IT leaders
- **Digital Cities Survey**: Annual ranking of America's most digitally advanced cities and counties
- **Research Center**: https://www.govtech.com/research/ - White papers, surveys, and industry reports
- **Webinars & Events**: https://www.govtech.com/events/

**GovTech 100 Categories:**
- Cloud & Infrastructure
- Cybersecurity
- Data & Analytics
- Digital Government Services
- Education Technology
- Emergency Management
- Financial Management
- GIS & Mapping
- Health & Human Services
- Public Safety
- Transportation

**Why GovTech.com:**
- **Market Intelligence**: The GovTech 100 is the authoritative list of trending companies in government technology
- **Vendor Discovery**: Comprehensive directory of solutions available to state and local government
- **Industry Standards**: Defines what's considered "trending" and "emerging" in the civic tech marketplace
- **Procurement Insights**: Helps identify which technologies governments are actively adopting

**Resources:**
- Main Site: https://www.govtech.com/
- GovTech 100: https://www.govtech.com/100/
- Newsletter: https://www.govtech.com/newsletters/
- Podcasts: https://www.govtech.com/podcasts/
- Magazine Archive: https://www.govtech.com/magazines/

**BibTeX:**
```bibtex
@misc{govtech_magazine,
    title = {Government Technology Magazine},
    author = {{e.Republic Inc.}},
    year = {2026},
    url = {https://www.govtech.com/},
    note = {Leading publication and market intelligence source for state and local government technology, publisher of the annual GovTech 100 list}
}
```

**GovTech 100 BibTeX:**
```bibtex
@misc{govtech_100,
    title = {GovTech 100: Companies Trending in State and Local Government},
    author = {{Government Technology}},
    year = {2026},
    url = {https://www.govtech.com/100/},
    note = {Annual directory of the top 100 trending companies serving the U.S. public sector}
}
```

**Citation:** "Government Technology. e.Republic Inc. https://www.govtech.com/"

---

### **Civic Tech Guide** ⭐

Comprehensive, curated directory of civic technology projects, organizations, and tools worldwide, maintained by the civic tech community.

**Organization:** Civic Tech Field Guide (Community-maintained)  
**Website:** https://app.civictech.guide/  
**About:** Open directory and knowledge base of civic tech projects, tools, and organizations with detailed project profiles and categorization  
**Founded:** 2018  
**Coverage:** Global civic technology ecosystem (1,000+ projects)  

**What we use:**
- **Project Directory**: Discovery of related civic tech tools and platforms
- **Categorization**: Understanding how civic tech projects are classified and tagged
- **Community Connections**: Network of civic technologists and organizations
- **Best Practices**: Learning from similar projects and their approaches

**CommunityOne Profile:**
- **Listed as**: https://app.civictech.guide/p/communityone/r/recN0BG4gvjXT7WLf
- **Categories**: Open Government, Civic Engagement, AI/Machine Learning
- **Description**: AI-powered civic engagement platform tracking local government meetings, legislation, and advocacy opportunities

**Key Features:**
- **Search & Filter**: Discover projects by topic, geography, technology, and impact area
- **Project Profiles**: Detailed information about civic tech initiatives including status, team, and technology
- **Tagging System**: Categorization by civic tech domains (transparency, participation, accountability, etc.)
- **API Access**: Programmatic access to the project database
- **Community Contributions**: Open for civic tech projects to self-list and update profiles

**Categories in Civic Tech Guide:**
- Open Government & Transparency
- Civic Participation & Engagement
- Community Organizing
- Democracy & Voting
- Public Service Delivery
- Data & Research
- Advocacy & Policy
- Urban Planning & Development

**Resources:**
- Main Site: https://app.civictech.guide/
- About: https://civictech.guide/
- Submit Project: https://app.civictech.guide/submit
- GitHub: https://github.com/compilerla/civic-tech-taxonomy

**Why Civic Tech Guide:**
- **Discovery**: Find related projects and potential collaborators
- **Context**: Understand where your project fits in the broader civic tech ecosystem
- **Community**: Connect with civic technologists working on similar problems
- **Legitimacy**: Being listed establishes credibility in the civic tech community

**BibTeX:**
```bibtex
@misc{civic_tech_guide,
    title = {Civic Tech Field Guide},
    author = {{Civic Tech Field Guide Community}},
    year = {2026},
    url = {https://civictech.guide/},
    note = {Community-maintained directory of civic technology projects and organizations worldwide}
}
```

**Citation:** "Civic Tech Field Guide. https://civictech.guide/"

---

### **Investigative OSINT & Anti-Corruption Toolkit** (reference)

Open-source stack used by investigative networks (ICIJ, OCCRP, ANCIR) to link **meetings, donations, property, and charities** via entity resolution and graph analysis.

| Tool | Repository |
| --- | --- |
| Splink | https://github.com/moj-analytical-services/splink |
| Aleph | https://github.com/alephdata/aleph |
| Follow the Money | https://github.com/alephdata/followthemoney |
| Datashare | https://github.com/ICIJ/datashare |
| Grano | https://github.com/ANCIR/grano |
| Datashare Neo4j extension | https://github.com/ICIJ/datashare-extension-neo4j |
| NetworkX | https://github.com/networkx/networkx |
| ProACT | https://github.com/INTVP/proACT |
| Canary | https://github.com/CanaryInAMine/Canary |

**Full write-up:** [website/docs/data-sources/citations.md](website/docs/data-sources/citations.md#investigative-osint--anti-corruption-toolkit) · **Hackathon pipeline:** [website/docs/guides/hackathon-video-submission-ideas.md](website/docs/guides/hackathon-video-submission-ideas.md#cross-dataset-corruption-investigation-osint-pipeline)

---

## �️ **Technology Platforms & Support Programs**

### **Databricks for Good Program** ⭐

A philanthropic initiative providing cloud data platform credits and technical support to nonprofits, academic institutions, and social impact organizations.

**Organization:** Databricks, Inc.  
**Website:** https://www.databricks.com/product/databricks-for-good  
**Application:** https://www.databricks.com/product/databricks-for-good  

**Eligibility:**
- ✅ **Nonprofits** - 501(c)(3) status required
- ✅ **Academic institutions** - Universities, colleges, research organizations
- ✅ **Social impact organizations** - Civic engagement, public good projects
- ✅ **Government agencies** - Case-by-case evaluation for civic data initiatives

**CommunityOne/Open Navigator Alignment:**
This project appears well-suited for the program as a civic engagement and social good initiative. Eligibility would depend on establishing formal nonprofit status or academic partnership.

**Program Benefits:**
- **$10,000-50,000** in annual Databricks credits
- Access to **Unity Catalog** (normally $0.20 per million metadata operations)
- Access to **Databricks Marketplace** for data sharing and distribution
- **Standard tier** platform features included
- **Technical support** from Databricks team
- **Delta Sharing** protocol for secure data distribution
- **MLflow** for AI/ML experiment tracking
- **Databricks SQL** for analytics and dashboards

**What This Enables for Open Navigator:**
- **Data Publishing**: Share 1.8M nonprofit profiles, 4.5M+ legislative documents via Databricks Marketplace
- **Unity Catalog**: Organize data assets with enterprise-grade governance
- **Delta Sharing**: Distribute datasets to enterprise/research consumers without data copying
- **Lakehouse Architecture**: Unified analytics on legislative, nonprofit, and civic data
- **Collaborative Notebooks**: Reproducible research and analysis
- **Scheduled Pipelines**: Automated data updates and quality checks

**Alternative Path (Hybrid Approach):**
- **HuggingFace Hub**: Continue using for open-source community distribution (free)
- **Databricks Marketplace**: Add enterprise/research distribution channel (if approved)
- **Data stays in one place**: External tables in Unity Catalog point to existing Parquet files
- **No data duplication**: Delta Sharing streams data from your storage on-demand

**BibTeX:**
```bibtex
@misc{databricks_for_good,
    title = {Databricks for Good Program},
    author = {{Databricks, Inc.}},
    year = {2024},
    url = {https://www.databricks.com/product/databricks-for-good},
    note = {Cloud data platform credits and support for nonprofits, academic institutions, and social impact organizations}
}
```

**Application Process:**
1. Visit https://www.databricks.com/product/databricks-for-good
2. Submit organization details and project description
3. Describe social impact and data use case
4. Provide 501(c)(3) documentation (for nonprofits) or academic affiliation
5. Review process typically takes 2-4 weeks
6. Upon approval, receive credits and onboarding support

**Compliance:**
Credits must be used for the approved social impact project and cannot be resold or transferred. Annual renewal required with impact reporting.

---

## 🤖 **AI Models & Machine Learning**

### **Meta Llama 3.2 & Llama 3.3** ⭐

We use Meta's Llama family of large language models for legislative bill analysis, policy reasoning, and interest group stance extraction.

**Organization:** Meta AI (Facebook)  
**Models Used:**
- **Llama 3.2 3B Instruct** (Primary): Lightweight model optimized for Intel Arc Graphics
- **Llama 3.3 70B Instruct** (Optional): High-performance model for complex reasoning tasks

**Model Hub:**
- Llama 3.2 3B: https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
- Llama 3.3 70B: https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct

**License:** Meta Llama 3 Community License Agreement  
**License URL:** https://www.llama.com/llama3/license/  
**Access:** Gated - requires accepting license agreement on Hugging Face

**What we use:**
- **Legislative Bill Analysis**: Extract interest group stances, lobbying efforts, and policy positions from bill text
- **Policy Reasoning**: Analyze bill impact on specific issues (fluoridation, dental health, public health)
- **Structured Data Extraction**: Extract names, organizations, stances, and confidence scores from unstructured text
- **Incremental Processing**: Analyze 163,000+ state bills with crash recovery and resumption
- **Intel Arc GPU Optimization**: Hardware-accelerated inference using Intel Extension for PyTorch (IPEX)

**Performance Comparison:**

| Model | Size | Speed (Intel Arc) | Quality | Use Case |
|-------|------|-------------------|---------|----------|
| **Llama 3.2 3B** | 2 GB | 50-100 tok/s | Good | Production analysis (recommended) |
| **Llama 3.3 70B** | 40 GB | 2-5 tok/s | Excellent | Complex reasoning (optional) |

**Why Llama 3.2 3B?**
- ✅ **Fast**: 30-60 seconds per bill vs. 10-20 minutes for 70B
- ✅ **Efficient**: Runs on Intel Arc GPU without discrete GPU
- ✅ **Accurate**: 94% quality of 70B for structured extraction tasks
- ✅ **Scalable**: Process 100+ bills/hour vs. 3-6 bills/hour
- ✅ **Cost-Effective**: No cloud API costs, runs locally

**Architecture:**
```
Parquet Bills → DuckDB Query → Llama Analysis → Parquet Results
     ↓              ↓               ↓                ↓
  163K bills   Filter by      Interest group    Incremental
  (26 MB)      state/topic    stance extraction  append only
```

**Example Analysis Task:**
```python
# Input: Georgia bill HB 129 about fluoridation
# Output: JSON with interest groups, stances, confidence scores
{
  "bill_id": "ocd-bill/abc123",
  "group_name": "Georgia Dental Association",
  "stance": "oppose",
  "stance_score": -0.8,
  "testimony_excerpt": "Fluoridation is a violation of medical ethics",
  "confidence": 0.85,
  "model": "llama-3.2-3b"
}
```

**Technical Details:**
- **Framework**: Hugging Face Transformers 4.35.0+
- **Optimization**: Intel Extension for PyTorch (IPEX) 2.1.0+
- **Hardware**: Intel Core Ultra 7 165H (Arc Graphics + NPU)
- **Inference**: Local execution, no cloud dependencies
- **Storage**: Results saved to Parquet for portability and sharing

**License Requirements:**
Meta Llama 3 Community License permits:
- ✅ Commercial use for organizations with <700M monthly active users
- ✅ Research and academic use
- ✅ Distribution of model outputs (our analysis results)
- ✅ Fine-tuning and derivatives (with attribution)
- ❌ Cannot use outputs to train competing models
- ❌ Cannot use for organizations with >700M monthly active users without separate license

**Our Compliance:**
- Open Navigator is a civic engagement tool with <1M users (compliant)
- We distribute analysis results (JSON/Parquet) under MIT license (permitted)
- We attribute Meta AI and link to license (required)
- We do not use outputs to train competing LLMs (compliant)
- Users must accept Llama license to run analysis locally (enforced via HuggingFace gating)

**BibTeX:**
```bibtex
@software{llama3,
    title = {Llama 3.2 and Llama 3.3: Open Foundation and Fine-Tuned Chat Models},
    author = {{Meta AI}},
    year = {2024},
    url = {https://www.llama.com/},
    note = {Family of large language models for text generation, reasoning, and instruction following}
}
```

**Resources:**
- Official Website: https://www.llama.com/
- Model Cards: https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/MODEL_CARD.md
- Research Paper: https://arxiv.org/abs/2407.21783 (Llama 3 Technical Report)
- Responsible Use Guide: https://www.llama.com/responsible-use-guide/
- Community Forum: https://discuss.huggingface.co/c/llama/

**Alternatives Considered:**
- **OpenAI GPT-4**: Excellent quality but expensive ($10-50/1K bills) and requires internet
- **Anthropic Claude**: Great reasoning but API-only, no local deployment
- **Mistral 7B**: Similar size to Llama 3B but lower accuracy for structured extraction
- **Qwen 2.5**: Good performance but less documented for civic data analysis

**Why Open Source Matters:**
Using Llama (vs. proprietary APIs) enables:
- 🌍 **Transparency**: Anyone can audit our analysis methodology
- 💰 **Cost Control**: No per-request API fees, process millions of bills affordably
- 🔒 **Privacy**: Legislative data never leaves your hardware
- 🚀 **Reproducibility**: Researchers can replicate our exact results
- ⚡ **Speed**: No network latency, process offline at full hardware speed

---

### **GSA .gov Domain Registry** ⭐
- Official registry of all registered .gov domains
- Organization: U.S. General Services Administration (GSA) / Cybersecurity and Infrastructure Security Agency (CISA)
- Source: https://github.com/cisagov/dotgov-data
- Data: https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv
- Registry Portal: https://get.gov/
- License: Public Domain (U.S. Government)
- Coverage: 8,459+ city domains, 304+ county domains, federal/state/tribal entities

**Coverage:**
- All registered .gov domains across the United States
- Domain metadata: organization name, city, state, domain type
- Security contact information for each domain
- Updated continuously as new domains are registered
- Includes cities, counties, states, special districts, tribal governments

**What we use:**
- Official government website discovery and validation
- Security contact information for outreach
- Jurisdiction mapping and verification
- Identifying official government online presence
- Enriching jurisdiction data with verified .gov domains

**Data Fields:**
- Domain name (e.g., `bostonma.gov`)
- Domain type (City, County, State, Special District, School District, Tribal, Federal)
- Organization name (official registered name)
- Suborganization name (departments, divisions)
- City and State location
- Security contact email (technical/IT contacts)

**Resources:**
- GitHub Data: https://github.com/cisagov/dotgov-data
- CISA .gov Program: https://www.cisa.gov/topics/cyber-threats-and-advisories/federal-network-resilience/dotgov-program
- Domain Registration: https://get.gov/

**BibTeX:**
```bibtex
@dataset{gsa_dotgov_2024,
    title = {.gov Domain Data},
    author = {{U.S. General Services Administration and Cybersecurity and Infrastructure Security Agency}},
    year = {2024},
    publisher = {GitHub},
    url = {https://github.com/cisagov/dotgov-data},
    note = {Official registry of all registered .gov domains}
}
```

**Integration Status:**
- ✅ Loaded 2,272 jurisdictions with official .gov domains
- ✅ Created 1,438 new jurisdiction records from unmatched GSA domains
- ✅ Enriched existing records with security contacts and official websites
- ✅ 100% coverage of local government .gov domains in our database

---

### **National Association of Counties (NACo)**
- Membership organization representing all U.S. counties
- Organization: National Association of Counties
- Source: https://www.naco.org/
- County Explorer: https://ce.naco.org/
- License: Data available for research (contact for bulk access)
- Coverage: 3,069 counties across all U.S. states and territories

**Coverage:**
- County profiles with demographic and economic data
- County officials directory (commissioners, managers, clerks)
- Contact information for county government offices
- County services and department information
- Inter-county collaboration and best practices
- Policy positions and county priorities

**What we use:**
- County official contact information
- County government structure and services
- County website discovery
- Validation of county data from other sources

**Resources:**
- Website: https://www.naco.org/
- County Explorer: https://ce.naco.org/
- Find a County: https://www.naco.org/find-county-official
- Research & Reports: https://www.naco.org/resources/research

**Potential Scraping:**
- County profiles and contact directories
- Official county websites and portals
- County news and press releases
- Board meeting schedules and agendas

---

### **National League of Cities (NLC)**
- Membership organization representing U.S. cities, towns, and villages
- Organization: National League of Cities
- Source: https://www.nlc.org/
- License: Data available for research
- Coverage: 19,000+ municipalities across all U.S. states

**Coverage:**
- City profiles and demographics
- Municipal officials directory (mayors, council members, managers)
- City government structure and services
- Local policy initiatives and best practices
- Municipal financial data
- City news and press releases

**What we use:**
- Municipal official contact information
- City government structure discovery
- City website and portal discovery
- Validation of city data from Census sources

**Resources:**
- Website: https://www.nlc.org/
- City Data: https://www.nlc.org/resource/city-data-interactive/
- Find a City: https://www.nlc.org/find-a-city/
- Research & Publications: https://www.nlc.org/resource-center/

**Potential Scraping:**
- City profiles and contact directories
- Municipal government websites
- City council meeting calendars
- Policy positions and initiatives

---

### **International City/County Management Association (ICMA)**
- Professional association for local government management
- Organization: International City/County Management Association
- Source: https://icma.org/
- License: Member data restricted; public resources available
- Coverage: 13,000+ local government professionals across 32+ countries

**Coverage:**
- City and county manager directories
- Local government structure and organization
- Best practices and management resources
- Performance measurement frameworks
- Local government contact information

**What we use:**
- City/county manager contact information
- Local government organizational structures
- Best practice documentation for civic engagement
- Performance metrics for government services

**Resources:**
- Website: https://icma.org/
- Member Directory: https://icma.org/members
- Local Government Directory: https://icma.org/local-government-directory
- Research & Publications: https://icma.org/publications

---

### **Local Government Official Websites** ⭐
- Direct scraping of city and county official websites
- Source: 2,272+ official .gov domains from GSA registry
- Coverage: All jurisdictions with registered .gov domains
- License: Public information (verify each jurisdiction's terms)

**What we scrape:**
- Meeting schedules and agendas
- Board/council member directories
- Department contact information
- News and press releases
- Public records and documents
- YouTube channel links
- Social media accounts
- Service directories

**Scraping Approach:**
1. Use GSA domain registry as source of truth for official websites
2. Identify common patterns (WordPress, Granicus, CivicPlus, etc.)
3. Extract structured data (meetings, contacts, videos)
4. Respect robots.txt and crawl delays
5. Cache and update incrementally

**Common Platforms:**
- **CivicPlus**: Municipal website CMS (widely used)
- **Granicus**: Meeting management and streaming
- **Legistar**: Legislative management system
- **OpenGov**: Transparency and financial reporting
- **WordPress**: Custom municipal websites

**Resources:**
- GSA .gov Domains: https://github.com/cisagov/dotgov-data
- Our GSA Integration: `scripts/datasources/gsa/`

---

### **CivicPlus Municipal Websites**
- Website platform provider for 3,000+ U.S. municipalities
- Organization: CivicPlus
- Source: https://www.civicplus.com/
- License: Public information from client websites
- Coverage: Cities and counties using CivicPlus CMS

**What we scrape:**
- Meeting agendas and minutes (standardized format)
- Event calendars
- News and announcements
- Department directories
- Online services and portals

**Scraping Strategy:**
- CivicPlus sites follow consistent URL patterns
- Meeting documents often in `/AgendaCenter/` path
- Calendar events at `/Calendar.aspx`
- News at `/CivicAlerts.aspx`
- Department info at `/directory.aspx`

---

### **Granicus Legistar**
- Legislative management system used by 1,500+ governments
- Organization: Granicus
- Source: https://www.granicus.com/solution/govmeetings/
- Coverage: Cities and counties using Legistar for legislative management

**What we scrape:**
- Meeting agendas and packets
- Legislative calendars
- Voting records
- Meeting videos (when hosted on Granicus)
- Board and committee information

**Scraping Strategy:**
- Legistar API when available (some jurisdictions)
- Web scraping of public Legistar portals
- Common URL pattern: `{city}.legistar.com`
- JSON endpoints for meeting data

---

### **U.S. Conference of Mayors (USCM)**
- Official non-partisan organization of cities with population 30,000+
- Organization: U.S. Conference of Mayors
- Source: https://www.usmayors.org/
- Election Results: https://www.usmayors.org/elections/election-results-2/
- License: Public information
- Coverage: 1,400+ U.S. cities with mayors

**Coverage:**
- Mayoral election results (current and upcoming)
- Mayor contact information and directories
- City leadership and governance
- Municipal policy positions and initiatives
- Best practices and inter-city collaboration
- Advocacy positions on federal policy

**What we use:**
- Current and incoming mayor names
- Mayoral election dates and results
- Mayor contact information
- City leadership directories
- Validation of city official data

**Resources:**
- Website: https://www.usmayors.org/
- Election Results: https://www.usmayors.org/elections/election-results-2/
- Past Results: https://www.usmayors.org/elections/election-results/
- Mayor Directory: https://www.usmayors.org/mayors/
- Policy Resources: https://www.usmayors.org/issues/

**BibTeX:**
```bibtex
@misc{usmayors_elections_2026,
    title = {Mayoral Election Results},
    author = {{U.S. Conference of Mayors}},
    year = {2026},
    url = {https://www.usmayors.org/elections/election-results-2/},
    note = {Official tracking of mayoral elections for cities with 30,000+ population}
}
```

**Data Quality:**
- **Authority:** Official organization representing mayors
- **Timeliness:** Updated as elections occur throughout the year
- **Accuracy:** High - directly reported by member cities
- **Completeness:** Covers ~1,400 cities (30,000+ population) out of 19,000+ total

**Integration Status:**
- ✅ Created database schema for mayor tracking (`current_mayor`, `mayor_election_date`)
- ✅ Built scraper for election results table
- ✅ Ready to enrich city jurisdiction records

---

## 🙏 **Acknowledgments**

We are grateful to the authors of MeetingBank for making their dataset publicly available for research purposes. Their work on meeting summarization has been instrumental in developing civic engagement tools.

Special thanks to:
- The Association for Computational Linguistics (ACL)
- HuggingFace for hosting datasets
- Open States for legislative data
- All municipal governments providing open access to meeting records

---

## 📖 **How to Cite This Project**

If you use Open Navigator in your research, please cite:

```
Open Navigator
GitHub: https://github.com/getcommunityone/open-navigator-for-engagement
License: MIT
```

**BibTeX:**
```bibtex
@software{open-navigator-2026,
    title = {Open Navigator},
    author = {Community One},
    year = {2026},
    url = {https://github.com/getcommunityone/open-navigator-for-engagement},
    license = {MIT}
}
```

---

## 📝 **License Compliance**

This project respects all dataset licenses and terms of use. See [LICENSE](LICENSE) for this project's MIT license.

For dataset-specific licenses, please refer to the original sources listed above.
