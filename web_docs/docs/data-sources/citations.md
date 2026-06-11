---
sidebar_position: 2
sidebar_label: Data and Citations
displayed_sidebar: citationsSidebar
---

# Data and Citations

:::tip[Why This Page Matters]
**All data used in Open Navigator is properly cited and attributed.** This page provides complete citations, licenses, BibTeX references, and links to original sources for academic research, government data, data sharing standards, and more.

**Use this page to:**
- ✅ Cite data sources in your research or publications
- ✅ Understand licensing and usage terms
- ✅ Find original dataset documentation
- ✅ Access API documentation and technical specs
:::

This page documents all data sources, standards, and research contributions used in **Open Navigator**. All datasets and specifications are properly attributed with citations, licenses, and usage notes.

## 📑 Quick Navigation

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', margin: '20px 0'}}>
  <a href="#-academic-research" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #2196F3'}}>
    <strong>🎓 Academic Research</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>MeetingBank, LocalView, Opportunity Insights, CivicSearch, Datamuse API, Roper Center, CDP, City Scrapers</span>
  </a>
  <a href="#-comparative--deliberative-analysis" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #3F51B5'}}>
    <strong>🆚 Comparative & Deliberative Analysis</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>AllSides, ProCon.org, iSideWith, OnTheIssues, Kialo, Ground News</span>
  </a>
  <a href="#government-data" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #4CAF50'}}>
    <strong>🏛️ Government Data</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>U.S. Census, IRS, Open States, LegiScan</span>
  </a>
  <a href="#data-sharing-standards" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #FF9800'}}>
    <strong>🌐 Data Sharing Standards</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>OCD-ID, Popolo, Schema.org, CEDS, OMOP CDM</span>
  </a>
  <a href="#election--advocacy" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #9C27B0'}}>
    <strong>🗳️ Election & Advocacy</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>Ballotpedia, MIT Election Lab, OpenElections, Alabama FCPA campaign finance disclosures</span>
  </a>
  <a href="#nonprofit--philanthropy" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #F44336'}}>
    <strong>🏢 Nonprofit & Philanthropy</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>IRS EO-BMF (1.9M+ orgs), Google BigQuery (5M+ Form 990s), GivingTuesday Data Lake (5.4M+ raw XMLs), ProPublica (Nonprofits, Congress, Campaign Finance, Vital Signs), Every.org, Findhelp, 211, Microsoft CDM, ARDA, HIFLD, NCS</span>
  </a>
  <a href="#-fact-checking" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #8BC34A'}}>
    <strong>✅ Fact-Checking</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>Google, PolitiFact, FactCheck.org</span>
  </a>
  <a href="#-civic-tech--open-source" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #673AB7'}}>
    <strong>💻 Civic Tech & Open Source</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>GitHub, Code for America, Splink, Aleph, Datashare, Neo4j, NetworkX, hackathons, cloud platforms</span>
  </a>
  <a href="#-community-solutions--use-cases" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #FFEB3B'}}>
    <strong>🌟 Community Solutions & Use Cases</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>Spectrum of Engagement, Harvard, Brookings, Reason Foundation, Open Data Impact, Tableau Data Equity Hub, PolicyMap, IATI</span>
  </a>
  <a href="#-civic-engagement-frameworks" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #00BCD4'}}>
    <strong>🤝 Civic Engagement Frameworks</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>Maine Township digital community programs (CivicPlus case study)</span>
  </a>
  <a href="#acknowledgments" className="card" style={{textDecoration: 'none', padding: '15px', borderLeft: '4px solid #607D8B'}}>
    <strong>🙏 Acknowledgments</strong><br/>
    <span style={{fontSize: '0.9em', color: '#666'}}>Organizations & individuals</span>
  </a>
</div>

---

## 🎓 Academic Research

**In this section:**
- [MeetingBank Dataset](#meetingbank-dataset)
- [LocalView Dataset (Harvard Dataverse)](#localview-dataset-harvard-dataverse)
- [Opportunity Insights](#opportunity-insights)
- [Measuring Conflict in Local Politics](#measuring-conflict-in-local-politics)
- [Council Data Project (CDP)](#council-data-project-cdp)
- [City Scrapers / Documenters.org](#city-scrapers--documentersorg)
- [Roper Center for Public Opinion Research](#roper-center-for-public-opinion-research)
- [Harvard Dataverse](#harvard-dataverse)
- [CivicSearch (School Board Meeting Platform)](#civicsearch-school-board-meeting-platform)
- [Datamuse API (Word-Finding Engine)](#datamuse-api-word-finding-engine)
- [Comparative Agendas Project](#comparative-agendas-project)

### MeetingBank Dataset

**What we use:** 1,366 city council meetings from 6 U.S. cities with transcripts and summaries for meeting discovery, transcript analysis, and summarization benchmarking.

**Citation:**
> Yebowen Hu, Tim Ganter, Hanieh Deilamsalehy, Franck Dernoncourt, Hassan Foroosh, Fei Liu. "MeetingBank: A Benchmark Dataset for Meeting Summarization" In Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL), July 2023, Toronto, Canada.

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
- [📄 Paper](https://arxiv.org/abs/2305.17529)
- [💾 Dataset](https://huggingface.co/datasets/huuuyeah/meetingbank)
- [📦 Zenodo](https://zenodo.org/record/7989108)

---

### LocalView Dataset (Harvard Dataverse)

**Organization:** Harvard University Mellon Urbanism Lab  
**What we use:** 1,000+ municipalities with meeting videos and automated transcripts for large-scale civic data analysis.

- **Website:** https://www.localview.net/
- **Dataverse:** https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM
- **GitHub:** https://mellonurbanism.harvard.edu/localview
- **Coverage:** Thousands of U.S. jurisdictions with continuous data collection
- **Data Included:**
  - Meeting videos (YouTube URLs)
  - Automated transcripts via speech-to-text
  - Metadata (meeting dates, agencies, agendas)
  - Quality tracking per jurisdiction
- **License:** Research use (Harvard Dataverse)
- **Research-grade:** Designed for large-scale quantitative analysis

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

---

### Opportunity Insights

**Organization:** [Opportunity Insights](https://opportunityinsights.org/) — a non-partisan, not-for-profit research group based at Harvard University that studies **economic mobility**, **neighborhoods**, **education**, and related topics using large-scale data, and publishes tools such as the **Opportunity Atlas** and **Social Capital Atlas** for public use.

**What we cite:** Open Navigator links readers to Opportunity Insights as a **reference** for rigorous, neighborhood- and institution-level evidence on upward mobility and place-based policy. **We do not redistribute Opportunity Insights datasets in this repository**; if you use their data or figures, cite the specific paper, dataset, or tool page from [opportunityinsights.org](https://opportunityinsights.org/) and follow their terms.

**Primary site:** [https://opportunityinsights.org/](https://opportunityinsights.org/)

**Resources (examples):**
- [Opportunity Atlas](https://www.opportunityatlas.org/) — neighborhood-level mobility and related maps (see also **Data** on [opportunityinsights.org](https://opportunityinsights.org/))
- Research library, replication materials, and downloadable data repository (see **Data** and **Research** on the site)

**BibTeX (organization + portal — adapt if you cite a specific paper or dataset):**
```bibtex
@misc{opportunity_insights_portal,
  author = {{Opportunity Insights}},
  title = {Opportunity Insights: Research and Data on Economic Mobility},
  year = {2026},
  url = {https://opportunityinsights.org/},
  note = {Non-partisan research institute based at Harvard University; includes Opportunity Atlas and related tools}
}
```

---

### Measuring Conflict in Local Politics

**Authors:** Tyler Simko, Mirya Holman, and Rebecca Johnson  
**What we use:** Methodologies and frameworks for analyzing political conflict, deliberation quality, and civic engagement in local government meetings.

**Citation (Original Version):**
> Simko, T., Holman, M., & Johnson, R. (2024). Measuring Conflict in Local Politics. EdWorkingPapers.com. https://edworkingpapers.com/sites/default/files/ai24-1102.pdf

**Citation (Version 2):**
> Simko, T., Holman, M., & Johnson, R. (2025). Measuring Conflict in Local Politics (Version 2). EdWorkingPapers.com. https://edworkingpapers.com/sites/default/files/ai25-1102_v2.pdf

**Resources:**
- [📄 Paper (2024)](https://edworkingpapers.com/sites/default/files/ai24-1102.pdf)
- [📄 Paper (Version 2, 2025)](https://edworkingpapers.com/sites/default/files/ai25-1102_v2.pdf)
- [🔗 EdWorkingPapers.com](https://edworkingpapers.com/)

**BibTeX:**
```bibtex
@techreport{simko2024measuring,
  author = {Simko, Tyler and Holman, Mirya and Johnson, Rebecca},
  title = {Measuring Conflict in Local Politics},
  year = {2024},
  institution = {EdWorkingPapers.com},
  number = {ai24-1102},
  url = {https://edworkingpapers.com/sites/default/files/ai24-1102.pdf}
}

@techreport{simko2025measuring,
  author = {Simko, Tyler and Holman, Mirya and Johnson, Rebecca},
  title = {Measuring Conflict in Local Politics},
  year = {2025},
  institution = {EdWorkingPapers.com},
  number = {ai25-1102},
  version = {2},
  url = {https://edworkingpapers.com/sites/default/files/ai25-1102_v2.pdf}
}
```

**Research Contributions:**
- Frameworks for measuring political conflict in municipal governments
- Methods for analyzing deliberation quality in public meetings
- Quantitative approaches to civic engagement assessment
- Applications for local government transparency and accountability

**License:** Academic research publication

---

### Council Data Project (CDP)

**Organization:** Open-source civic tech collaboration  
**What we use:** 20+ cities with complete data pipelines - meeting transcripts, videos, voting records, and legislation tracking. **Open Navigator's data model is compatible with CDP backend schema for interoperability.**

- **Website:** https://councildataproject.org/
- **Documentation:** https://councildataproject.org/cdp-backend/
- **GitHub:** https://github.com/CouncilDataProject
- **Backend Models:** https://councildataproject.org/cdp-backend/database_models.html
- **Coverage:** 20+ major U.S. cities with full infrastructure
- **Data Included:**
  - Meeting transcripts (searchable, indexed)
  - Video recordings with timestamps
  - Voting records and roll calls
  - Legislation text and tracking
  - Councilmember information
- **Infrastructure:** Complete ETL pipelines for each city
- **License:** Open source (MIT)
- **API:** Per-city deployments (e.g., https://councildataproject.org/seattle)
- **Data Model:** Event, Session, Transcript, Matter, Vote, Person, Body models
- **Compatibility:** See [CDP Compatibility Guide](./council-data-project-compatibility) for field mappings

**BibTeX:**
```bibtex
@software{council_data_project,
  title = {Council Data Project: Indexing City Council Meetings},
  author = {{Council Data Project Team}},
  year = {2020},
  url = {https://councildataproject.org/},
  note = {Open-source infrastructure for making local government more accessible},
  license = {MIT}
}
```

**Research Context:**
CDP provides a standardized data model for civic meeting data that Open Navigator extends to support:
- Multi-source ingestion (YouTube, LocalView, Legistar, Granicus)
- AI-powered transcription (Gemini, Whisper)
- Nationwide coverage (90,000+ jurisdictions)
- Policy analysis and opportunity detection

---

### City Scrapers / Documenters.org

**Organization:** Documenters Network (civic journalism collaboration)  
**What we use:** 100-500 validated government agency URLs across 5 major cities for automated meeting discovery.

- **Website:** https://cityscrapers.org/
- **Documenters:** https://www.documenters.org/
- **GitHub:** https://github.com/City-Bureau
- **Coverage:** Chicago, Pittsburgh, Detroit, Cleveland, Los Angeles
- **Data Included:**
  - Government agency URLs (start_urls from spider files)
  - Granicus video page URLs with YouTube embeds
  - Meeting event schemas
  - Scraper patterns for common platforms
- **Cities Covered:**
  - Chicago City Scrapers
  - Pittsburgh City Scrapers
  - Detroit Documenters
  - Cleveland City Scrapers
  - LA Metro Documenters
- **License:** Open source (MIT)
- **Use Case:** Pre-validated URLs for quality meeting discovery

**BibTeX:**
```bibtex
@software{city_scrapers,
  title = {City Scrapers},
  author = {{City Bureau and Documenters Network}},
  year = {2024},
  url = {https://cityscrapers.org/},
  license = {MIT}
}
```

---

### Roper Center for Public Opinion Research

**Organization:** Cornell University  
**What we use:** Scientifically validated survey questions and public opinion baselines for topic definitions and messaging optimization.

- **Source:** https://ropercenter.cornell.edu/
- **iPoll Database:** https://ropercenter.cornell.edu/ipoll/
- **Coverage:** 500,000+ survey questions from 1930s-present, all major polling organizations
- **License:** Free public search (metadata and question wording), full data requires institutional membership
- **Citation:** "Roper Center for Public Opinion Research, Cornell University. iPoll Databank. https://ropercenter.cornell.edu/ipoll/"

---

### Harvard Dataverse

**What we use:** Meeting datasets and civic engagement research.

- **Source:** https://dataverse.harvard.edu/
- **License:** Varies by dataset
- **Coverage:** Academic research datasets on local government, public meetings, civic participation

---

### CivicSearch (School Board Meeting Platform)

**Organization:** Datamuse, Inc.  
**What we use:** Aggregated school board meeting transcripts, agendas, and videos for tracking education policy and local governance.

- **Website:** https://schools.civicsearch.org/
- **Platform:** Datamuse-powered civic search interface
- **Coverage:** School districts nationwide with meeting transcripts and videos
- **Data Included:**
  - School board meeting transcripts (AI-indexed)
  - Meeting agendas and minutes
  - Video recordings (when available)
  - Searchable text across multiple districts
  - Meeting dates and attendance
- **Example:** [Tuscaloosa City Schools](https://schools.civicsearch.org/tuscaloosa-city-alabama)
- **License:** Free public access for search; bulk/API access requires case-by-case approval
- **Use Case:** Education policy tracking, school board decision analysis, parent/community engagement

**Access Tiers:**
- **Public Search:** Free access via web interface
- **Bulk Data/API:** Contact Datamuse for research or civic organization partnerships
- **Commercial Use:** Licensing required for commercial applications

**Data Privacy:**
- Public meeting transcripts are public record
- Datamuse indexing and presentation subject to their site terms
- No user-uploaded data sold to third parties

**Attribution Requirements:**
```
Data source: CivicSearch (Datamuse, Inc.)
https://schools.civicsearch.org/
School board meeting transcripts and agendas
```

**Terms of Service:**
- ❌ **No automated scraping** - Use official API when available
- ✅ **Attribution required** - Link back to CivicSearch for data used
- ✅ **Public record data** - Meeting transcripts are generally public domain
- ⚠️ **Bulk access** - Requires partnership agreement for large-scale data extraction

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

**Contact for Data Partnerships:**
For bulk data access, API integration, or civic tech collaborations, reach out to Datamuse directly as a "civic technologist" or research organization. There is no standard commercial checkout - partnerships are handled case-by-case.

---

### Datamuse API (Word-Finding Engine)

**Organization:** Datamuse, Inc.  
**What we use:** Natural language processing tools for text analysis, word associations, rhyme detection, and semantic search in meeting transcripts and policy documents.

- **API Documentation:** https://www.datamuse.com/api/
- **Developer Site:** https://www.datamuse.com/
- **Use Cases:** Dictionary apps, RhymeZone, word associations, semantic search
- **Coverage:** English language word relationships, definitions, pronunciations, usage frequency
- **License:** Free tier for most applications; paid tier for high-volume commercial use

**API Endpoints:**
- `/words` - Word finding based on constraints (rhymes, similar meaning, etc.)
- `/sug` - Word suggestions for autocomplete
- Query parameters for semantic relationships, phonetic matching, vocabulary

**Pricing Tiers:**

| Tier | Cost | Limits | Use Case |
|------|------|--------|----------|
| **Free** | $0 | 100,000 requests/day | Non-commercial, small commercial apps |
| **Professional** | Contact for pricing | Unlimited + support | High-volume commercial applications |

**Free Tier Details:**
- ✅ **100,000 requests per day** - Generous limit for most applications
- ✅ **Commercial use allowed** - Can use in commercial apps under daily limit
- ✅ **No API key required** - Simple HTTP GET requests
- ✅ **Fast response times** - Optimized for real-time applications

**Paid Tier (High-Volume):**
- Exceeding 100,000 requests/day requires paid tier
- Contact Datamuse for custom pricing and SLA
- Dedicated support and guaranteed uptime

**Attribution Requirements:**
- ✅ **Link to Datamuse:** Required (or strongly requested) for free tier users
- ✅ **Credit in documentation:** Mention "Powered by Datamuse API"
- Example: `<a href="https://www.datamuse.com/">Powered by Datamuse API</a>`

**Restrictions:**
- ❌ **No scraping of web interfaces** - Use official API, not web scraping
- ❌ **Rate limiting enforced** - Exceeding 100K/day will be throttled
- ✅ **Caching allowed** - Can cache results to reduce API calls

**Terms of Service:**
- Free tier subject to daily quota
- No sale of user-uploaded data
- Commercial use allowed within free tier limits
- Bulk/enterprise usage requires paid license

**Example API Call:**
```bash
# Find words that mean "government" and sound like "regime"
curl "https://api.datamuse.com/words?ml=government&sl=regime"

# Find words that rhyme with "policy"
curl "https://api.datamuse.com/words?rel_rhy=policy"

# Word associations for "civic engagement"
curl "https://api.datamuse.com/words?ml=civic+engagement&max=10"
```

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

**Integration Use Cases:**
- **Meeting Transcript Analysis:** Identify policy-related terms and semantic relationships
- **Search Enhancement:** Improve search with synonym expansion and related terms
- **Topic Modeling:** Extract key themes from public comments and testimony
- **Accessibility:** Provide word suggestions for users with cognitive disabilities
- **Multilingual Support:** Word associations for translation assistance

**Datamuse.ai (Separate Product):**
Note: Datamuse.ai is a distinct SaaS product for natural language exploration:
- **Starter:** ~$29/month (100 queries/month)
- **Professional:** ~$99/month (unlimited queries + API access)
- **Free Trial:** Available for testing
This is separate from the word-finding API and has different pricing.

---

### Comparative Agendas Project

**Organization:** Comparative Agendas Project (originated as the U.S. Policy Agendas Project by Frank R. Baumgartner and Bryan D. Jones)  
**What we use:** The policy-topic coding taxonomy (major topic and subtopic codes) as a reference framework for classifying meeting, bill, and decision themes.

- **Website:** https://www.comparativeagendas.net/
- **Master Codebook:** https://www.comparativeagendas.net/pages/master-codebook
- **Coverage:** Coded policy agendas across many countries and U.S. institutions, 1947–present
- **Data Included:**
  - Major topic codes (e.g., macroeconomics, civil rights, health, environment)
  - Subtopic codes within each major topic
  - Cross-national and longitudinal policy-attention datasets
- **License:** Free for non-commercial research use; see the site for dataset-specific terms

**BibTeX:**
```bibtex
@misc{comparative_agendas_project,
  author = {{Comparative Agendas Project}},
  title  = {Comparative Agendas Project},
  url    = {https://www.comparativeagendas.net/},
  note   = {Policy-topic coding taxonomy and cross-national policy agendas data (1947--present)}
}
```

**Resources:**
- [🌐 Project site](https://www.comparativeagendas.net/)
- [📕 Master Codebook](https://www.comparativeagendas.net/pages/master-codebook)

---

## 🆚 Comparative & Deliberative Analysis

**In this section:**
- [AllSides](#allsides)
- [ProCon.org (Britannica)](#proconorg-britannica)
- [iSideWith](#isidewith)
- [OnTheIssues](#ontheissues)
- [Kialo](#kialo)
- [Ground News](#ground-news)

These platforms present **multiple positions on the same issue side by side** — pro/con arguments, left/center/right framing, candidate stances, and structured debate trees. We cite them as **reference and design inspiration** for Open Navigator's "competing views" / "argued by" analysis, which surfaces the different sides of a local decision. **We do not redistribute their data, ratings, or argument content**; if you use anything from these sites, cite the specific page and follow each site's terms.

### AllSides

**Organization:** AllSides, Inc.  
**What it does:** Rates the political lean of news outlets (**Left / Center / Right**) and presents the same story as covered by sources across the spectrum, plus a widely cited Media Bias Chart.

- **Website:** https://www.allsides.com/
- **Media Bias Ratings:** https://www.allsides.com/media-bias/ratings
- **Use as reference for:** Presenting a single civic issue through multiple framings instead of one editorial voice.
- **License / use:** Site content is proprietary; **reference-only**. Link and credit AllSides; do not republish their bias ratings or balanced-news feeds as your own.

**BibTeX:**
```bibtex
@misc{allsides,
  author = {{AllSides, Inc.}},
  title  = {AllSides: Balanced News and Media Bias Ratings},
  url    = {https://www.allsides.com/},
  note   = {Left/Center/Right media bias ratings; reference-only, not redistributed.}
}
```

### ProCon.org (Britannica)

**Organization:** Encyclopaedia Britannica (ProCon.org)  
**What it does:** Nonpartisan, **structured pro/con arguments** on controversial public-policy issues, with sourcing for each side.

- **Website:** https://www.procon.org/
- **Use as reference for:** The pro/con argument structure behind the "competing views" lens — each position stated plainly with its supporting evidence.
- **License / use:** Proprietary (Britannica); **reference-only**. Cite the specific issue page; do not copy their argument text.

**BibTeX:**
```bibtex
@misc{procon_britannica,
  author = {{ProCon.org / Encyclopaedia Britannica}},
  title  = {ProCon.org: Pros and Cons of Controversial Issues},
  url    = {https://www.procon.org/},
  note   = {Nonpartisan structured pro/con arguments; reference-only.}
}
```

### iSideWith

**Organization:** iSideWith  
**What it does:** Matches users with candidates and parties by comparing the user's answers against **politicians' stated positions** across policy topics.

- **Website:** https://www.isidewith.com/
- **Use as reference for:** Mapping a decision or candidate to a set of positions per topic.
- **License / use:** Proprietary; **reference-only**. Link and credit; do not scrape or redistribute their position data.

**BibTeX:**
```bibtex
@misc{isidewith,
  author = {{iSideWith}},
  title  = {iSideWith: Political Quiz and Candidate Position Matching},
  url    = {https://www.isidewith.com/},
  note   = {Candidate/voter position matching by issue; reference-only.}
}
```

### OnTheIssues

**Organization:** OnTheIssues (Jesse Gordon / VoteMatch)  
**What it does:** Nonpartisan archive of **politicians' positions and quotes organized by issue**, enabling side-by-side comparison of where officials stand.

- **Website:** https://www.ontheissues.org/
- **Use as reference for:** A per-official, per-topic stance record that complements the "argued by" attribution.
- **License / use:** Proprietary compilation; **reference-only**. Cite the specific politician/issue page.

**BibTeX:**
```bibtex
@misc{ontheissues,
  author = {{OnTheIssues}},
  title  = {OnTheIssues: Every Political Leader on Every Issue},
  url    = {https://www.ontheissues.org/},
  note   = {Politicians' positions and quotes by issue; reference-only.}
}
```

### Kialo

**Organization:** Kialo  
**What it does:** Collaborative **debate platform** that maps an issue into a tree of pro and con arguments, each scored and sourced — a visual model of structured deliberation.

- **Website:** https://www.kialo.com/
- **Education edition:** https://www.kialo-edu.com/
- **Use as reference for:** The branching pro/con argument tree as a way to render the competing-views analysis.
- **License / use:** Proprietary platform; **reference-only**. Link and credit; user-generated debate content is subject to Kialo's terms.

**BibTeX:**
```bibtex
@misc{kialo,
  author = {{Kialo}},
  title  = {Kialo: Structured Debate and Argument Mapping},
  url    = {https://www.kialo.com/},
  note   = {Pro/con argument trees; reference-only.}
}
```

### Ground News

**Organization:** Ground News (Snapwise Inc.)  
**What it does:** News aggregator that **compares coverage of the same story across outlets**, showing bias distribution and "Blindspot" gaps between Left and Right reporting.

- **Website:** https://ground.news/
- **Use as reference for:** Quantifying and displaying how differently the same civic event is framed across sources.
- **License / use:** Proprietary; **reference-only**. Link and credit; do not redistribute their bias/coverage analytics.

**BibTeX:**
```bibtex
@misc{ground_news,
  author = {{Ground News (Snapwise Inc.)}},
  title  = {Ground News: Compare News Coverage and Media Bias},
  url    = {https://ground.news/},
  note   = {Cross-outlet coverage and bias comparison; reference-only.}
}
```

---

## 🏛️ Government Data

**In this section:**
- [U.S. Census Bureau](#us-census-bureau)
- [State Symbols USA (reference)](#state-symbols-usa-reference)
- [IRS Exempt Organizations Business Master File (EO-BMF)](#irs-exempt-organizations-business-master-file-eo-bmf)
- [Open States / Plural Policy](#open-states--plural-policy-)
- [LegiScan](#legiscan-)

### U.S. Census Bureau

**What we use:** Geographic boundaries, demographic data, population estimates, and economic indicators.

- **Source:** https://www.census.gov/
- **License:** Public Domain (U.S. Government)
- **Datasets:** Census Gazetteer, American Community Survey (ACS), Decennial Census
- **Coverage:** All 50 states, 3,144 counties, 19,000+ incorporated places

---

### State Symbols USA (reference)

**Organization:** State Symbols USA (educational resource; Dotsquares)  
**What we use:** Curated **state colors** and related civic identity reference material (third-party compilation, not a government primary source).

- **Website:** https://statesymbolsusa.org/
- **State colors (category):** https://statesymbolsusa.org/categories/colors
- **License / use:** Site content is copyrighted; treat as **reference-only**. Link and credit [State Symbols USA](https://statesymbolsusa.org/) when you mention or display derived context. Do **not** republish their imagery or text as your own without permission from the site operators.

### Wikimedia Commons (reference assets)

**Organization:** Wikimedia Foundation — [Wikimedia Commons](https://commons.wikimedia.org/)  
**What we use:** **Local mirrors** of freely licensed **SVG state flags** and **U.S. license plate** images for documentation and design reference.

- **Local cache:** Run `scripts/wikicommons/download_wikicommons_assets.sh` → `data/cache/wikicommons/` (see `scripts/wikicommons/README.md` and `_manifest.json`). Outputs `{USPS}_colors_hero.svg` (canonical `Flag of …` per state category) and per-state/year license plates plus `{USPS}_latest.*`.
- **Attribution:** Cite each file’s Commons page; licenses are typically CC BY-SA (verify on the file page).

**BibTeX (Commons, generic):**
```bibtex
@misc{wikimedia_commons,
  author = {{Wikimedia Commons contributors}},
  title = {Wikimedia Commons},
  year = {2026},
  url = {https://commons.wikimedia.org/},
  note = {Per-file license on each description page; typically CC BY-SA.}
}
```

**BibTeX (State Symbols USA site, no local mirror):**
```bibtex
@misc{state_symbols_usa,
  author = {{State Symbols USA}},
  title = {State Symbols, Icons, and Treasures Across the {USA}},
  year = {2025},
  url = {https://statesymbolsusa.org/categories/colors},
  note = {Educational reference; state colors category URL. Check site terms before redistributing media.}
}
```

---

### OpenAddresses Project ⭐

**Organization:** OpenAddresses contributors (open-source community)
**What we use:** A developer-focused, raw index of where local governments host their public address, parcel, and appraisal data — structured as JSON/YAML source files (URLs, API endpoints, FTP paths, format/license metadata) rather than a clickable UI. Complements CISA `.gov` and the Census Government Integrated Directory by providing the actual *data endpoint* per jurisdiction (assessor / GIS server) instead of just the website root.

- **Site:** https://openaddresses.io/
- **Repository:** https://github.com/openaddresses/openaddresses
- **Source layout:** per-country / per-state / per-county YAML/JSON files under `sources/` (e.g. `sources/us/al/jefferson.json`) describing the upstream URL, format (Shapefile, CSV, GeoJSON, ArcGIS REST), licensing, and conform/transform rules.
- **Code license:** BSD-3-Clause; per-dataset licenses (mostly public-domain / open) declared inside each source file.
- **Coverage:** 1,000+ U.S. county GIS / assessor systems plus many international jurisdictions.
- **Used for:** Discovering the canonical upstream data URLs for county and city parcel / address systems; downstream of jurisdiction discovery (CISA `.gov`, Census GID) — gives the *where to actually pull the rows from* once a jurisdiction is identified.

**How we use it:** Browse the `sources/` directory in the GitHub repo. For each priority state, the relevant per-county files document the upstream parcel / assessor / GIS endpoint plus the schema mapping needed to normalize it. Cite the specific source file(s) consumed (not just the repo root).

**BibTeX:**
```bibtex
@misc{openaddresses_project,
  author = {{OpenAddresses contributors}},
  title = {OpenAddresses: A free, open, global collection of address data},
  year = {2026},
  url = {https://openaddresses.io/},
  howpublished = {\url{https://github.com/openaddresses/openaddresses}},
  note = {Code: BSD-3-Clause; per-source dataset licenses declared in each YAML file.}
}
```

---

### IRS Exempt Organizations Business Master File (EO-BMF)

**Organization:** Internal Revenue Service (IRS), U.S. Department of Treasury  
**What we use:** **PRIMARY BULK DATA SOURCE** for comprehensive nonprofit data - ALL 1.9M+ U.S. tax-exempt organizations with EIN, NTEE codes, financial data, subsection classification, and geographic location.

- **Source:** https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
- **Search Tool:** https://www.irs.gov/charities-non-profits/tax-exempt-organization-search
- **Bulk Downloads:** https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads
- **API Documentation:** See [IRS Bulk Data Integration](./irs-bulk-data.md)
- **Coverage:** 1,952,238 organizations (as of April 2026)
  - **Churches & Religious Organizations:** 300,000+ (NTEE codes X, X20, X21, X22, X30, X40)
  - **Health Organizations:** 80,000+ (NTEE codes E, E20-E99)
  - **Human Services:** 200,000+ (NTEE codes P, P20-P99)
  - **All Other Categories:** 1.3M+ (Education, Arts, Environment, etc.)
- **Update Frequency:** Monthly
- **License:** Public domain (U.S. government data)
- **Format:** CSV (regional files), convertible to Parquet
- **Record Count:** 1.9M+ total nonprofits across 4 regional files

**Data Fields (28 columns):**
- **Identification:** EIN, organization name, sort name
- **Location:** Street address, city, state, ZIP code
- **Classification:** NTEE code, subsection (501(c)(3), etc.), foundation code
- **Financial:** Asset amount, income amount, revenue amount
- **Status:** Tax-exempt status, deductibility status, ruling date
- **Organization:** Organization code, activity codes, group affiliation

**NTEE Codes for Churches:**
- **X** - Religion Related, Spiritual Development
- **X20** - Christian (churches, ministries)
- **X21** - Protestant
- **X22** - Roman Catholic
- **X30** - Jewish
- **X40** - Islamic

**Use Cases:**
- **Bulk Download:** Get ALL nonprofits in a state (e.g., 26,148 in Alabama vs 25 from ProPublica API)
- **Comprehensive Coverage:** 1,000x more data per request than API methods
- **Offline Analysis:** Download once, query locally forever (cached as Parquet)
- **NTEE Filtering:** Filter by category code (health, education, religion, etc.)
- **Geographic Analysis:** Complete state/city/ZIP coverage for spatial mapping

**BibTeX Citation:**
```bibtex
@misc{irs_eobmf_2026,
  title = {Exempt Organizations Business Master File Extract (EO-BMF)},
  author = {{Internal Revenue Service}},
  year = {2026},
  month = {April},
  url = {https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf},
  note = {Record count: 1,952,238 organizations. Updated monthly.}
}
```

**Integration:**
- **ProPublica API** complements with detailed Form 990 financials and mission statements
- **Every.org** adds human-readable descriptions and cause tags
- **IRS EO-BMF** provides the complete foundation layer with all organizations

**Complements:**
- **ARDA** for congregation characteristics and health ministry programs
- **HIFLD** for geospatial location data
- **National Congregations Study** for social service provision patterns
- **ProPublica API** for detailed financial breakdowns and executive compensation

---

### Open States / Plural Policy ⭐

**Organization:** Plural Policy (formerly Open States Foundation)  
**What we use:** State and local legislative information - bulk downloads of bills, votes, legislators, and legislative sessions for all 50 states.

- **Website:** https://openstates.org/
- **API Documentation:** https://openstates.org/api/
- **Bulk Downloads:** https://open.pluralpolicy.com/data/ ⭐ **Recommended approach**
- **Scrapers Repository:** https://github.com/openstates/openstates-scrapers
- **Local Database Setup:** https://docs.openstates.org/contributing/local-database/
- **Code of Conduct:** https://docs.openstates.org/code-of-conduct/
- **Schema Documentation:** https://github.com/openstates/people/blob/master/schema.md

**Coverage:**
- **All 50 states** + DC + Puerto Rico
- **7,300+ state legislators** with committee assignments
- **Millions of bills** with full text, votes, and sponsors
- **Monthly PostgreSQL dumps** (9.8GB+) for complete local analysis
- **Video sources** (YouTube channels, Granicus portals)

**License:** 
- **Bulk data:** Public Domain (preferred method)
- **API content:** Varies by state
- **API Key:** Free tier (50,000 requests/month)

**Bulk Data Formats:**
1. **CSV:** Complete legislative sessions per state
   - URL: https://data.openstates.org/session/csv/
   - Best for: Spreadsheet analysis, quick exploration
2. **JSON:** Bills with full text and metadata
   - URL: https://data.openstates.org/session/json/
   - Best for: Application integration, detailed parsing
3. **PostgreSQL:** Monthly database dumps
   - URL: https://data.openstates.org/postgres/monthly/
   - Best for: SQL analysis, local development, complete schema
   - Size: 9.8GB+ (complete legislative database)
   - No rate limits on bulk downloads

**What We Use:**
- PostgreSQL monthly dumps for local database (see `scripts/bulk_legislative_download.py`)
- CSV/JSON session data for specific state analysis
- Video source discovery (YouTube channels, Granicus portals)
- Legislator contact information and committee assignments

**Potential Contributions:**
Our project could contribute back to the OpenStates ecosystem:
- **Scraper patterns** for video sources and meeting archives
- **Meeting video discovery** to enhance their data
- **Granicus/YouTube integrations** for automated tracking
- We follow their [Code of Conduct](https://docs.openstates.org/code-of-conduct/) for all contributions

**Local Database Setup:**
We use the PostgreSQL dumps following their [local database documentation](https://docs.openstates.org/contributing/local-database/):
```bash
# Download monthly dump
python scripts/bulk_legislative_download.py --postgres --month 2026-04

# Restore to PostgreSQL
./scripts/setup_openstates_db.sh
```

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

### LegiScan ⭐

**Organization:** LegiScan  
**What we use:** Comprehensive state legislative tracking with bill text, votes, people, and datasets for all 50 states.

- **Website:** https://legiscan.com/
- **API Documentation:** https://legiscan.com/legiscan
- **Dataset Downloads:** https://legiscan.com/datasets
- **People Database:** https://legiscan.com/legiscan/people
- **Bill Search:** https://legiscan.com/

**Coverage:**
- **All 50 states** + DC + U.S. Congress
- **Current and historical legislation** back to 2011
- **Bill text, sponsors, votes, amendments** with full tracking
- **370,000+ legislators** (current and historical)
- **Roll call votes** with individual legislator positions
- **Committee assignments** and hearing schedules
- **Fiscal notes** and impact statements

**Available Datasets:**
1. **National Dataset:** Complete legislative data for all states
   - All bills, resolutions, and legislative documents
   - Updated daily during legislative sessions
   - Includes bill text, sponsors, status tracking
2. **State-Specific Datasets:** Per-state downloads
   - Session-specific or multi-year data
   - Optimized for state-level analysis
3. **People Dataset:** Legislator information
   - Contact details, committee assignments
   - District information and party affiliation
   - Historical legislator records
4. **Roll Call Dataset:** Voting records
   - Individual votes on bills and amendments
   - Voting patterns and trends
   - Committee and floor votes

**API Access:**
- **Free Tier:** 30,000 requests per month
- **API Key:** Required (free registration)
- **Bulk Downloads:** Available for subscribers
- **Real-time Updates:** Daily synchronization during sessions

**Data Format:**
- **JSON API** for programmatic access
- **CSV/Excel** exports for datasets
- **SQL dumps** available for subscribers
- **RSS feeds** for bill monitoring

**What We Use:**
- Bill text and status for legislative tracking (see `scripts/legislative_tracker.py`)
- Legislator contact information for advocacy features
- Roll call votes for voting pattern analysis
- Dataset downloads for bulk legislative analysis

**Comparison with Open States:**
- **LegiScan:** More detailed bill tracking, commercial support, datasets for download
- **Open States:** Free bulk PostgreSQL dumps, open source scrapers, community-driven

Both are complementary - we use Open States for bulk data and LegiScan for detailed bill tracking and datasets.

**License:** 
- API data: Terms of Service apply (https://legiscan.com/legiscan)
- Datasets: Subscription required for bulk downloads
- API Key: Free tier available

**Use Cases:**
- Track legislation by keyword (e.g., "fluoridation", "oral health")
- Monitor bill progress across multiple states
- Analyze legislator voting patterns
- Build advocacy alerts and notifications
- Research legislative trends over time

**BibTeX:**
```bibtex
@misc{legiscan,
    title = {LegiScan: State and Federal Legislative Tracking},
    author = {{LegiScan}},
    year = {2024},
    url = {https://legiscan.com/},
    note = {Comprehensive legislative data for all 50 U.S. states and Congress}
}
```

**Documentation:** https://legiscan.com/legiscan  
**Support:** support@legiscan.com  
**Terms:** https://legiscan.com/legiscan

---

## 🌐 Data Sharing Standards

**In this section:**
- [Open Civic Data (OCD) Standards](#open-civic-data-ocd-standards)
- [Popolo Project](#popolo-project)
- [Schema.org](#schemaorg)
- [Common Education Data Standards (CEDS)](#common-education-data-standards-ceds)
- [OMOP Common Data Model (OHDSI)](#omop-common-data-model-ohdsi)

### Open Civic Data (OCD) Standards

**What we use:** Standardized jurisdiction identifiers for cross-platform compatibility.

**Standard:** [OCDEP 2 - Division Identifiers](https://open-civic-data.readthedocs.io/en/latest/proposals/0002.html)

- **Repository:** https://github.com/opencivicdata/ocd-division-ids
- **License:** Open source
- **Format:** `ocd-division/country:us/state:al/place:birmingham`
- **Coverage:** All U.S. jurisdictions (cities, counties, states, school districts)

**Example Implementation:**
```
ocd-division/country:us/state:al                      # State
ocd-division/country:us/state:al/county:jefferson     # County
ocd-division/country:us/state:al/place:birmingham     # City
ocd-division/country:us/state:al/school_district:birmingham_city  # School District
```

### Popolo Project

**What we use:** International open government data specification for people, organizations, and elected positions.

- **Specification:** https://www.popoloproject.com/
- **GitHub:** https://github.com/popolo-project/popolo-spec
- **License:** Creative Commons Attribution 4.0 International
- **Adoption:** Used by Civic Commons, OpenNorth, mySociety, Sunlight Foundation, and 30+ civic tech organizations worldwide

**Popolo Classes Implemented:**

| Popolo Class | Our Entity | Use Case |
|--------------|------------|----------|
| **Person** | LEADER | Elected officials, appointees |
| **Organization** | ORGANIZATION | Nonprofits, government agencies |
| **Membership** | LEADER ↔ ORGANIZATION | Relationships with roles and terms |
| **Post** | LEADER.position_type | Positions like "Mayor", "Council Member" |
| **VoteEvent** | VOTE | Voting records on motions/bills |
| **Motion** | AGENDA, LEGISLATION | Formal proposals |
| **Area** | JURISDICTION | Geographic/political boundaries |
| **Event** | MEETING | Public meetings with agendas |

<details>
<summary><strong>Popolo Dependencies (15 W3C/IETF Standards)</strong></summary>

| Standard | Prefix | Use Case |
|----------|--------|----------|
| [FOAF](http://xmlns.com/foaf/0.1/) | `foaf` | People, social networks |
| [vCard](https://www.rfc-editor.org/rfc/rfc6350.html) | `vcard` | Contact information (IETF RFC 6350) |
| [Schema.org](https://schema.org/) | `schema` | Structured web data |
| [DCMI Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/) | `dcterms` | Metadata, provenance |
| [W3C Organization Ontology](https://www.w3.org/TR/vocab-org/) | `org` | Organizational structures |
| [ISA Location](https://www.w3.org/ns/locn) | `locn` | Addresses, geographic data |
| [GeoNames](http://www.geonames.org/ontology/) | `gn` | Geographic identifiers |
| [SKOS](https://www.w3.org/2004/02/skos/) | `skos` | Taxonomies, classification |
| [BIO](http://purl.org/vocab/bio/0.1/) | `bio` | Life events, relationships |
| [BIBFRAME](https://www.loc.gov/bibframe/) | `bf` | Bibliographic references |
| [W3C Contact](http://www.w3.org/2000/10/swap/pim/contact#) | `con` | Contact utility concepts |
| [NEPOMUK Calendar](http://www.semanticdesktop.org/ontologies/ncal/) | `ncal` | Events, meetings |
| [ISA Person](http://www.w3.org/ns/person) | `person` | Person attributes |
| [RDF Schema](https://www.w3.org/TR/rdf-schema/) | `rdfs` | Semantic web foundation |
| [ODRS](http://schema.theodi.org/odrs) | `odrs` | Data licensing |

</details>

### Schema.org

**Organization:** W3C Community Group (sponsors: Google, Microsoft, Yahoo, Yandex)  
**What we use:** SEO-optimized structured data, JSON-LD exports, semantic web compatibility.

- **Source:** https://schema.org/
- **License:** Creative Commons Attribution-ShareAlike License (CC BY-SA 3.0)
- **Coverage:** 800+ types, 1,400+ properties

**Our Schema.org Type Mappings:**

| Our Entity | Schema.org Type | Use Case |
|------------|----------------|----------|
| JURISDICTION | [AdministrativeArea](https://schema.org/AdministrativeArea) | City/county pages |
| MEETING | [Event](https://schema.org/Event) | Google Calendar rich results |
| LEADER | [Person](https://schema.org/Person) + [GovernmentOfficial](https://schema.org/GovernmentOfficial) | Official profiles |
| ORGANIZATION | [Organization](https://schema.org/Organization) + [NGO](https://schema.org/NGO) | Nonprofit listings |
| LEGISLATION | [Legislation](https://schema.org/Legislation) | Bill tracking |
| BALLOT_MEASURE | [Legislation](https://schema.org/Legislation) | Ballot guides |
| VOTE | [VoteAction](https://schema.org/VoteAction) | Voting records |
| FACT_CHECK | [ClaimReview](https://schema.org/ClaimReview) | Google Fact Check Explorer |
| SCHOOL_DISTRICT | [EducationalOrganization](https://schema.org/EducationalOrganization) | School district info |
| VIDEO | [VideoObject](https://schema.org/VideoObject) | YouTube integration |
| DOCUMENT | [DigitalDocument](https://schema.org/DigitalDocument) | Document library |
| CONSTITUENT | [Person](https://schema.org/Person) | Donor/volunteer profiles |
| DONATION | [DonateAction](https://schema.org/DonateAction) | Donation receipts |
| CAMPAIGN | [FundingScheme](https://schema.org/FundingScheme) | Fundraising campaigns |
| PROGRAM_DELIVERY | [Service](https://schema.org/Service) | Program catalog |

**Benefits:**
- ✅ Google Search rich results
- ✅ Voice assistant compatibility (Alexa, Google Assistant)
- ✅ Knowledge Graph integration
- ✅ Cross-platform (Apple, Bing, Yandex)

### Common Education Data Standards (CEDS)

**Organization:** U.S. Department of Education, National Center for Education Statistics (NCES)  
**What we use:** School district data modeling, NCES interoperability, education finance tracking.

- **Source:** https://ceds.ed.gov/
- **GitHub:** https://github.com/CEDStandards
- **License:** Public Domain (U.S. Government)
- **Coverage:** 2,300+ data elements, 500+ option sets

**CEDS Alignment:**

| Our Field | CEDS Element ID | CEDS Element Name |
|-----------|----------------|-------------------|
| `nces_id` | 000827 | LEA Identifier (NCES) |
| `district_name` | 000168 | Name of Institution |
| `total_students` | 001475 | Student Count |
| `total_revenue` | 000612 | Total Revenue |
| `per_pupil_spending` | 000613 | Expenditure per Student |

**Benefits:**
- ✅ NCES Common Core of Data (CCD) compatibility
- ✅ F-33 Finance Survey alignment
- ✅ Federal grant reporting (ESSA, Title I, IDEA)

---

### OMOP Common Data Model (OHDSI)

**Organization:** Observational Health Data Sciences and Informatics (OHDSI)  
**What we use:** Vocabulary and terminology standardization system - CONCEPT, VOCABULARY, CONCEPT_CLASS, CONCEPT_RELATIONSHIP tables for consistent data classification.

- **Source:** https://ohdsi.github.io/CommonDataModel/
- **GitHub:** https://github.com/OHDSI/CommonDataModel
- **Vocabulary Documentation:** https://ohdsi.github.io/TheBookOfOhdsi/StandardizedVocabularies.html
- **License:** Apache License 2.0
- **Coverage:** Comprehensive vocabulary system for standardizing concepts across domains

**OMOP CDM Tables We Implement:**

| Table | Purpose | Our Use Case |
|-------|---------|-------------|
| **CONCEPT** | Master vocabulary list | Standardized codes for topics, demographics, classifications |
| **VOCABULARY** | Source vocabularies | Track origin of concepts (NTEE, FIPS, Schema.org, etc.) |
| **CONCEPT_CLASS** | Categorization | Group concepts by type (demographic, geographic, topic) |
| **CONCEPT_RELATIONSHIP** | Linkages | Map relationships between concepts (is-a, maps-to, subsumes) |

**Our OMOP-Inspired Vocabularies:**

| Vocabulary ID | Description | Concept Count |
|---------------|-------------|---------------|
| `NTEE` | National Taxonomy of Exempt Entities | 600+ |
| `FIPS` | Federal Information Processing Standards | 90,000+ |
| `Schema.org` | Structured data types | 800+ |
| `Popolo` | Open government data specs | 15+ |
| `OCD-ID` | Open Civic Data identifiers | 22,000+ |
| `CEDS` | Common Education Data Standards | 2,300+ |
| `CENSUS` | U.S. Census categories | 1,000+ |
| `INTERNAL` | Custom platform classifications | 500+ |

**Example Implementation:**
```sql
-- CONCEPT table: standardized demographics
concept_id | concept_name              | vocabulary_id | concept_class_id
-----------|---------------------------|---------------|------------------
100001     | Race: White               | CENSUS        | Demographic
100002     | Race: Black/African Amer. | CENSUS        | Demographic
100003     | Hispanic/Latino Ethnicity | CENSUS        | Demographic
100004     | Gender: Male              | CENSUS        | Demographic

-- CONCEPT_RELATIONSHIP: hierarchies
concept_id_1 | concept_id_2 | relationship_id
-------------|--------------|----------------
100002       | 100000       | Is a           # Race category
100003       | 100010       | Is a           # Ethnicity category
```

**Benefits:**
- ✅ Consistent terminology across all datasets
- ✅ Hierarchical concept relationships
- ✅ Traceable concept provenance (source vocabularies)
- ✅ Industry-standard approach used by healthcare and research institutions
- ✅ Supports multiple classification systems simultaneously

**BibTeX:**
```bibtex
@misc{ohdsi_omop_cdm,
  author = {{Observational Health Data Sciences and Informatics (OHDSI)}},
  title = {OMOP Common Data Model},
  year = {2024},
  url = {https://ohdsi.github.io/CommonDataModel/},
  license = {Apache-2.0}
}
```

---

## 🗳️ Election & Advocacy

**In this section:**
- [Ballotpedia](#ballotpedia)
- [MIT Election Data + Science Lab](#mit-election-data--science-lab)
- [OpenElections](#openelections)
- [Alabama FCPA public general reports](#alabama-fcpa-public-general-reports)

### Ballotpedia

**Organization:** Lucy Burns Institute  
**What we use:** Ballot measures, referendums, propositions for fluoridation tracking and health policy analysis.

- **Source:** https://ballotpedia.org/
- **API:** https://ballotpedia.org/API-documentation
- **Coverage:** All 50 states, historical measures back to 1990s
- **License:** API access limited at scale (paid tier available)

### MIT Election Data + Science Lab

**Organization:** Massachusetts Institute of Technology  
**What we use:** County-level election results for political composition analysis.

- **Source:** https://electionlab.mit.edu/data
- **Repository:** https://github.com/MEDSL/official-returns
- **Coverage:** 1976-present, presidential/congressional/gubernatorial results
- **License:** Free for research and commercial use

### OpenElections

**What we use:** State-by-state certified election results in standardized CSV format.

- **Source:** https://openelections.net/
- **GitHub:** https://github.com/openelections
- **Coverage:** All 50 states (various completion levels), precinct-level data
- **License:** Open source (varies by state)

### Alabama FCPA public general reports

**Organization:** Alabama Secretary of State (Fair Campaign Practices Act disclosures via Alabama Votes)  
**What we use:** Alabama **state and local campaign finance** public filings — browse and export style reports through the FCPA disclosure portal (`fcpa.alabamavotes.gov`).

- **Public general reports:** [https://fcpa.alabamavotes.gov/page.request.do?page=page.acfPublicGeneralReports](https://fcpa.alabamavotes.gov/page.request.do?page=page.acfPublicGeneralReports)
- **Portal home:** https://fcpa.alabamavotes.gov/
- **Coverage:** Alabama candidates, PACs/committees, and related disclosures as filed under Alabama law (see official site for report types and update cadence).
- **License / access:** Public government disclosure data; scraping or bulk reuse must comply with site terms of use and applicable law.

**BibTeX:**
```bibtex
@misc{alabama_fcpa_public_reports,
  author = {{Alabama Secretary of State}},
  title = {Fair Campaign Practices Act (FCPA) --- Public general reports},
  url = {https://fcpa.alabamavotes.gov/page.request.do?page=page.acfPublicGeneralReports},
  note = {Alabama campaign finance disclosure portal accessed via Alabama Votes.}
}
```

---

## 🏢 Nonprofit & Philanthropy

**In this section:**
- [IRS Exempt Organizations Business Master File (EO-BMF)](#irs-exempt-organizations-business-master-file-eo-bmf) - **PRIMARY BULK DATA SOURCE (1.9M+ orgs)**
- [Google BigQuery IRS 990 Data](#google-bigquery-irs-990-data) - **RECOMMENDED FOR BULK FORM 990 ENRICHMENT (5M+ filings)**
- [GivingTuesday 990 Data Infrastructure](#givingtuesday-990-data-infrastructure) - **AWS S3 DATA LAKE (5.4M+ raw Form 990 XMLs)**
- [ProPublica Nonprofit Explorer](#propublica-nonprofit-explorer)
- [ProPublica Congress API](#propublica-congress-api)
- [ProPublica Campaign Finance API](#propublica-campaign-finance-api)
- [ProPublica Vital Signs API](#propublica-vital-signs-api)
- [Every.org Charity API](#everyorg-charity-api)
- [Findhelp.org (Aunt Bertha)](#findhelporg-aunt-bertha)
- [211 Regional Directories](#211-regional-directories)
- [Association of Religion Data Archives (ARDA)](#association-of-religion-data-archives-arda)
- [Homeland Infrastructure Foundation-Level Data (HIFLD)](#homeland-infrastructure-foundation-level-data-hifld)
- [National Congregations Study (NCS)](#national-congregations-study-ncs)
- [Microsoft Common Data Model for Nonprofits](#microsoft-common-data-model-for-nonprofits)

### IRS Exempt Organizations Business Master File (EO-BMF)

**Organization:** Internal Revenue Service (IRS), U.S. Department of Treasury  
**What we use:** **PRIMARY BULK DATA SOURCE** for comprehensive nonprofit data - ALL 1.9M+ U.S. tax-exempt organizations with EIN, NTEE codes, financial data, subsection classification, and geographic location.

- **Source:** https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
- **Search Tool:** https://www.irs.gov/charities-non-profits/tax-exempt-organization-search
- **Bulk Downloads:** https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads
- **API Documentation:** See [IRS Bulk Data Integration](./irs-bulk-data.md)
- **Coverage:** 1,952,238 organizations (as of April 2026)
  - **Churches & Religious Organizations:** 300,000+ (NTEE codes X, X20, X21, X22, X30, X40)
  - **Health Organizations:** 80,000+ (NTEE codes E, E20-E99)
  - **Human Services:** 200,000+ (NTEE codes P, P20-P99)
  - **All Other Categories:** 1.3M+ (Education, Arts, Environment, etc.)
- **Update Frequency:** Monthly
- **License:** Public domain (U.S. government data)
- **Format:** CSV (regional files), convertible to Parquet
- **Record Count:** 1.9M+ total nonprofits across 4 regional files

**Data Fields (28 columns):**
- **Identification:** EIN, organization name, sort name
- **Location:** Street address, city, state, ZIP code
- **Classification:** NTEE code, subsection (501(c)(3), etc.), foundation code
- **Financial:** Asset amount, income amount, revenue amount
- **Status:** Tax-exempt status, deductibility status, ruling date
- **Organization:** Organization code, activity codes, group affiliation

**NTEE Codes for Churches:**
- **X** - Religion Related, Spiritual Development
- **X20** - Christian (churches, ministries)
- **X21** - Protestant
- **X22** - Roman Catholic
- **X30** - Jewish
- **X40** - Islamic

**Use Cases:**
- **Bulk Download:** Get ALL nonprofits in a state (e.g., 26,148 in Alabama vs 25 from ProPublica API)
- **Comprehensive Coverage:** 1,000x more data per request than API methods
- **Offline Analysis:** Download once, query locally forever (cached as Parquet)
- **NTEE Filtering:** Filter by category code (health, education, religion, etc.)
- **Geographic Analysis:** Complete state/city/ZIP coverage for spatial mapping

**BibTeX Citation:**
```bibtex
@misc{irs_eobmf_2026,
  title = {Exempt Organizations Business Master File Extract (EO-BMF)},
  author = {{Internal Revenue Service}},
  year = {2026},
  month = {April},
  url = {https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf},
  note = {Record count: 1,952,238 organizations. Updated monthly.}
}
```

**Integration:**
- **ProPublica API** complements with detailed Form 990 financials and mission statements
- **Every.org** adds human-readable descriptions and cause tags
- **IRS EO-BMF** provides the complete foundation layer with all organizations

**Complements:**
- **ARDA** for congregation characteristics and health ministry programs
- **HIFLD** for geospatial location data
- **National Congregations Study** for social service provision patterns
- **ProPublica API** for detailed financial breakdowns and executive compensation

---

### Google BigQuery IRS 990 Data

**Organization:** Google Cloud Platform (IRS data mirrored by Google)  
**What we use:** **RECOMMENDED FOR BULK FORM 990 ENRICHMENT** - SQL-queryable IRS Form 990 electronic filings with detailed financial data, mission statements, and program descriptions.

- **Source:** https://console.cloud.google.com/marketplace/product/internal-revenue-service/irs-990
- **Documentation:** https://cloud.google.com/bigquery/docs/irs-990-dataset
- **BigQuery Dataset:** `bigquery-public-data.irs_990`
- **Coverage:** 5,000,000+ Form 990 electronic filings (2011-present)
- **Update Frequency:** Annually (updated when IRS publishes new data)
- **License:** Public domain (U.S. government data, hosted by Google)
- **Format:** SQL-queryable tables in BigQuery
- **Cost:** Free tier includes 1 TB of queries per month

**Available Tables:**
- **`irs_990.irs_990_2013` - `irs_990.irs_990_2024`** - Individual years (2013-2024)
- **`irs_990.irs_990_ein`** - All filings aggregated by EIN
- **`irs_990.irs_990_pf_2013` - `irs_990.irs_990_pf_2024`** - Private foundation filings (Form 990-PF)

**Data Fields (100+ columns):**
- **Identification:** EIN, organization name, tax year
- **Financials:**
  - Total revenue, contributions, program service revenue, investment income
  - Total expenses, program expenses, management expenses, fundraising expenses
  - Total assets, total liabilities, net assets
  - Grants paid, grants received
- **Mission & Programs:**
  - Mission description (text field)
  - Program service accomplishments (up to 10 programs with descriptions)
  - Program service expenses per program
- **Governance:**
  - Number of voting members, independent members
  - Officer and director compensation
  - Key employee information
- **Activities:**
  - Legislative activities, political expenditures, lobbying
  - Foreign operations, foreign grants
  - Website URL
- **Compliance:**
  - Public inspection policies
  - Conflict of interest policies
  - Whistleblower policies

**Key Advantages:**
- **Serverless SQL:** Query 5M+ records without downloading files
- **Mission Extraction:** Get mission statements and program descriptions in bulk
- **Website URLs:** Extract organization websites (not in EO-BMF)
- **Historical Data:** 10+ years of financial trends per organization
- **Scalable:** Process thousands of nonprofits in a single query
- **No API Rate Limits:** Unlike ProPublica's 25-record limit

**Example Use Cases:**
- **Bulk Mission Enrichment:** Extract mission statements for all health nonprofits in Alabama
- **Website Discovery:** Get organization websites for outreach campaigns
- **Financial Trend Analysis:** Track revenue/expense trends over 10 years
- **Program Service Analysis:** Identify nonprofits by specific program keywords
- **Grant Analysis:** Find organizations that award grants vs. receive grants

**Setup Requirements:**
1. Create a Google Cloud project
2. Enable BigQuery API
3. Authenticate:
   ```bash
   # Option A: Application default credentials
   gcloud auth application-default login
   
   # Option B: Service account key
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
   ```

**Example Query (Extract Alabama Health Nonprofits with Missions):**
```sql
SELECT 
  ein,
  organization_name,
  tax_year,
  mission_description,
  website,
  total_revenue,
  total_expenses,
  program_service_expenses
FROM `bigquery-public-data.irs_990.irs_990_2023`
WHERE state = 'AL'
  AND mission_description LIKE '%health%'
  AND total_revenue > 100000
ORDER BY total_revenue DESC
LIMIT 1000
```

**BibTeX Citation:**
```bibtex
@misc{google_bigquery_irs990,
  title = {IRS 990 Dataset},
  author = {{Google Cloud Platform} and {Internal Revenue Service}},
  year = {2024},
  url = {https://console.cloud.google.com/marketplace/product/internal-revenue-service/irs-990},
  note = {BigQuery public dataset: bigquery-public-data.irs\_990. Coverage: 5M+ Form 990 electronic filings (2011-present)}
}
```

**Integration:**
- **IRS EO-BMF** provides the complete organization registry (1.9M+ orgs)
- **Google BigQuery** enriches with mission statements, websites, and detailed financials
- **ProPublica API** adds executive compensation and recent filing details
- **GivingTuesday Data Lake** provides raw XML for custom field extraction

**Complements:**
- See [Form 990 XML Data (GivingTuesday Data Lake)](./form-990-xml.md) for alternative bulk download approach
- See [IRS Bulk Data Integration](./irs-bulk-data.md) for EO-BMF foundation layer

**Cost Estimates:**
- **Free tier:** 1 TB queries/month = ~2-4 million nonprofit records
- **Beyond free tier:** $5 per TB after first 1 TB
- **Example:** Enriching 100,000 nonprofits with missions = ~20 GB = **Free**

---

### GivingTuesday 990 Data Infrastructure

**Organization:** GivingTuesday  
**What we use:** Raw Form 990 XML filings from AWS S3 for detailed financial data extraction, custom field parsing, and comprehensive nonprofit analysis.

- **Website:** https://990data.givingtuesday.org/
- **Data Lake:** `s3://gt990datalake-rawdata` (AWS S3, us-east-1 Virginia, Public Access)
- **Console:** https://us-east-1.console.aws.amazon.com/s3/buckets/gt990datalake-rawdata
- **Coverage:** 5.4M+ e-filed Form 990s (2011-present, ~300K new filings/year)
- **Scale:** ~10 TB of raw XML data
- **Update Frequency:** Ongoing (as IRS publishes new e-filings)
- **License:** Public domain (IRS data) + Open source tools
- **Access:** Free, no AWS credentials required (anonymous access via `--no-sign-request`)
- **Format:** XML files (1-2 MB each) + CSV/Parquet indices

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
| **Individual XMLs** | Single state or targeted | ~2 hrs (22K orgs) | 32 GB | 32 GB |
| **ZIP Archives** | All states / nationwide | ~6 hrs total | 38 GB | 95 GB |

**Choose Individual XMLs when:**
- You need data for 1-5 states only
- You want to download only specific EINs
- Storage space is limited
- You want incremental caching

**Choose ZIP Archives when:**
- You need all 50 states
- You're building a comprehensive database
- You have 100+ GB storage
- You want offline access to all filings

**What You Can Extract:**
- **Financials:** Revenue, expenses, assets, liabilities, net income, grants paid/received
- **Programs:** Detailed program descriptions, accomplishments, expenses per program (up to 10)
- **Governance:** Officer compensation, board members, key employees (with names and titles)
- **Activities:** Legislative activities, lobbying expenses, political contributions
- **Mission:** Organization mission statement and activity descriptions
- **Website:** Organization website URLs
- **Grants:** List of grant recipients with amounts (for grantmaking organizations)
- **Custom Fields:** Any field in the IRS Form 990 schema (990, 990-EZ, 990-PF)

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

**Python Access:**
```python
import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure anonymous S3 client
s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))

# Download individual XML
xml_obj = s3.get_object(
    Bucket='gt990datalake-rawdata',
    Key='EfileData/XmlFiles/202233259349300703_public.xml'
)
xml_content = xml_obj['Body'].read()

# Download ZIP
zip_obj = s3.get_object(
    Bucket='gt990datalake-rawdata',
    Key='EfileData/XmlZips/2023_TEOS_XML_01A.zip'
)
zip_content = zip_obj['Body'].read()
```

**Index Schema:**
The CSV index contains: `EIN`, `TaxPeriod`, `ObjectId`, `URL`, `FormType`, `OrganizationName`, `DLN`, `SubmittedOn`

**Key Advantages:**
- **Raw XML Access:** Extract ANY field from Form 990, including custom/rare fields
- **No Query Costs:** Download once, parse locally (unlike BigQuery queries)
- **Offline Processing:** Process on your own infrastructure without rate limits
- **Complete Historical Data:** All e-filed 990s since 2011
- **Batch Downloads:** Download thousands of XMLs in parallel
- **No Authentication:** Public S3 bucket (no AWS account needed)

**Use Cases:**
- **Custom Field Extraction:** Parse fields not available in BigQuery (e.g., specific schedules)
- **Bulk Enrichment:** Download and process thousands of nonprofits locally
- **Offline Analysis:** Build your own database from raw XML
- **Historical Trends:** Analyze 10+ years of financial data
- **Grant Research:** Extract detailed grant recipient lists from Form 990 Schedule I

**BibTeX Citation:**
```bibtex
@misc{givingtuesday990data,
  title = {GivingTuesday 990 Data Infrastructure},
  author = {{GivingTuesday}},
  year = {2023},
  url = {https://990data.givingtuesday.org/},
  note = {AWS S3 data lake of IRS Form 990 XML filings. Bucket: s3://gt990datalake-rawdata. Coverage: 5.4M+ filings (2011-present)}
}
```

**Integration:**
- **IRS EO-BMF** provides the complete organization registry (1.9M+ orgs)
- **GivingTuesday Data Lake** enriches with raw XML for custom parsing
- **Google BigQuery** offers SQL interface for standard fields
- **ProPublica API** adds web-friendly access for individual lookups

**Complements:**
- See [Form 990 XML Data (GivingTuesday Data Lake)](./form-990-xml.md) for detailed integration guide
- See [Form 990 Enrichment Guide](../guides/form-990-enrichment.md) for usage examples
- See [IRS Bulk Data Integration](./irs-bulk-data.md) for EO-BMF foundation layer

**Attribution:**
When publishing analyses using this data, please cite:
1. GivingTuesday 990 Data Infrastructure: https://990data.givingtuesday.org/
2. Our enrichment tools: https://github.com/getcommunityone/open-navigator-for-engagement

---

### ProPublica Nonprofit Explorer

**Organization:** ProPublica, Inc.  
**What we use:** Enhanced financial data and detailed Form 990 filings to complement IRS EO-BMF bulk data.

- **Source:** https://projects.propublica.org/nonprofits/
- **API Documentation:** https://projects.propublica.org/nonprofits/api
- **Coverage:** 3,000,000+ organizations, 10+ years of historical data
- **Data Included:**
  - Total revenue, expenses, assets, liabilities
  - Executive compensation (top 5 highest paid)
  - Program service expenses vs. administrative overhead
  - NTEE classification codes (National Taxonomy of Exempt Entities)
  - EIN (Employer Identification Number) for verification
- **Rate Limits:** Free, unlimited access (respectful use recommended: ~1 req/sec)
- **API Limitation:** Returns max 25 results per request, no pagination (use IRS EO-BMF for bulk downloads)
- **License:** Free for research and commercial use

**BibTeX:**
```bibtex
@misc{propublica_nonprofits,
  author = {{ProPublica}},
  title = {Nonprofit Explorer},
  year = {2024},
  url = {https://projects.propublica.org/nonprofits/},
  note = {Accessed: 2024}
}
```

---

### ProPublica Congress API

**Organization:** ProPublica, Inc.  
**What we use:** Legislative data including roll-call votes, member information, bills, and congressional activity to link policy decisions to government meetings.

- **Source:** https://projects.propublica.org/api-docs/congress-api/
- **API Documentation:** https://projects.propublica.org/api-docs/congress-api/
- **Coverage:** U.S. Congress data from 102nd Congress (1991) to present
- **Data Included:**
  - Roll-call votes by member and bill
  - Bill information, status, and amendments
  - Member biographical data and voting records
  - Committee assignments and leadership
  - Congressional statements and floor appearances
- **Access:** **API Key Required** (Free - sign up at https://www.propublica.org/datastore/api/propublica-congress-api)
- **Authentication:** Include as HTTP header: `X-API-Key: YOUR_API_KEY`
- **Rate Limits:** 5,000 requests per day
- **License:** Free for non-commercial and commercial use with attribution

**Use Cases:**
- Link local government meetings to federal legislation
- Track how elected officials vote on issues discussed locally
- Correlate campaign contributions with voting patterns

**BibTeX:**
```bibtex
@misc{propublica_congress,
  author = {{ProPublica}},
  title = {Congress API},
  year = {2024},
  url = {https://projects.propublica.org/api-docs/congress-api/},
  note = {Accessed: 2024}
}
```

---

### Federal Election Commission (FEC) - Bulk Data & OpenFEC API

**Organization:** Federal Election Commission (FEC), U.S. Government  
**What we use:** **PRIMARY SOURCE** for campaign finance data - individual contributions, candidate filings, committee data, and political expenditures for comprehensive campaign finance analysis.

- **OpenFEC API:** https://api.open.fec.gov/developers/
- **Bulk Data Portal:** https://www.fec.gov/data/browse-data/?tab=bulk-data
- **Documentation:** https://www.fec.gov/campaign-finance-data/
- **Coverage:** Complete FEC data from 1980s to present (updated nightly)
- **Data Included:**
  - **Individual contributions** $200+ (Schedule A)
  - **Operating expenditures** (Schedule B)
  - **Candidate master files** (House, Senate, Presidential)
  - **Committee master files** (PACs, Super PACs, party committees)
  - **Campaign finance totals** by election cycle
  - **Independent expenditures** and electioneering communications
- **Access Methods:**
  - **Bulk Downloads:** Free, unlimited, no API key (CSV and FEC format)
  - **OpenFEC API:** Free with API key (1,000 requests/hour)
  - **Demo Key:** 30 requests/hour (no registration)
- **API Key:** Free at https://api.data.gov/signup/
- **License:** Public Domain (U.S. Government)
- **Update Frequency:** Nightly (most datasets)

**Use Cases:**
- Map donor networks and political influence patterns
- Link nonprofit leadership donations to policy decisions
- Track campaign finance in health advocacy organizations
- Analyze funding sources for ballot initiatives
- Cross-reference contributions with government grant awards
- "Follow the money" from donor to policy outcome

**Critical Policy Restriction:**
- ⚠️ **Cannot use contributor data for commercial solicitation or fundraising**
- FEC data is for transparency and research, not marketing

**BibTeX:**
```bibtex
@misc{fec_data_2024,
  author = {{Federal Election Commission}},
  title = {Campaign Finance Data and Bulk Downloads},
  year = {2024},
  url = {https://www.fec.gov/data/},
  note = {Updated nightly. Accessed: 2024}
}

@misc{openfec_api_2024,
  author = {{Federal Election Commission}},
  title = {OpenFEC API},
  year = {2024},
  url = {https://api.open.fec.gov/developers/},
  note = {RESTful API for campaign finance data. Accessed: 2024}
}
```

**Integration:** `discovery/fec_integration.py`

---

### ProPublica Campaign Finance API

**Organization:** ProPublica, Inc.  
**What we use:** Simplified access to FEC data with pre-aggregated summaries and top donor analysis (complements direct FEC data access).

- **Source:** https://projects.propublica.org/api-docs/campaign-finance/
- **API Documentation:** https://projects.propublica.org/api-docs/campaign-finance/
- **Coverage:** FEC data from 2000 election cycle to present
- **Data Included:**
  - Candidate financial summaries and filings
  - Committee information and contributions
  - Individual and organizational donor data
  - Independent expenditures and disbursements
  - Top donors by industry and geography
- **Access:** **API Key Required** (Free - sign up at https://www.propublica.org/datastore/api/campaign-finance-api)
- **Authentication:** Include as HTTP header: `X-API-Key: YOUR_API_KEY`
- **Rate Limits:** 5,000 requests per day
- **License:** Free for non-commercial and commercial use with attribution

**Note:** ProPublica API provides easier-to-use summaries of FEC data. For bulk analysis, use FEC Bulk Downloads directly.

**Use Cases:**
- Quick lookups of candidate finance summaries
- Pre-aggregated top donor analysis
- Industry contribution patterns
- Journalist-friendly data formatting

**BibTeX:**
```bibtex
@misc{propublica_campaign_finance,
  author = {{ProPublica}},
  title = {Campaign Finance API},
  year = {2024},
  url = {https://projects.propublica.org/api-docs/campaign-finance/},
  note = {Accessed: 2024}
}
```

---

### ProPublica Vital Signs API

**Organization:** ProPublica, Inc.  
**What we use:** Healthcare provider data including doctors, facilities, disciplinary actions, and Medicare participation to support oral health policy analysis.

- **Source:** https://projects.propublica.org/vital-signs/
- **API Documentation:** https://projects.propublica.org/api-docs/vital-signs/
- **Coverage:** 1,000,000+ healthcare providers across the United States
- **Data Included:**
  - Doctor biographical information and specialties
  - Medical school and residency training
  - Hospital affiliations and group practices
  - State medical board disciplinary actions
  - Medicare participation and payments
  - Malpractice claims and settlements
- **Access:** **API Key Required** (Free - sign up at https://www.propublica.org/datastore/api/vital-signs-api)
- **Authentication:** Include as HTTP header: `X-API-Key: YOUR_API_KEY`
- **Rate Limits:** 5,000 requests per day
- **License:** Free for non-commercial and commercial use with attribution

**Use Cases:**
- Map dental care access and provider availability
- Link health policy discussions to provider networks
- Identify healthcare deserts and underserved areas
- Track quality metrics for oral health providers
- Correlate public health outcomes with provider density

**BibTeX:**
```bibtex
@misc{propublica_vital_signs,
  author = {{ProPublica}},
  title = {Vital Signs: Health Care Provider Data},
  year = {2024},
  url = {https://projects.propublica.org/vital-signs/},
  note = {Accessed: 2024}
}
```

---

### Every.org Charity API

**Organization:** Every.org (Public Benefit Corporation)  
**What we use:** Human-readable mission statements, organization logos, cause categories, cleaner metadata than raw IRS filings.

- **API Documentation:** https://www.every.org/nonprofit-api
- **Coverage:** 1,000,000+ verified nonprofits
- **Data Included:**
  - Mission statements and descriptions
  - Organization logos and images
  - Cause tags (health, education, environment, etc.)
  - Social media links
- **Access:** API key required (free tier available)
- **License:** API Terms of Service

---

### Findhelp.org (Aunt Bertha)

**Organization:** Findhelp (formerly Aunt Bertha)  
**What we use:** Comprehensive directory of local social services - specific programs, hours, eligibility requirements, contact information.

- **Source:** https://www.findhelp.org/
- **Coverage:** 400,000+ community programs across the United States
- **Data Included:**
  - Program descriptions and services offered
  - Days/hours of operation
  - Eligibility requirements
  - Languages spoken
  - Insurance accepted
  - Contact information (phone, email, address)
- **Access:** Public search available, API access by request
- **Use Case:** Manual enrichment of ProPublica financial data with service delivery details

**Example:** https://www.findhelp.org/search?query=dental&location=Tuscaloosa,%20AL

---

### 211 Regional Directories

**What we use:** Regional social services directories with detailed program information, crisis hotlines, local resources.

- **Source:** https://www.211.org/ (national network)
- **Example:** https://www.211connects.org (Alabama)
- **Coverage:** Local services in most U.S. cities and counties
- **Data Included:**
  - Specific services and programs
  - Hours of operation
  - Eligibility criteria
  - Languages and accessibility
- **Access:** Public search, some regions offer data partnerships
- **License:** Varies by region

---

### Association of Religion Data Archives (ARDA)

**Organization:** Pennsylvania State University  
**What we use:** U.S. Congregational Life Survey and denominational data for understanding church characteristics, programs, and community services including health ministries.

- **Source:** https://www.thearda.com/
- **Data Portal:** https://www.thearda.com/data-archive
- **U.S. Congregational Life Survey:** https://www.thearda.com/Archive/Files/Descriptions/USCONGLIFE.asp
- **Coverage:** 300,000+ congregations with detailed program data
- **License:** Free for research and non-commercial use

**Key Datasets:**

| Dataset | Coverage | Variables |
|---------|----------|----------|
| **U.S. Congregations** | All denominations, 50 states | Congregation size, programs, community services |
| **Religious Congregations & Membership Study** | County-level data | Adherents, congregations by denomination |
| **National Congregations Study** | Representative sample of 1,200+ | Worship, programs, social services |

**What We Extract:**
- Congregation size and attendance
- Health ministry programs (dental, medical, mental health)
- Food programs and community meals
- Youth and senior programs
- Community outreach budget
- Social service partnerships

**Example Use Case:**  
Identify churches with active health ministries in Tuscaloosa, AL that provide free dental kits, health screenings, or partner with mobile dental units.

**Citation:**
```bibtex
@misc{arda_congregations,
  author = {{Association of Religion Data Archives}},
  title = {U.S. Congregational Life Survey},
  year = {2024},
  publisher = {Pennsylvania State University},
  url = {https://www.thearda.com/},
  note = {Free for research use}
}
```

---

### Homeland Infrastructure Foundation-Level Data (HIFLD)

> **⚠️ 2026 Update:** The HIFLD Open portal (hifld-geoplatform.opendata.arcgis.com) has been officially sunsetted. Data has migrated to the Data Rescue Project (portal.datarescueproject.org), ArcGIS Online mirrors, and USGS re-indexing.

**Organization:** U.S. Department of Homeland Security (DHS)  
**What we use:** Geospatial databases of critical infrastructure and community resources for mapping service locations and identifying gaps.

- **Legacy Source:** ~~https://hifld-geoplatform.opendata.arcgis.com/~~ (Sunset)
- **New Sources:** 
  - https://portal.datarescueproject.org/ (Rescued datasets)
  - https://www.arcgis.com (Re-indexed datasets)
- **Format:** Shapefile, GeoJSON, CSV, Parquet
- **License:** Public Domain (U.S. Government)

**Currently Loaded (2026):**

| Infrastructure Type | Item ID | Record Count | Portal | Status |
|---------------------|---------|--------------|--------|--------|
| **Places of Worship** | `495cc33ef490462ab2d8933247a66a87` | 254,742 | ArcGIS Online | ✅ Loaded |
| **Hospitals** | `f36521f6e07f4a859e838f0ad7536898` | 7,496 | ArcGIS Online | ✅ Loaded |
| **Law Enforcement** | `333a74c8e9c64cb6870689d31e8836af` | 46,972 | ArcGIS Online | ✅ Loaded |

**Available but Not Yet Loaded:**

| Infrastructure Type | Identifier | Portal | Status |
|---------------------|------------|--------|--------|
| **Public Schools** | `hifld-open-public-schools` | Data Rescue | ⚠️ Requires different API |
| **Private Schools** | `hifld-open-private-schools` | Data Rescue | ⚠️ Requires different API |
| **Fire Stations** | `d33b8b5d03a84170847b48d7d4c1bdf6` | ArcGIS Online | ⚠️ Dataset format incompatible |
| **Courthouses** | `f4007823f38c4b12b508f7b76400c0a9` | ArcGIS Online | 🔍 Proxy for gov buildings |

**How to Find Item IDs (2026):**
1. **ArcGIS Online**: Search https://www.arcgis.com/home/search.html for "HIFLD [dataset name]"
2. Click on the dataset
3. The Item ID is in the URL: `https://www.arcgis.com/home/item.html?id=ITEM_ID_HERE`
4. **Data Rescue Project**: Visit https://portal.datarescueproject.org/ (uses slug identifiers, not Item IDs)

**Common Fields Across Datasets:**
- NAME - Facility name
- ADDRESS - Street address
- CITY, STATE, ZIP - Location details
- LATITUDE, LONGITUDE - Precise geolocation
- TYPE - Facility type/category
- TELEPHONE - Contact phone
- WEBSITE - Organization website

**Use Cases:**
1. **Map service providers** - Overlay infrastructure on jurisdiction maps
2. **Identify service deserts** - Find areas underserved by critical facilities
3. **Route mobile services** - Plan stops at schools, churches, or community centers
4. **Partnership outreach** - Locate facilities for collaboration opportunities
5. **Emergency planning** - Understand infrastructure distribution

**Automated Download (ArcGIS Online datasets):**
```bash
# Download Places of Worship (254,742 records)
python scripts/datasources/hifld/download_arcgis_dataset.py \
  --item-id 495cc33ef490462ab2d8933247a66a87 \
  --to-parquet

# Download Hospitals (7,496 records)
python scripts/datasources/hifld/download_arcgis_dataset.py \
  --item-id f36521f6e07f4a859e838f0ad7536898 \
  --to-parquet

# Download Law Enforcement (46,972 records)
python scripts/datasources/hifld/download_arcgis_dataset.py \
  --item-id 333a74c8e9c64cb6870689d31e8836af \
  --to-parquet

# Load all downloaded datasets to PostgreSQL
python scripts/datasources/hifld/load_hifld_to_postgres.py
```

**Data Rescue Project datasets** (Public/Private Schools) require a different download approach and are not yet supported by the automated scripts.

**Dependencies:**
```bash
pip install arcgis geopandas loguru
```

**Citation:**
> "Homeland Infrastructure Foundation-Level Data (HIFLD). U.S. Department of Homeland Security. https://hifld-geoplatform.opendata.arcgis.com/"

**Dataset-Specific Citations:**
```
# Law Enforcement
"HIFLD: Local Law Enforcement Locations. U.S. Department of Homeland Security. Accessed via ArcGIS Online and Data Rescue Project, 2026."

**Dataset-Specific Citations:**
```
# Places of Worship (254,742 locations)
"HIFLD: All Places of Worship. U.S. Department of Homeland Security. 
https://www.arcgis.com/home/item.html?id=495cc33ef490462ab2d8933247a66a87"

# Hospitals (7,496 locations)
"HIFLD: Hospitals. U.S. Department of Homeland Security. 
https://www.arcgis.com/home/item.html?id=f36521f6e07f4a859e838f0ad7536898"

# Law Enforcement (46,972 locations)
"HIFLD: Local Law Enforcement Locations. U.S. Department of Homeland Security. 
https://www.arcgis.com/home/item.html?id=333a74c8e9c64cb6870689d31e8836af

### National Congregations Study (NCS)

**Organization:** Duke University  
**What we use:** Representative survey of U.S. congregations to understand social service provision, health programs, and civic engagement patterns.

- **Source:** https://sites.duke.edu/ncsweb/
- **Principal Investigator:** Mark Chaves, Duke University Divinity School
- **Coverage:** 1,200+ congregations (representative sample)
- **Waves:** 1998, 2006-07, 2012, 2018-19
- **License:** Free for academic and research use

**Key Findings:**
- **60% of congregations** provide social services (food, housing, health)
- **15% of congregations** have health-related programs
- **Large urban churches** (500+ attendees) more likely to have formal health ministries
- **25% collaborate** with clinics, hospitals, or health departments

**Variables We Use:**

| Variable | Description | Relevance |
|----------|-------------|-----------|
| `HLTHPROG` | Has health-related program | Health ministry presence |
| `FOODPROG` | Operates food program | Nutrition education opportunity |
| `YOUTHPROG` | Youth programs | Reach children for dental education |
| `SENIORPROG` | Senior programs | Medicare enrollment help |
| `PARTNERSHIP` | Partners with nonprofits | Collaboration potential |

**Citation:**
```bibtex
@misc{ncs_2018,
  author = {Chaves, Mark and Anderson, Shawna},
  title = {National Congregations Study: Cumulative Dataset (1998, 2006-07, 2012, 2018-19)},
  year = {2020},
  publisher = {Duke University},
  url = {https://sites.duke.edu/ncsweb/},
  doi = {10.1093/soc/swaa029}
}
```

---

### Microsoft Common Data Model for Nonprofits

**Organization:** Microsoft Corporation  
**What we use:** Nonprofit data standardization, constituent relationship management, donor tracking, program outcome measurement.

- **Repository:** https://github.com/microsoft/Nonprofits/tree/master/CommonDataModelforNonprofits
- **ERD Documentation:** [common-data-model-for-nonprofits-erds.pdf](https://github.com/microsoft/Nonprofits/blob/master/CommonDataModelforNonprofits/Documents/common-data-model-for-nonprofits-erds.pdf)
- **License:** MIT License
- **Coverage:** Donor management, fundraising, program delivery, volunteer management, impact measurement

**Microsoft CDM Entities Implemented:**

| Microsoft CDM Entity | Our Entity | Description |
|---------------------|------------|-------------|
| Constituent | CONSTITUENT | Donors, volunteers, members, beneficiaries |
| Donation | DONATION | Financial contributions and in-kind gifts |
| Campaign | CAMPAIGN | Fundraising campaigns and appeals |
| Designation | DESIGNATION | Fund allocation (unrestricted, restricted, endowment) |
| Membership | MEMBERSHIP | Member enrollment and renewals |
| Volunteer Preference | VOLUNTEER_ACTIVITY | Volunteer hours and activities |
| Delivery Framework | PROGRAM_DELIVERY | Programs and services delivered |
| Objective | PROGRAM_OUTCOME | Measurable impact and KPIs |

**Integration Benefits:**
- ✅ Dynamics 365 Nonprofit compatibility
- ✅ Power Platform (Power BI, Power Apps, Power Automate)
- ✅ Azure Synapse analytics
- ✅ Constituent 360 view

---

## ✅ Fact-Checking

**In this section:**
- [Google Fact Check Tools API](#google-fact-check-tools-api)
- [FactCheck.org](#factcheckorg)
- [PolitiFact](#politifact)

### Google Fact Check Tools API

**Organization:** Google LLC  
**What we use:** Aggregated fact-checking data for verifying claims from meetings and legislation.

- **Source:** https://toolbox.google.com/factcheck/explorer
- **API:** https://developers.google.com/fact-check/tools/api
- **Schema:** https://developers.google.com/search/docs/appearance/structured-data/factcheck
- **Coverage:** 100+ fact-checking organizations worldwide
- **License:** Free API (10,000 queries/day quota)

### FactCheck.org

**Organization:** Annenberg Public Policy Center, University of Pennsylvania  
**What we use:** Nonpartisan fact-checking of political claims and health policy verification.

- **Source:** https://www.factcheck.org/
- **Coverage:** National politics, health claims, science, viral content (2003-present)
- **License:** Free (web scraping allowed with rate limiting)

### PolitiFact

**Organization:** Poynter Institute (Pulitzer Prize-winning)  
**What we use:** State-level fact-checking, Truth-O-Meter ratings for ballot measures.

- **Source:** https://www.politifact.com/
- **Coverage:** All 50 states, federal politics (2007-present)
- **Rating Scale:** True, Mostly True, Half True, Mostly False, False, Pants on Fire
- **License:** Free (web scraping allowed with rate limiting)

---

## 💻 Civic Tech & Open Source

**In this section:**
- [Investigative OSINT & anti-corruption toolkit](#investigative-osint--anti-corruption-toolkit)
- [Cloud & Data Platforms](#cloud--data-platforms)
- [Civic Tech Field Guide](#civic-tech-field-guide)
- [Code for America: Brigade Network](#code-for-america-brigade-network)
- [U.S. Digital Response (USDR)](#us-digital-response-usdr)
- [Digital Public Goods Alliance (DPGA)](#digital-public-goods-alliance-dpga)

### Investigative OSINT & anti-corruption toolkit

Investigative journalism networks (for example **ICIJ** on the Panama Papers and **OCCRP** on cross-border corruption) rely on an ecosystem of open-source tools—not a single “anti-corruption app”—to connect **meeting notes, campaign finance, property records, and charities**. Open Navigator’s cross-dataset work (entity resolution, graph views, meeting NLP) aligns with this stack.

**Core challenge:** **Entity resolution**—ensuring “John Smith” the developer, “J. Smith” the donor, and “Johnny Smith” on a charity board are the same person (or confidently not).

**Recommended pipeline (do not rebuild from scratch):**

```
[Meeting notes / bills]  →  ICIJ Datashare  →  NER / searchable text     ┐
[Donations & charities]  →  Splink          →  probabilistic name match  ├──  Neo4j / NetworkX
[Property & assessor]    →  Benford / outliers → valuation spikes         ┘
                              (followthemoney schema)
```

| Tool | Repository | What it does | When to cite |
| --- | --- | --- | --- |
| **Splink** | [moj-analytical-services/splink](https://github.com/moj-analytical-services/splink) | Probabilistic record linkage (Fellegi–Sunter); dedupe and link messy names/addresses across tables without shared IDs | Property rolls × donors × charity boards |
| **Aleph** | [alephdata/aleph](https://github.com/alephdata/aleph) | OCCRP’s investigation platform: ingest, search, and cross-reference document and entity collections | Document-heavy corruption probes |
| **Follow the Money** | [alephdata/followthemoney](https://github.com/alephdata/followthemoney) | Data model for anti-corruption entities (Person, Company, Land, Interest, Donation) | Structuring heterogeneous feeds before graph export |
| **Datashare** | [ICIJ/datashare](https://github.com/ICIJ/datashare) | ICIJ document analysis: OCR on PDFs, entity extraction, full-text search over large troves | Meeting minutes, legislation, scanned packets |
| **Grano** | [ANCIR/grano](https://github.com/ANCIR/grano) | ANCIR toolkit for mapping political and economic influence networks | Influence / lobbying style graphs |
| **Datashare → Neo4j** | [ICIJ/datashare-extension-neo4j](https://github.com/ICIJ/datashare-extension-neo4j) | Exports Datashare entities into Neo4j for traversable graphs | “Short path” queries between meetings and money |
| **NetworkX** | [networkx/networkx](https://github.com/networkx/networkx) | Python graph algorithms: centrality, community detection, path analysis | Hub officials, collusive clusters |
| **ProACT** | [INTVP/proACT](https://github.com/INTVP/proACT) | World Bank–linked procurement transparency platform; includes reusable anomaly scripts (e.g. Benford) | Transferable math for donations / valuations |
| **Canary** | [CanaryInAMine/Canary](https://github.com/CanaryInAMine/Canary) | Data-journalism accountability tool for fraud/anomaly patterns in public records | Public-records screening |

**Query pattern (after linking):** Push linked entities into **Neo4j** using **followthemoney**-style types, then run **Cypher** for short paths between **policy events** (votes, zoning, contracts) and **private enrichment** (donations, property transfers, charity flows).

**Open Navigator overlap:** Meeting transcripts and policy JSON (`decisions[]`, `people[]`, `places[]`), FEC / nonprofit bronze, assessor and parcel discovery (OpenAddresses), and jurisdiction graphs are inputs to the same pipeline—CommunityOne is the **local-government meeting layer**; Splink/Aleph/Neo4j are the **cross-agency glue**.

**Hackathon pitches:** See [Hackathon video submission ideas — OSINT pipeline](../guides/hackathon-video-submission-ideas.md#cross-dataset-corruption-investigation-osint-pipeline) and [fraud tracks](../guides/hackathon-video-submission-ideas.md#fraud-and-conflict-of-interest-hackathon-ideas-master-list).

**License note:** Each repository has its own license (often Apache-2.0 or similar); cite the **tool paper/site**, the **GitHub repo**, and any **journalistic investigation** that motivated your use.

---

### Cloud & Data Platforms

**Organization:** Microsoft Corporation / GitHub, Inc.  
**What we use:** GitHub REST and GraphQL APIs for tracking civic tech projects, hackathons, contributors, and open source development.

- **Source:** https://docs.github.com/en/rest
- **GraphQL API:** https://docs.github.com/en/graphql
- **Rate Limits:** 5,000 requests/hour (authenticated)
- **License:** Free (API usage subject to GitHub Terms of Service)

**Data Extracted:**

| Dataset | Description | Fields Tracked |
|---------|-------------|----------------|
| `github_repositories` | Civic tech projects and repos | name, stars, forks, topics, language, license |
| `contributors` | Project maintainers and contributors | login, contributions, role, github_sponsor_enabled |
| `project_issues` | Good first issues, help wanted | labels, state, title, created_at |
| `project_funding` | GitHub Sponsors, OpenCollective | funding_type, sponsor_count, monthly_amount |
| `hackathon_projects` | Projects built at civic hackathons | hackathon_id, project_name, repo_url, demo_url |

**Civic Tech Topics Tracked:**
- `civic-tech`, `open-government`, `government-transparency`
- `public-data`, `open-data`, `civic-engagement`
- `democracy`, `accountability`, `policy-analysis`

**Why GitHub API:**
- **Discovery:** Find civic tech projects and open source tools
- **Collaboration:** Track contributors and maintainers
- **Opportunities:** Surface "good first issue" labels for new contributors
- **Funding:** Identify projects needing financial support
- **Hackathons:** Document projects built at civic hackathon events

**Implementation:**
```python
# Our platform uses:
- /civic_tech/github_repositories  # Project metadata
- /civic_tech/contributors         # Maintainer info
- /civic_tech/project_issues       # Contribution opportunities
- /civic_tech/project_funding      # Financial support
- /civic_tech/hackathon_projects   # Hackathon outputs
```

**Citation:**
```bibtex
@misc{github_api,
  author = {{GitHub, Inc.}},
  title = {GitHub REST API and GraphQL API},
  year = {2024},
  url = {https://docs.github.com/en/rest},
  note = {API for accessing repository data, issues, contributors, and project metadata}
}
```

---

### Civic Tech Field Guide

**Organization:** Compiler LA  
**What we use:** Curated directory of 1,000+ civic technology projects categorized by issue area and impact.

- **Source:** https://civictech.guide/
- **Dataset:** https://airtable.com/shr8yfQ5p3CJGMnCs/tblv0VlP8vVGIBYI6
- **Format:** CSV, Airtable API
- **License:** Open Database License (ODbL)

**Categories:**
- Democracy & Voting
- Environment & Climate
- Housing & Homelessness
- Criminal Justice
- Education
- Health & Safety
- Economic Justice
- Infrastructure

**Notable Projects Catalogued:**
- OpenBudget Oakland (Budget transparency)
- Food Oasis (Food access mapping)
- Health Equity Tracker (CDC data visualization)
- City Scrapers (Meeting minutes automation)
- Documenters Network (Public meeting coverage)

**Why Civic Tech Field Guide:**
- **Taxonomy:** Standardized categorization of civic tech projects
- **Discovery:** Find existing tools before building new ones
- **Inspiration:** Learn from successful civic tech implementations
- **Collaboration:** Connect with project maintainers

**Citation:**
```bibtex
@misc{civic_tech_field_guide,
  author = {{Compiler LA}},
  title = {Civic Tech Field Guide},
  year = {2024},
  url = {https://civictech.guide/},
  note = {Curated directory of 1,000+ civic technology projects}
}
```

---

### Code for America: Brigade Network

**Organization:** Code for America  
**What we use:** Brigade chapter locations, hackathon events, and civic tech projects built by local volunteer groups.

- **Source:** https://brigade.codeforamerica.org/
- **Brigades:** https://brigade.codeforamerica.org/brigades
- **Projects:** https://brigade.codeforamerica.org/projects
- **License:** Public information, project-specific licenses vary

**Brigade Network:**
- **80+ active brigades** across the United States
- Monthly civic hack nights and community meetups
- Annual **National Day of Civic Hacking**
- **CodeAcross** weekend hackathons

**Notable Brigade Projects:**

| Project | Brigade | Impact |
|---------|---------|--------|
| **OpenBudget Oakland** | Code for Oakland | Budget transparency & visualization |
| **Food Oasis** | Hack for LA | Map food resources (300+ locations) |
| **Health Equity Tracker** | Code for America | CDC health disparities data |
| **BallotNav** | National | Ballot drop-off location finder |
| **Documenters** | City Bureau (Chicago) | Public meeting coverage network |

**Hackathon Events Tracked:**

| Event | Frequency | Focus |
|-------|-----------|-------|
| **National Day of Civic Hacking** | Annual (June) | Nationwide simultaneous hackathons |
| **CodeAcross** | Annual (February) | Local government collaboration |
| **Monthly Hack Nights** | Monthly | Ongoing project development |

**Brigade Data in Our Platform:**
```python
# We track:
- /civic_tech/brigade_chapters      # 80+ locations with contact info
- /civic_tech/hackathons            # Events: CodeAcross, NDoCH
- /civic_tech/hackathon_projects    # Projects built at events
- /civic_tech/hackathon_participants # Contributors and attendees
```

**Citation:**
```bibtex
@misc{code_for_america_brigade,
  author = {{Code for America}},
  title = {Brigade Network: Volunteer Civic Technology},
  year = {2024},
  url = {https://brigade.codeforamerica.org/},
  note = {80+ local volunteer groups building civic technology}
}
```

---

### U.S. Digital Response (USDR)

**Organization:** U.S. Digital Response  
**What we use:** Emergency civic tech projects and rapid-response open source tools for government needs.

- **Source:** https://www.usdigitalresponse.org/
- **Projects:** https://github.com/usdigitalresponse
- **License:** Varies by project (mostly MIT, Apache 2.0)

**Key Projects:**

| Project | Purpose | Tech Stack |
|---------|---------|------------|
| **grants-ingest** | Federal grant opportunity aggregation | Python, PostgreSQL |
| **usdr-gost** | Grant opportunity management system | TypeScript, React |
| **cpf-reporter** | Compliance reporting automation | Node.js |

**Focus Areas:**
- **COVID-19 Response:** Vaccine distribution, testing sites
- **Emergency Management:** Disaster response coordination
- **Grants & Funding:** Grant opportunity discovery
- **Government Modernization:** UI/UX improvements for gov services

**Why USDR:**
- **Rapid Response:** Builds tools during emergencies
- **Open Source:** All code publicly available
- **Government Partnership:** Works directly with agencies
- **Reusable Tools:** Solutions applicable to multiple jurisdictions

**Citation:**
```bibtex
@misc{us_digital_response,
  author = {{U.S. Digital Response}},
  title = {Open Source Civic Technology for Emergency Response},
  year = {2024},
  url = {https://www.usdigitalresponse.org/},
  note = {Rapid-response civic tech projects for government needs}
}
```

---

### Digital Public Goods Alliance (DPGA)

**Organization:** United Nations Development Programme (UNDP), Norway, Sierra Leone, Germany  
**What we use:** Registry of 500+ Digital Public Goods (DPGs) certified as open source projects meeting UN Sustainable Development Goals.

- **Source:** https://digitalpublicgoods.net/
- **Registry:** https://digitalpublicgoods.net/registry/
- **Standard:** https://digitalpublicgoods.net/standard/
- **License:** CC0 1.0 Universal (registry data)

**DPG Standard Requirements:**
1. ✅ **Open License:** OSI-approved, Creative Commons
2. ✅ **Open Source:** Public code repositories
3. ✅ **Documentation:** Clear usage instructions
4. ✅ **Privacy & Security:** Data protection mechanisms
5. ✅ **Standards:** Adheres to relevant standards
6. ✅ **SDG Alignment:** Supports UN Sustainable Development Goals

**Notable Digital Public Goods:**

| DPG | Category | Impact |
|-----|----------|--------|
| **OpenStreetMap** | Geographic data | Global collaborative mapping |
| **DHIS2** | Health information | Used in 100+ countries |
| **Open Food Network** | Food systems | Local food marketplace platform |
| **Ushahidi** | Crisis response | Crowdsourced incident reporting |
| **Khan Academy** | Education | Free online learning platform |

**Why DPGA:**
- **Certification:** Vetted open source projects
- **SDG Alignment:** Projects tied to development goals
- **Sustainability:** Focus on long-term viability
- **Global Impact:** International collaboration

**Our Use Case:**
```python
# We track DPG-certified civic tech projects:
- /civic_tech/github_repositories (dpg_certified = true)
- /civic_tech/project_metadata (sdg_goals = [...])
```

**Citation:**
```bibtex
@misc{digital_public_goods_alliance,
  author = {{Digital Public Goods Alliance}},
  title = {Digital Public Goods Registry},
  year = {2024},
  url = {https://digitalpublicgoods.net/},
  note = {500+ open source projects certified as Digital Public Goods}
}
```

---

## 🌟 Community Solutions & Use Cases

**In this section:**
- [Spectrum of Community Engagement to Ownership](#spectrum-of-community-engagement-to-ownership)
- [Harvard Ash Center: Data-Smart City Solutions (Archived)](#harvard-ash-center-data-smart-city-solutions-archived)
- [Brookings Institution: Data-Driven Policymaking](#brookings-institution-data-driven-policymaking)
- [Reason Foundation](#reason-foundation)
- [Open Data Impact: Evidence-Based Research](#open-data-impact-evidence-based-research)
- [Tableau Data Equity Hub (Salesforce Data for Good)](#tableau-data-equity-hub-salesforce-data-for-good)
- [PolicyMap](#policymap)

### Spectrum of Community Engagement to Ownership

**Organization:** Facilitating Power, Rosa González  
**What we use:** Framework for community-driven governance that maps to our data structure (nonprofits, jurisdictions, grants, officials).

- **Source:** https://movementstrategy.org/
- **Framework:** https://movementstrategy.org/b/wp-content/uploads/2021/08/Spectrum-of-Community-Engagement-to-Ownership.pdf
- **Article:** "From Community Engagement to Ownership"
- **License:** Creative Commons (educational use)

**The Spectrum Framework - Four Key Sectors:**

| Sector | Maps to Our Data | Community Role |
|--------|------------------|----------------|
| **Community-Based Organizations** | `/nonprofits` | Grassroots leadership, lived experience |
| **City/County Staff** | `/jurisdictions` | Government accountability, service delivery |
| **Philanthropic Partners** | `/grants` | Resource allocation, funding equity |
| **Facilitative Leaders** | `/officials` | Elected officials, decision makers |

**Engagement Levels:**
1. **Inform** → One-way communication
2. **Consult** → Gather input, government decides
3. **Involve** → Work together on solutions
4. **Collaborate** → Shared decision-making
5. **Defer to** → Community-driven governance

**Real-World Case Studies:**

**Providence, RI: Racial and Environmental Justice Committee**
- **Challenge:** Environmental hazards disproportionately affect communities of color
- **Our Data:** `/jurisdictions/demographics` + `/nonprofits/environmental_orgs` + `/meetings/public_hearings`
- **Outcome:** Moved from "consulting" to "community-driven" - residents now co-chair committee
- **Metrics:** Track using `/analytics/metric_views` - meeting attendance, community proposals adopted

**Portland, OR: Equity Working Group**
- **Challenge:** Budget decisions lacked community input
- **Our Data:** `/budgets/city_budgets` + `/nonprofits/advocacy_orgs` + `/officials/city_council`
- **Outcome:** Participatory budgeting with community ownership
- **Metrics:** Track using `/analytics/dashboard_metrics` - community budget proposals, funding allocated

**How Our Platform Supports the Spectrum:**
- **Inform:** `/meetings/agendas` + `/documents` for transparency
- **Consult:** `/surveys` + `/factchecks` for informed input
- **Involve:** `/civic_tech/hackathons` + `/nonprofits/volunteer_activities`
- **Collaborate:** `/grants/participatory_budgeting` + `/legislation/co-creation`
- **Defer to:** `/analytics/community_impact_metrics`

**Citation:**
```bibtex
@article{gonzalez_spectrum,
  author = {González, Rosa},
  title = {Spectrum of Community Engagement to Ownership},
  organization = {Facilitating Power},
  year = {2021},
  url = {https://movementstrategy.org/}
}
```

---

### Harvard Ash Center: Data-Smart City Solutions (Archived)

**Organization:** Harvard Kennedy School Ash Center for Democratic Governance and Innovation  
**What we use:** Research on how data engineering impacts community outcomes - informs our `/analytics/metric_views` templates.

- **Source:** https://ash.harvard.edu/
- **Note:** Data-Smart City Solutions initiative (archived) - use cases based on historical civic data research
- **License:** Educational use

**Example Use Cases from Data-Smart Research:**

**Use Case 1: Youth Obesity Prevention (Austin, TX)**

**Problem:** Childhood obesity rates 30% higher in low-income neighborhoods

**Data Integration:**
```python
# Our platform combines:
- /jurisdictions/demographics          # BMI, income, age
- /nonprofits (NTEE K30)              # Food access programs
- /civic_tech/food_oasis              # Food desert mapping
- /meetings/school_board              # Nutrition policy discussions
```

**Outcome:**
- Identified 15 "food deserts" lacking fresh produce
- Partnered with 8 nonprofits to launch mobile markets
- School board approved healthier lunch standards

**Metrics We Track:**
- **Metric View:** `youth_nutrition_access`
- **KPIs:** Fresh food outlets per capita, school lunch quality scores, childhood obesity trends
- **Dashboard:** `/analytics/dashboard_metrics/health_equity`

---

**Use Case 2: College Readiness (Mesa Public Schools, AZ)**

**Problem:** 40% of students off-track for college by 9th grade

**Data Integration:**
```python
# Our platform combines:
- /school_districts/nces_data         # Enrollment, demographics
- /school_districts/budgets           # Per-pupil spending, program funding
- /analytics/date_dimension           # Time-series tracking
- /surveys/student_surveys            # Student engagement, aspirations
```

**Outcome:**
- Early warning system identifies at-risk students
- Targeted interventions (tutoring, mentorship)
- College enrollment increased 15%

**Metrics We Track:**
- **Metric View:** `college_readiness_pipeline`
- **KPIs:** On-track percentage, intervention effectiveness, college enrollment rates
- **Dashboard:** `/analytics/dashboard_metrics/education_outcomes`

---

**Our Use Case Template:**

For each community challenge, we provide:
1. **Problem Definition** → What data shows the issue
2. **Data Integration** → Which datasets to combine
3. **Analytics View** → Pre-built metric views
4. **Action Pathways** → Nonprofits, officials, meetings to engage
5. **Success Metrics** → How to measure impact

**Citation:**
```bibtex
@misc{harvard_datasmart_use_cases,
  author = {{Harvard Kennedy School Ash Center}},
  title = {Data-Smart City Solutions: Civic Data Use Cases},
  year = {2016},
  note = {Archived civic data research initiative},
  url = {https://ash.harvard.edu/}
}
```

---

### Brookings Institution: Data-Driven Policymaking

**Organization:** Brookings Institution, Center on Regulation and Markets  
**What we use:** Data Academy model for turning "Open Data" into "Accessible Data" - validates our `/domains` and `/standards` architecture.

- **Source:** https://www.brookings.edu/
- **Article:** "How Citizens and Local Governments Advance Data-Driven Policymaking"
- **License:** Public research

**The Data Academy Model:**

**Case Study: Tempe, AZ**

**Workflow:**
```
City Creates Dashboard → Residents Attend Data Academy → Data Informs Policy
     (/standards)             (/meetings/trainings)        (/legislation)
```

**Our Platform Support:**

| Stage | City Action | Our Data | Resident Outcome |
|-------|-------------|----------|------------------|
| **1. Publish** | Open data portal | `/standards/schema_org_jsonld` | Machine-readable datasets |
| **2. Train** | Data Academy | `/meetings/trainings` | Residents learn SQL, Tableau |
| **3. Analyze** | Dashboard access | `/analytics/dashboard_metrics` | Community-driven insights |
| **4. Advocate** | Public testimony | `/meetings/public_hearings` | Data-backed proposals |
| **5. Legislate** | Policy adoption | `/legislation/local_ordinances` | Evidence-based laws |

**Example: Tempe Water Conservation Policy**

**Data Stack:**
- **Raw Data:** `/jurisdictions/budget_data` - Water department spending
- **Standards:** `/standards/ceds_aligned` - Standardized metrics
- **Training:** `/meetings/trainings` - "Water Data 101" workshop
- **Analytics:** `/analytics/metric_views/water_usage_per_capita`
- **Outcome:** `/legislation` - New conservation ordinance passed

**Residents Learned:**
- How to query public datasets
- How to create visualizations
- How to present findings to city council

---

**Case Study: Norfolk, VA - Flooding Resilience**

**Problem:** Sea level rise threatens low-income neighborhoods

**Data Integration:**
```python
# Our platform combines:
- /jurisdictions/demographics          # Vulnerable populations
- /budgets/city_budgets               # Infrastructure spending
- /nonprofits (NTEE W)                # Environmental advocacy
- /meetings/public_hearings           # Community testimony
- /standards/schema_org_jsonld        # GeoJSON flood maps
```

**Data Academy Curriculum:**
1. **Week 1:** Understanding flood risk data
2. **Week 2:** Budget analysis (where does money go?)
3. **Week 3:** Creating data visualizations
4. **Week 4:** Presenting to city council

**Outcome:**
- 50 residents trained
- Community-led flood resilience plan
- $10M infrastructure investment in vulnerable areas

---

**Why Data Academies Matter:**

**Traditional Model (Fails):**
- City: "Here's a 500-page PDF budget"
- Residents: *Can't understand it, disengage*

**Data Academy Model (Works):**
- City: "Here's open data + training"
- Residents: *Build skills, create analysis, influence policy*

**Our Role:**
1. **Standardize Data:** `/standards/popolo_exports` makes data interoperable
2. **Host Training Events:** `/meetings/trainings` tracks Data Academy schedules
3. **Provide Analytics:** `/analytics/metric_views` offers ready-to-use dashboards
4. **Connect Stakeholders:** `/nonprofits` + `/officials` + `/civic_tech` = collaboration

**Citation:**
```bibtex
@article{brookings_data_driven,
  author = {{Brookings Institution}},
  title = {How Citizens and Local Governments Advance Data-Driven Policymaking},
  journal = {Brookings Center on Regulation and Markets},
  year = {2023},
  url = {https://www.brookings.edu/}
}
```

---

### Reason Foundation

**Organization:** [Reason Foundation](https://reason.org/) — 501(c)(3) nonprofit think tank publishing policy research (including transportation, infrastructure, and governance topics).

**What we use:** Context and references to state highway performance, transportation innovation, and related policy materials (for example the **Annual Highway Report** and other publications hosted on [reason.org](https://reason.org/)).

- **Website:** https://reason.org/
- **Use:** When you quote, summarize, or reproduce Reason materials, cite the **specific report or page** and follow Reason Foundation’s terms and copyright notices on that content.

**Citation:**
```bibtex
@misc{reason_foundation,
  author = {{Reason Foundation}},
  title = {Reason Foundation},
  year = {2026},
  url = {https://reason.org/},
  note = {Nonprofit policy research organization; transportation and governance among topic areas}
}
```

---

### Open Data Impact: Evidence-Based Research

**Organization:** The GovLab at New York University (NYU Tandon School of Engineering)  
**What we use:** Evidence-based research on open data impact - validates our platform's approach and demonstrates measurable outcomes from open data initiatives.

- **Source:** https://odimpact.org/
- **Key Findings Report:** https://odimpact.org/key-findings.html
- **Full Report:** https://odimpact.org/files/open-data-impact-key-findings.pdf
- **Funded by:** Omidyar Network
- **License:** Creative Commons Attribution-ShareAlike 4.0 International License

**Research Overview:**

**19 Global Case Studies** analyzing what works in open data:
- Sectoral and geographic representativeness
- First-hand interviews with stakeholders
- Measurable, tangible impact analysis
- Best practices and enabling conditions

**Economic Impact Estimates:**
- **McKinsey (2013):** $3 trillion per year global value of open data
- **Omidyar Network Study:** $13 trillion over 5 years in G20 nations

**Four Main Impact Dimensions:**

| Impact Type | Description | Our Platform Support |
|-------------|-------------|---------------------|
| **Improving Government** | Transparency, accountability, efficiency | `/jurisdictions/budgets` + `/meetings` + `/legislation` |
| **Empowering Citizens** | Informed decision-making, participation | `/analytics/dashboards` + `/surveys` + `/factchecks` |
| **Creating Opportunity** | Economic innovation, new businesses | `/civic_tech` + `/grants` + `/nonprofits` |
| **Solving Public Problems** | Data-driven solutions to complex issues | `/community_solutions` + `/metric_views` |

**Enabling Conditions for Success:**

**1. Supply-Side (Data Providers):**
- **Quality Data:** Accurate, timely, machine-readable
- **Our Implementation:** `/standards/schema_org_jsonld`, `/standards/popolo_exports`

**2. Demand-Side (Data Users):**
- **Capacity Building:** Skills to analyze and use data
- **Our Implementation:** `/meetings/trainings` (Data Academies), `/analytics/metric_views`

**3. Intermediaries:**
- **Data Translators:** Organizations bridging supply and demand
- **Our Implementation:** `/civic_tech/brigade_chapters`, `/nonprofits/advocacy_orgs`

**4. Ecosystem:**
- **Multi-Stakeholder Collaboration:** Government + Civic Tech + Nonprofits
- **Our Implementation:** `/community_solutions/stakeholder_mapping`

**Key Challenges Identified:**

| Challenge | ODI Findings | Our Mitigation Strategy |
|-----------|--------------|------------------------|
| **Data Quality** | Incomplete, outdated data | Automated ingestion + validation pipelines |
| **Technical Capacity** | Users lack skills to analyze | Pre-built dashboards + metric views |
| **Sustainability** | Projects depend on grants | Open-source + reusable infrastructure |
| **Privacy Risks** | Potential for harm | Anonymization + ethical data standards |

**10 Recommendations for Next-Generation Open Data:**

1. **Focus on Demand, Not Just Supply** → We provide ready-to-use analytics
2. **Build User Capacity** → Data Academies tracked in `/meetings/trainings`
3. **Create Data Intermediaries** → Civic tech projects in `/civic_tech`
4. **Ensure Data Quality** → Standards compliance (`/standards`)
5. **Enable Interoperability** → OCD-ID, Popolo, Schema.org integration
6. **Measure Impact** → `/analytics/metric_views` + `/community_solutions/metrics`
7. **Sustain Engagement** → Open-source + HuggingFace hosting
8. **Mitigate Risks** → Privacy-first design, anonymization
9. **Foster Collaboration** → Multi-stakeholder `/community_solutions`
10. **Scale What Works** → Reusable templates + case studies

**How We Apply ODI Research:**

**Our Platform as Evidence-Based Open Data Infrastructure:**
- **Supply:** 90K+ jurisdictions, 3M+ nonprofits, 500K+ meetings → standardized datasets
- **Demand:** Pre-built dashboards, metric views, analytics → accessible to non-technical users
- **Intermediaries:** Civic tech projects, brigade chapters, nonprofits → data translators
- **Ecosystem:** Community solutions framework → multi-stakeholder collaboration

**Real-World Validation:**

ODI case studies demonstrate that open data works when:
1. ✅ **Data is standardized** → We use OCD-ID, Popolo, Schema.org
2. ✅ **Users have capacity** → We provide training + dashboards
3. ✅ **Intermediaries bridge gaps** → We integrate civic tech projects
4. ✅ **Impact is measured** → We track metrics + outcomes

**Example ODI Case Study Applied to Our Platform:**

**Chile's Budget Transparency (ODI Case Study):**
- **Problem:** Citizens couldn't understand government budgets
- **Solution:** Open budget data + visualization tools
- **Impact:** Increased public participation in budget process

**Our Implementation:**
```python
# Replicating Chile's success:
- /jurisdictions/budget_data       # Open budget data (supply)
- /analytics/dashboard_metrics     # Budget visualizations (demand)
- /meetings/trainings             # Data literacy programs (capacity)
- /meetings/public_hearings       # Public participation (engagement)
- /community_solutions/metrics    # Budget impact tracking (measurement)
```

**Citation:**
```bibtex
@techreport{verhulst_open_data_impact,
  author = {Verhulst, Stefaan and Young, Andrew},
  title = {Open Data Impact: When Demand and Supply Meet - Key Findings of the Open Data Impact Case Studies},
  institution = {The GovLab, NYU Tandon School of Engineering},
  year = {2016},
  url = {https://odimpact.org/key-findings.html},
  note = {Supported by Omidyar Network. 19 global case studies.}
}
```

**Why This Matters for Our Platform:**

Open Data Impact provides **evidence-based validation** that our approach works:
- ✅ Combining **supply** (data) + **demand** (analytics) + **capacity** (training) = impact
- ✅ Multi-stakeholder collaboration drives success
- ✅ Standardization and quality are essential
- ✅ Impact must be measured and documented

Their research proves: **Open data alone isn't enough. You need the ecosystem we're building.**

---

### Tableau Data Equity Hub (Salesforce Data for Good)

**Organization:** Tableau / Salesforce  
**What we use:** Data equity frameworks, community-centered data storytelling resources, and visualization best practices for presenting civic and social impact data equitably.

- **Source:** https://www.salesforce.com/company/equality/
- **License:** Proprietary (educational/reference use)
- **Program:** Tableau Data for Good / Salesforce Equality initiatives

**Key Resources:**

| Resource | Relevance to Our Platform |
|----------|--------------------------|
| **Data Equity Hub** | Frameworks for equitable data representation in dashboards |
| **Viz for Social Good** | Best practices for community-facing analytics |
| **Tableau Public** | Free publishing platform for civic data visualizations |
| **Data + Equality** | Research on closing data gaps in underrepresented communities |

**Why This Matters for Open Navigator:**

Tableau's Data Equity Hub provides principles for **presenting civic data without reproducing bias** — directly applicable to our `/analytics/dashboard_metrics` and `/analytics/metric_views` templates:

- **Representation:** Ensure demographic data in `/jurisdictions/demographics` is visualized equitably
- **Accessibility:** Chart design standards for community-facing dashboards
- **Framing:** Avoid deficit narratives when displaying health, income, and education data
- **Participation:** Center community voices in data storytelling

**Citation:**
```bibtex
@misc{tableau_data_equity_hub,
  author = {{Tableau} and {Salesforce}},
  title = {Data Equity Hub — Salesforce Equality},
  year = {2024},
  url = {https://www.salesforce.com/company/equality/},
  note = {Tableau Data for Good initiative. Frameworks for equitable data visualization and community-centered data storytelling.}
}
```

---

### PolicyMap

**Organization:** PolicyMap, Inc.  
**What we cite:** [PolicyMap](https://www.policymap.com/) offers **mapping, analytics, and curated U.S. socio-economic data** for understanding communities and markets—widely used in housing, health, government, and nonprofit contexts. We reference it as an example of **neighborhood-level decision support** that complements open government and Census-based workflows in Open Navigator. **We do not redistribute PolicyMap data in this repository**; their data catalog, licensing, and attribution rules apply when you use their products directly (see their site, including **Citing Us** and **Terms** in the footer).

**Primary site:** [https://www.policymap.com/](https://www.policymap.com/)

**BibTeX (portal — follow [PolicyMap](https://www.policymap.com/) citing guidance for specific datasets or maps):**
```bibtex
@misc{policymap_portal,
  author = {{PolicyMap}},
  title = {PolicyMap: Mapping, Analytics, and Data Visualization},
  year = {2026},
  url = {https://www.policymap.com/},
  note = {Commercial mapping and data platform; cite per publisher requirements when using licensed data}
}
```

---

### IATI Standard (International Aid Transparency Initiative)

**Organization:** IATI Secretariat  
**What we use:** International development funding transparency framework - informs grant tracking, nonprofit program outcomes, and cross-sector collaboration metrics.

- **Source:** https://iatistandard.org/
- **Current Version:** IATI Standard v2.03
- **Specification:** https://iatistandard.org/en/iati-standard/203/
- **License:** Open Data Commons Attribution License (ODC-By)
- **Coverage:** 1,300+ publishers, $1+ trillion in development aid tracked
- **Used for:** Grant funding transparency, nonprofit program measurement, community solution tracking

**Why IATI in Community Solutions:**

IATI provides a proven framework for **tracking community impact across sectors** - government, nonprofits, foundations, and international partners.

**Citation:**
```bibtex
@misc{iati_standard,
  author = {{IATI Secretariat}},
  title = {IATI Standard Version 2.03},
  year = {2018},
  url = {https://iatistandard.org/},
  note = {Open Data Commons Attribution License (ODC-By)}
}
```

**Resources:**
- **Registry:** https://iatiregistry.org/
- **d-Portal:** https://d-portal.org/
- **Datastore:** https://iatidatastore.iatistandard.org/

---

## 🤝 Civic Engagement Frameworks

**In this section:**
- [Maine Township: digital community marketplace (case study)](#maine-township-digital-community-marketplace-case-study)

### Maine Township: digital community marketplace (case study)

**Organization:** CivicPlus (published case study); Maine Township, Illinois (local government)  
**What we use:** A reference narrative for **resident-facing civic engagement** in parks, recreation, and special events—shifting high-demand programs from **in-person-only** registration and **paper-based** space tracking to **online access**, **interactive maps** with **real-time availability**, **digital payments**, **unified records** for walk-in and web signups, and **timely notifications** (for example weather updates to participants).

- **Case study:** [CivicPlus — *Modernizing Tradition: Maine Township’s Garage Sale Goes Digital*](https://www.civicplus.com/case-studies/pr/maine-township-goes-digital-successfully/)
- **Publisher summary:** Vendor registration moved online in **2024**; reported outcomes include shorter in-person queues, higher online adoption, fewer space-assignment errors, and staff time reclaimed for community programs (per the case study page).

**Why we cite it:** It documents an **operational engagement pattern**—inform, transact, visualize spatial capacity, and communicate at scale—that informs how we think about accessibility, transparency, and service design for community programs (not an endorsement of any particular vendor or product).

**License / attribution:** Public marketing case study on the publisher’s site; link and summarize rather than reproducing long excerpts without permission.

**Citation:**
```bibtex
@misc{civicplus_maine_township_garage_sale_2026,
  author = {{CivicPlus}},
  title = {Modernizing Tradition: Maine Township's Garage Sale Goes Digital},
  year = {2026},
  url = {https://www.civicplus.com/case-studies/pr/maine-township-goes-digital-successfully/},
  note = {Case study; recreation and community event digital engagement}
}
```


## 🙏 Acknowledgments

We are grateful to the following organizations and individuals:

**Academic Institutions:**
- Association for Computational Linguistics (ACL) for MeetingBank
- Harvard University Mellon Urbanism Lab for LocalView
- [Opportunity Insights](https://opportunityinsights.org/) (Harvard University) for public research and data on economic mobility and neighborhoods
- Cornell University Roper Center for public opinion research
- MIT Election Data + Science Lab for election data
- University of Pennsylvania Annenberg Center for fact-checking

**Civic Tech Community:**
- **GroundVue** - Partner organization inspiring community accountability work
- **Code for America** - Civic technology movement and brigade network
- **City Bureau** - Documenters Network and City Scrapers project
- **Council Data Project** - Open-source municipal data infrastructure
- **U.S. Digital Response** - Emergency civic technology support
- **Civic Tech Field Guide** - Community resource and project directory

**Standards Bodies:**
- W3C Community Group for Schema.org
- Open Civic Data for jurisdiction identifiers (OCDEP 2)
- Popolo Project for open government data standards
- IATI Secretariat for international aid transparency
- U.S. Department of Education for CEDS

**Enterprise Tech for Social Good:**
- **Microsoft** - Tech for Social Impact (Nonprofit CDM)
- **Google** - Data Commons (Knowledge Graph & Civic Data API)
- **AWS** - Open Data for Good (Registry best practices)
- **Databricks** - Databricks for Good (Unity Catalog, Delta Lake, MLflow, Agent Bricks)
- **Snowflake** - Snowflake for Good (Data Marketplace)
- **Oracle** - NetSuite Social Impact (Fund accounting models)
- **Salesforce / Tableau** - Salesforce.org (Nonprofit Success Pack), Tableau Data Equity Hub (Data for Good)
- **Cisco** - Crisis Response (Network resilience)
- **IBM** - Science for Social Good (AI use cases)
- **Meta** - Data for Good (Population mapping)

**Data Platforms & Organizations:**
- HuggingFace for dataset hosting
- [PolicyMap](https://www.policymap.com/) for commercial neighborhood mapping and socio-economic data reference (see [Community Solutions — PolicyMap](#policymap))
- ProPublica for nonprofit financial data (3M+ organizations), congressional voting records, campaign finance data, and healthcare provider information
- Open States for legislative data
- OHDSI for OMOP Common Data Model (vocabulary system)
- Every.org for charity metadata and mission statements
- Findhelp.org for local social services directory (400K+ programs)
- [State Symbols USA](https://statesymbolsusa.org/categories/colors) for curated state-colors reference (see [Government Data — State Symbols USA](#state-symbols-usa-reference))

**Government:**
- Alabama Secretary of State for Fair Campaign Practices Act (FCPA) public campaign finance reports ([Alabama Votes FCPA portal](https://fcpa.alabamavotes.gov/page.request.do?page=page.acfPublicGeneralReports))
- U.S. Census Bureau for demographic data
- National Center for Education Statistics (NCES)
- IRS for tax-exempt organization data
- CISA for .gov domain registry
- All municipal governments providing open access to meeting records

**Special Thanks:**
- All civic technologists building open government tools
- Municipal staff maintaining public meeting archives
- Journalists and community advocates holding power accountable


---

## 📖 How to Cite This Project

If you use **Open Navigator** in your research, please cite:

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

## 📝 License Compliance

This project respects all dataset licenses and terms of use. See [LICENSE](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/LICENSE) for this project's MIT license.

For dataset-specific licenses, please refer to the original sources listed above.
