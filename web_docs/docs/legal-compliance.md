---
sidebar_position: 100
sidebar_label: Legal & Compliance
slug: /legal-compliance
---

# Legal Compliance & Data Use Policies

:::info[Purpose]
This document ensures **Open Navigator** complies with all data source terms of service, API policies, and legal requirements. Every data source is documented with its use policy, licensing terms, and compliance status.
:::

:::tip[Looking for Legal Policies?]
**For complete legal documentation, see:**
- **[Terms of Service](./legal/terms-of-service.md)** - Main legal agreement
- **[Data Provider Terms](./legal/data-provider-terms.md)** - All third-party provider terms
- **[Privacy Policy](./legal/privacy-policy.md)** - How we handle your information
- **[Legal Overview](./legal/)** - Complete legal documentation index

This page provides **technical compliance details** for developers and data users.
:::

## 📋 Overview

Open Navigator is built on **publicly available government data** and **open APIs**. We respect all terms of service, implement proper rate limiting, provide attribution, and comply with all data use policies.

**Our Commitments:**
- ✅ **Transparency** - All data sources are documented and cited
- ✅ **Attribution** - Proper citations in all published datasets
- ✅ **Compliance** - Adherence to all terms of service and API policies
- ✅ **Privacy** - No collection of personal data beyond what's publicly available
- ✅ **Rate Limiting** - Respectful API usage with proper delays
- ✅ **Accessibility** - Making public data more accessible to communities

**Legal Agreements:**
- See [Terms of Service](./legal/terms-of-service.md) for user agreements
- See [Data Provider Terms](./legal/data-provider-terms.md) for complete provider requirements
- See [Privacy Policy](./legal/privacy-policy.md) for privacy practices

## 🏛️ U.S. Government Data Sources

**In this section:**
- [IRS Exempt Organizations Business Master File (EO-BMF)](#irs-exempt-organizations-business-master-file-eo-bmf)
- [IRS Form 990 Data (Google BigQuery Public Datasets)](#irs-form-990-data-google-bigquery-public-datasets)
- [U.S. Census Bureau Data](#us-census-bureau-data)
- [Grants.gov API](#grantsgov-api)
- [National Center for Education Statistics (NCES)](#national-center-for-education-statistics-nces)

### IRS Exempt Organizations Business Master File (EO-BMF)

**Data Type:** Tax-exempt organization records (1.9M+ nonprofits)  
**Source:** [IRS Statistics of Income](https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf)  
**License:** Public Domain (U.S. Government Work)  
**Terms of Use:** [IRS.gov Copyright and Reuse Policy](https://www.irs.gov/about-irs/irsgov-privacy-policy)

**Compliance Status:** ✅ **COMPLIANT**
- Public domain data
- No API key required
- No restrictions on commercial or non-commercial use
- Attribution recommended but not required

**Implementation:** `discovery/irs_bmf_ingestion.py`

**Use Policy Key Points:**
- Data is updated monthly by the IRS
- Free to download and redistribute
- No personal financial information included (aggregate data only)

---

### IRS Form 990 Data (Google BigQuery Public Datasets)

**Data Type:** Nonprofit tax filings (5M+ Form 990s, 2013-present)  
**Source:** [Google BigQuery Public Datasets](https://console.cloud.google.com/marketplace/product/internal-revenue-service/irs-990)  
**Original Source:** [IRS Tax Exempt Organization Search](https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads)  
**License:** Public Domain (U.S. Government Work)  
**Terms of Use:** [Google Cloud Terms of Service](https://cloud.google.com/terms)

**Compliance Status:** ✅ **COMPLIANT**
- Public domain IRS data hosted by Google
- Requires Google Cloud account and BigQuery API access
- Standard BigQuery pricing applies (first 1TB queries/month free)
- Must comply with Google Cloud Terms of Service

**Implementation:** `scripts/enrich_nonprofits_bigquery.py`

**Use Policy Key Points:**
- Attribution to IRS and Google Cloud recommended
- Subject to Google BigQuery quotas and pricing
- Data is public but access requires Google Cloud credentials
- Must not use for unauthorized commercial solicitation

---

### U.S. Census Bureau Data

**Data Type:** Geographic boundaries, demographics, government entities  
**Source:** [U.S. Census Bureau](https://www.census.gov/)  
**APIs Used:**
- [Census Gazetteer Files](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html)
- [Census Bureau API](https://www.census.gov/data/developers.html)

**License:** Public Domain (U.S. Government Work)  
**Terms of Use:** [Census Bureau Data Policy](https://www.census.gov/about/policies.html)

**Compliance Status:** ✅ **COMPLIANT**
- Public domain data
- Free API access (API key recommended but not required)
- No restrictions on use or redistribution
- Attribution appreciated

**Implementation:** `discovery/census_ingestion.py`

**Use Policy Key Points:**
- Must not claim U.S. Census Bureau endorsement
- Data is free and unrestricted
- API rate limits apply (500 requests/IP per day without key)

---

### Grants.gov API

**Data Type:** Federal grant opportunities  
**Source:** [Grants.gov](https://www.grants.gov/)  
**API Documentation:** [Grants.gov API](https://www.grants.gov/web/grants/support/technical-support/grantor-technical-support/grants-gov-api.html)  
**License:** Public Domain (U.S. Government Work)  
**Terms of Use:** [Grants.gov Terms of Use](https://www.grants.gov/web/grants/support/terms-of-use.html)

**Compliance Status:** ✅ **COMPLIANT**
- Public government data
- No API key required for search and fetch endpoints
- Free unlimited access
- Must not misrepresent grant opportunities

**Implementation:** `discovery/grants_gov_integration.py`

**Use Policy Key Points:**
- Data is public and free to use
- Must not alter grant opportunity information
- Attribution to Grants.gov recommended

---

### National Center for Education Statistics (NCES)

**Data Type:** School district boundaries, demographics, enrollment  
**Source:** [NCES Common Core of Data](https://nces.ed.gov/ccd/)  
**License:** Public Domain (U.S. Government Work)  
**Terms of Use:** [NCES Privacy Policy](https://nces.ed.gov/privacysecurity/)

**Compliance Status:** ✅ **COMPLIANT**
- Public domain educational data
- No API key required
- Free download and redistribution
- No personal student information

**Implementation:** `discovery/nces_ingestion.py`

---

## 🆓 Free Public APIs (API Key Required)

**In this section:**
- [Open States API](#open-states-api)
- [Google Civic Information API](#google-civic-information-api)
- [FEC / OpenFEC API](#fec--openfec-api)
- [Google Data Commons](#google-data-commons)

### Open States API

**Data Type:** State legislation, legislators, votes, bills  
**Source:** [Open States](https://openstates.org/)  
**Operator:** Open States Foundation (part of Plural)  
**API Documentation:** [Open States API v3](https://docs.openstates.org/api-v3/)  
**License:** Varies by state (generally permissive)  
**Terms of Use:** [Open States Terms of Service](https://openstates.org/tos/)

**Compliance Status:** ✅ **COMPLIANT**
- **Free tier:** 50,000 requests/month
- **API key required:** Free registration at [openstates.org](https://openstates.org/accounts/signup/)
- Must provide attribution to Open States
- Non-commercial and commercial use allowed with attribution

**Implementation:** `discovery/openstates_sources.py`

**Use Policy Key Points:**
- Must display "Powered by Open States" or similar attribution
- Rate limit: 50,000 requests/month (free tier)
- Data licenses vary by state jurisdiction
- Must comply with API rate limits

**Environment Variable:**
```bash
OPENSTATES_API_KEY=your-api-key-here
```

---

### Google Civic Information API

**Data Type:** Elected officials, polling locations, election info  
**Source:** [Google Civic Information API](https://developers.google.com/civic-information)  
**License:** [Google APIs Terms of Service](https://developers.google.com/terms)  
**Terms of Use:** [Google Civic API Policies](https://developers.google.com/civic-information/docs/usage_limits)

**Compliance Status:** ✅ **COMPLIANT** (when API key configured)
- **Free tier:** 25,000 requests/day
- **API key required:** Free from [Google Cloud Console](https://console.cloud.google.com/)
- Must comply with Google APIs Terms of Service
- Must display attribution: "Data provided by Google"

**Implementation:** `discovery/google_civic_integration.py`

**Use Policy Key Points:**
- Free up to 25,000 requests/day
- Must not cache data beyond 30 days
- Must display Google attribution
- Subject to Google API quotas

**Environment Variable:**
```bash
GOOGLE_CIVIC_API_KEY=your-api-key-here
```

---

### FEC / OpenFEC API

**Data Type:** Campaign finance, political contributions, candidate data, committee filings  
**Source:** [OpenFEC API](https://api.open.fec.gov/developers/)  
**Bulk Downloads:** [FEC Bulk Data Portal](https://www.fec.gov/data/browse-data/?tab=bulk-data)  
**License:** Public Domain (U.S. Government Work)  
**Terms of Use:** [FEC.gov Terms of Use](https://www.fec.gov/updates/sale-or-use-contributor-information/)

**Compliance Status:** ✅ **COMPLIANT**

**API Access:**
- **Free tier:** 1,000 requests/hour (API key required)
- **Demo key:** 30 requests/hour (no registration)
- API key free at [api.data.gov](https://api.data.gov/signup/)
- Must not use contributor data for commercial solicitation

**Bulk Download Access:**
- **Free unlimited downloads** of complete datasets (CSV, FEC format)
- No API key required for bulk downloads
- Available datasets:
  - Individual contributions (Schedule A)
  - Operating expenditures (Schedule B)
  - Committee master files
  - Candidate master files
  - Campaign finance totals by election cycle
- Updated nightly (most datasets)
- Complete historical data from 1980s to present

**Implementation:** `discovery/fec_integration.py`

**Use Policy Key Points:**
- FEC data is public domain
- **CRITICAL:** Cannot use contributor information for commercial solicitation or fundraising
- Must comply with API rate limits (API only)
- Attribution to FEC required
- Bulk downloads have no rate limits

**Environment Variable:**
```bash
FEC_API_KEY=your-api-key-here  # Only needed for API, not bulk downloads
```

---

### Google Data Commons

**Data Type:** Demographics, economics, health statistics  
**Source:** [Google Data Commons](https://datacommons.org/)  
**API Documentation:** [Data Commons API](https://docs.datacommons.org/api/)  
**License:** [Data Commons Terms](https://datacommons.org/about)  
**Terms of Use:** [Google Terms of Service](https://policies.google.com/terms)

**Compliance Status:** ✅ **COMPLIANT**
- Free access to aggregated statistical data
- No API key required for most endpoints
- Must provide attribution to Google and original data sources
- Subject to Google Terms of Service

**Implementation:** `discovery/google_data_commons.py`

**Use Policy Key Points:**
- Data sourced from authoritative public sources
- Must attribute to Data Commons and original sources
- Free for non-commercial and commercial use

---

## 🌐 Linked Open Data (No API Key Required)

**In this section:**
- [Wikidata](#wikidata)
- [DBpedia](#dbpedia)

### Wikidata

**Data Type:** Structured knowledge from Wikipedia  
**Source:** [Wikidata](https://www.wikidata.org/)  
**SPARQL Endpoint:** [Wikidata Query Service](https://query.wikidata.org/)  
**License:** [CC0 1.0 Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/)  
**Terms of Use:** [Wikimedia Terms of Use](https://foundation.wikimedia.org/wiki/Terms_of_Use)

**Compliance Status:** ✅ **COMPLIANT**
- CC0 Public Domain - no restrictions
- No API key required
- Free unlimited access
- Must respect rate limits and user agent requirements

**Implementation:** `discovery/wikidata_integration.py`

**Use Policy Key Points:**
- Set descriptive User-Agent header
- Respect rate limits (no more than 1 request/second recommended)
- Data is CC0 public domain
- Attribution appreciated but not required

**User-Agent:**
```python
User-Agent: CommunityOne/1.0 (https://communityone.com/; contact@example.com)
```

---

### DBpedia

**Data Type:** Structured data from Wikipedia infoboxes  
**Source:** [DBpedia](https://www.dbpedia.org/)  
**Lookup API:** [DBpedia Lookup Service](https://lookup.dbpedia.org/)  
**License:** [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) and [GFDL](https://www.gnu.org/licenses/fdl-1.3.html)  
**Terms of Use:** [DBpedia Usage Policies](https://www.dbpedia.org/about/)

**Compliance Status:** ✅ **COMPLIANT**
- Free to use with attribution
- No API key required
- Must provide attribution to DBpedia and Wikipedia
- Must respect rate limits

**Implementation:** `discovery/dbpedia_integration.py`

**Use Policy Key Points:**
- Must attribute to DBpedia and Wikipedia
- Set descriptive User-Agent
- Rate limiting recommended (1-2 requests/second)
- Share-alike license (CC BY-SA 3.0)

---

## 💰 Paid/Commercial Services (Reference Only)

**In this section:**
- [Ballotpedia API v3.0](#ballotpedia-api-v30)

### Ballotpedia API v3.0

**Data Type:** Elected officials, ballot measures, election results  
**Source:** [Ballotpedia](https://ballotpedia.org/)  
**API Documentation:** [Ballotpedia API](https://ballotpedia.org/API_documentation)  
**License:** **Paid service - requires commercial license**  
**Terms of Use:** [Ballotpedia Terms of Use](https://ballotpedia.org/Ballotpedia:General_disclaimer)

**Compliance Status:** ⚠️ **NOT USED** (Reference implementation only)
- **PAID SERVICE** - requires payment for API access
- Code provided in `discovery/ballotpedia_integration.py` is reference only
- Web scraping may violate terms of service
- **Use free alternatives instead:** Google Civic API, Open States

**Free Alternatives:**
- ✅ Google Civic Information API (25k requests/day free)
- ✅ Open States API (50k requests/month free)
- ✅ NCES (free public data for school boards)

**Use Policy Key Points:**
- **DO NOT USE** without paid API license
- Web scraping is discouraged and may violate ToS
- Reference code for educational purposes only

---

## 📊 Third-Party Datasets

**In this section:**
- [GivingTuesday 990 Data Lake](#givingtuesday-990-data-lake)
- [ProPublica Nonprofit Explorer](#propublica-nonprofit-explorer)

### GivingTuesday 990 Data Lake

**Data Type:** IRS Form 990 XML filings  
**Source:** [GivingTuesday 990 Data Infrastructure](https://990data.givingtuesday.org/)  
**Storage:** AWS S3 Public Bucket (no credentials required)  
**License:** Public Domain (IRS data)  
**Terms of Use:** [AWS S3 Public Dataset Program](https://registry.opendata.aws/gt990datalake/)

**Compliance Status:** ✅ **COMPLIANT**
- Public dataset program
- No AWS credentials required (`--no-sign-request`)
- IRS data is public domain
- Attribution to GivingTuesday and IRS required

**Implementation:** `scripts/enrich_nonprofits_gt990.py`

**Use Policy Key Points:**
- Free access via AWS S3
- Must attribute to GivingTuesday and IRS
- Standard AWS data egress charges may apply
- Data is public domain

---

### ProPublica Nonprofit Explorer

**Data Type:** Nonprofit data and 990 filings  
**Source:** [ProPublica Nonprofit Explorer](https://projects.propublica.org/nonprofits/api)  
**API Documentation:** [Nonprofit Explorer API](https://projects.propublica.org/nonprofits/api)  
**License:** Mixed (IRS data is public domain, ProPublica analysis varies)  
**Terms of Use:** [ProPublica Data Store Terms](https://www.propublica.org/datastore/terms)

**Compliance Status:** ✅ **COMPLIANT**
- Free API access (no authentication or API key required)
- IRS data is public domain
- Must attribute to ProPublica
- Editorial/analytical use allowed, but cannot redistribute or commercialize raw data

**Use Policy Key Points:**
- ✅ Free unlimited API access
- ✅ Must provide attribution to ProPublica
- ✅ Can use data for publication, analysis, and editorial purposes
- ❌ Cannot republish raw data in its entirety
- ❌ Cannot sell access to the data or charge for it
- ❌ Cannot sell advertising specifically against the data
- ❌ Cannot sub-license or resell the data
- ProPublica's analysis may have separate copyright
- Rate limiting recommended (be respectful, ~1 req/sec suggested)

---

## 🔒 Privacy & Data Protection

**In this section:**
- [Personal Information](#personal-information)
- [GDPR & Privacy Compliance](#gdpr--privacy-compliance)
- [Data Retention](#data-retention)

### Personal Information

**What We Collect:**
- ✅ Publicly available information from government sources
- ✅ Elected officials' names, positions, contact information (public records)
- ✅ Public meeting attendees and speakers (from published minutes)
- ✅ Nonprofit organization data (from IRS filings)

**What We DON'T Collect:**
- ❌ Private citizen information not in public records
- ❌ Personal financial information
- ❌ Health information
- ❌ Social Security numbers
- ❌ Any data that requires authentication to access

### GDPR & Privacy Compliance

**Status:** ✅ **COMPLIANT**

- All data is from **public sources** (government records, public meetings, tax filings)
- No personal data collection beyond publicly available information
- No tracking or behavioral profiling
- Right to be forgotten: Contact us to request removal of public records data

**Legal Basis:**
- **Legitimate Interest:** Making public government data accessible
- **Public Task:** Civic engagement and democratic participation
- **Public Records Exception:** Government records are exempt from many privacy restrictions

### Data Retention

- Source data refreshed from authoritative sources monthly
- Cached data retained for performance optimization
- Public records data retained indefinitely (historical archive)
- API keys and credentials stored securely in environment variables (never in code)

---

## 🚨 Rate Limiting & Fair Use

**In this section:**
- [Our Rate Limiting Policies](#our-rate-limiting-policies)
- [User-Agent Requirements](#user-agent-requirements)

### Our Rate Limiting Policies

To be respectful of data sources and comply with terms of service:

| Source | Rate Limit | Implementation |
|--------|------------|----------------|
| **Wikidata** | 1 req/second | `time.sleep(1.0)` |
| **DBpedia** | 2 req/second | `time.sleep(0.5)` |
| **Ballotpedia** (web scraping) | 1 req/2 seconds | `await asyncio.sleep(2.0)` |
| **Open States** | 50k/month | API key quotas |
| **Google Civic** | 25k/day | API key quotas |
| **Census API** | 500/day (no key) | API key recommended |
| **FEC API** | 1,000/hour | API key required |

### User-Agent Requirements

All HTTP requests include descriptive User-Agent headers:

```python
User-Agent: CommunityOne/1.0 (Civic Engagement Platform; https://communityone.com/)
```

This allows data providers to:
- Identify our platform
- Contact us if issues arise
- Monitor usage patterns

---

## ✅ Attribution & Citations

**In this section:**
- [How We Provide Attribution](#how-we-provide-attribution)
- [Required Attributions](#required-attributions)

### How We Provide Attribution

**In Published Datasets:**
- HuggingFace dataset cards include full citations
- README files list all source attributions
- Data provenance tracked in metadata columns

**In Documentation:**
- Complete citations page: [Citations & Data Sources](./data-sources/citations.md)
- BibTeX references for academic use
- Links to original sources

**In Application:**
- Footer attribution to all data sources
- "About this data" tooltips with source information
- Links to authoritative sources for verification

### Required Attributions

When using our datasets, please include:

```
Data sources:
- U.S. Census Bureau (Public Domain)
- IRS Exempt Organizations Business Master File (Public Domain)
- Open States API (openstates.org)
- Google Civic Information API
- Wikidata (CC0 Public Domain)
- DBpedia (CC BY-SA 3.0)

Processed and published by: Open Navigator
https://github.com/getcommunityone/open-navigator-for-engagement
```

---

## 📜 Software License

**Open Navigator** is licensed under the **MIT License**.

See [LICENSE](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/LICENSE) for full text.

**Summary:**
- ✅ Free for commercial and non-commercial use
- ✅ Modification and redistribution allowed
- ✅ Attribution required (MIT License notice)
- ✅ No warranty or liability

---

## ⚖️ Legal Disclaimers

### No Government Endorsement

This platform is not affiliated with, endorsed by, or sponsored by:
- U.S. Internal Revenue Service
- U.S. Census Bureau
- Any state or local government
- Any data source provider

### Data Accuracy

While we strive for accuracy:
- Data is sourced from authoritative public sources
- Data is provided "as is" without warranties
- Users should verify critical information with original sources
- Errors in source data may be present in our datasets

### No Legal or Medical Advice

This platform provides information only. It does not provide:
- Legal advice
- Medical or health advice
- Financial advice
- Professional consultation services

### Limitation of Liability

See [LICENSE](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/LICENSE) for full limitation of liability terms.

---

## 📞 Contact & Compliance Questions

**For compliance questions or concerns:**
- **Email:** [Add contact email]
- **GitHub Issues:** [Report data compliance issues](https://github.com/getcommunityone/open-navigator-for-engagement/issues)

**To request data removal:**
- Public records data: Contact the original government agency
- Our processing: Open a GitHub issue or email us

**To report API abuse or violations:**
- Open a GitHub issue with details
- We will investigate and remediate promptly

---

### Legal Policies
- **[Terms of Service](./legal/terms-of-service.md)** - User agreement and legal terms
- **[Data Provider Terms](./legal/data-provider-terms.md)** - Complete third-party provider terms
- **[Privacy Policy](./legal/privacy-policy.md)** - Privacy practices and user rights
- **[Legal Overview](./legal/)** - Complete legal documentation index

### Data Documentation
- [Citations & Data Sources](./data-sources/citations.md) - Complete academic citations and BibTeX
- [Data Model & ERD](./data-sources/data-model-erd.md) - Database schema and relationships
- [HuggingFace Datasets](./data-sources/huggingface-datasets.md) - Published dataset catalog
- [API Integration Status](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/docs/API_INTEGRATION_STATUS.md) - Technical implementation details

---

:::tip[Compliance is a Priority]
We take legal compliance seriously. If you notice any issues with data usage, licensing, or terms of service compliance, please [open an issue](https://github.com/getcommunityone/open-navigator-for-engagement/issues) immediately.

**All users must comply with:**
- Our [Terms of Service](./legal/terms-of-service.md)
- All third-party [Data Provider Terms](./legal/data-provider-terms.md)
- Our [Privacy Policy](./legal/privacy-policy.md)
- Community feedback

---

## 🔗 Related Documentation

- [Citations & Data Sources](./data-sources/citations.md) - Complete academic citations and BibTeX
- [Data Model & ERD](./data-sources/data-model-erd.md) - Database schema and relationships
- [HuggingFace Datasets](./data-sources/huggingface-datasets.md) - Published dataset catalog
- [API Integration Status](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/docs/API_INTEGRATION_STATUS.md) - Technical implementation details

---

:::tip[Compliance is a Priority]
We take legal compliance seriously. If you notice any issues with data usage, licensing, or terms of service compliance, please [open an issue](https://github.com/getcommunityone/open-navigator-for-engagement/issues) immediately.
:::
