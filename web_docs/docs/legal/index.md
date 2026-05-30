---
sidebar_position: 1
sidebar_label: Terms and Privacy
---

# Terms and Privacy

:::info[Purpose]
This section contains all legal policies, terms of service, and compliance documentation for Open Navigator. Please review these documents carefully before using the Service.
:::

## 📋 Required Reading

All users must comply with the following documents:

### [Terms of Service](./terms-of-service.md)
The main legal agreement governing your use of Open Navigator. This document incorporates all third-party data provider terms and establishes your rights and responsibilities.

**Key Topics:**
- Acceptable use policies
- Attribution requirements
- Prohibited uses (especially FEC donor solicitation restrictions)
- Intellectual property rights
- Limitation of liability

**⚠️ CRITICAL:** By using this Service, you agree to comply with ALL third-party provider terms, including Charity Navigator's strict attribution requirements and rate limits.

---

### [Data Provider Terms of Service](./data-provider-terms.md)
Comprehensive documentation of all third-party data provider terms, usage policies, rate limits, and attribution requirements.

**Covers:**
- U.S. Government sources (IRS, Census, NCES, FEC, Grants.gov)
- Google services (BigQuery, Civic API, Data Commons)
- Nonprofit data (Charity Navigator, ProPublica, Every.org)
- Civic APIs (Open States, Wikidata, DBpedia)
- Academic datasets (MeetingBank, LocalView, CDP)
- Election data (MIT Election Lab, OpenElections)

**Must Read If:**
- You plan to redistribute data from this Service
- You're building applications using our data
- You need to understand rate limits and quotas
- You want to know specific attribution requirements

---

### [Privacy Policy](./privacy-policy.md)
How we collect, use, and protect your information. Includes your rights under CCPA (California) and GDPR (Europe).

**Key Points:**
- We only aggregate publicly available data
- We don't sell your information
- You can request deletion of your account
- Public records exceptions apply
- Your privacy rights and how to exercise them

---

### [Legal Compliance & Data Use Policies](../legal-compliance.md)
Technical compliance documentation showing our adherence to all data source terms of service, API policies, and legal requirements.

**Includes:**
- Compliance status for each data source
- Implementation details for rate limiting
- User-Agent requirements
- Attribution implementations
- Data provenance tracking

---

## 🚨 Critical Compliance Requirements

### Charity Navigator
**MANDATORY on ALL pages using their data:**
- ✅ Display "Powered by Charity Navigator"
- ✅ Link charity names to their CN profiles
- ✅ Include trademark notice
- ❌ Maximum 1,000 API calls per day
- ❌ NO redistribution of CN data
- ❌ NO competing rating systems

**Violation consequences:** API access termination, potential legal action

---

### Google Services
**MANDATORY:**
- ✅ Display "Data provided by Google" where applicable
- ❌ Civic API data CANNOT be cached beyond 30 days
- ❌ Must comply with Google Cloud Terms of Service
- ❌ Subject to API quotas

---

### ProPublica APIs
**MANDATORY:**
- ✅ Provide attribution to ProPublica
- ✅ Include API key in headers (`X-API-Key`)
- ❌ **CRITICAL:** FEC Campaign Finance data CANNOT be used for commercial solicitation or fundraising
- ❌ Rate limits: 5,000 requests/day

---

### Open States
**MANDATORY:**
- ✅ Display "Powered by Open States"
- ✅ API key required (free registration)
- ❌ 50,000 requests/month free tier
- ❌ Data licenses vary by state

---

### DBpedia
**MANDATORY:**
- ✅ Attribute to DBpedia and Wikipedia
- ✅ CC BY-SA 3.0 license (share-alike applies)
- ❌ Derivative works must use compatible license

---

## ⚖️ Your Responsibilities

When using Open Navigator, you agree to:

1. **Respect Rate Limits**
   - Implement caching where permitted
   - Add delays between requests
   - Monitor your usage against quotas

2. **Provide Attribution**
   - Include all required credits
   - Link to data provider profiles where required
   - Display trademark notices

3. **Prohibited Uses**
   - ❌ NO use of FEC donor data for commercial solicitation
   - ❌ NO redistribution of Charity Navigator data
   - ❌ NO circumvention of rate limits
   - ❌ NO removal of attribution notices

4. **Data Accuracy**
   - Verify critical information with original sources
   - Report errors or inaccuracies to us
   - Don't misrepresent data provenance

---

## 🔒 Privacy & Security

### What We Collect
- **Public data only:** Government records, tax filings, public meetings
- **Optional account data:** Email address (if you create an account)
- **Technical data:** IP address, browser info (for security)

### What We DON'T Collect
- ❌ Private financial information
- ❌ Health information
- ❌ Social Security numbers
- ❌ Any data requiring authentication to access

### Your Rights
- ✅ Request removal of public records data (case-by-case)
- ✅ Delete your account anytime
- ✅ Access and download your data
- ✅ Opt out of analytics

**See [Privacy Policy](./privacy-policy.md) for complete details.**

---

## 📊 Data Sources Quick Reference

### 🏛️ Government Data Sources (1-6)

| # | Abbrev | Source | Public Domain? | API Key? | Rate Limit | Attribution |
|---|--------|--------|---------------|----------|------------|-------------|
| 1 | IRSB | **IRS EO-BMF** | Yes | No | None | Recommended |
| 2 | CENS | **Census Bureau** | Yes | No* | 500 req/IP/day* | Recommended |
| 3 | NCES | **NCES (Schools)** | Yes | No | None | Recommended |
| 4 | FECP | **FEC / OpenFEC** | Yes | Yes | 1,000 req/hour | **REQUIRED** |
| 5 | GRNT | **Grants.gov** | Yes | No | None | Recommended |
| 6 | GSAD | **GSA Domains** | Yes | No | None | No |

### 🎬 Media & Social Platforms (7)

| # | Abbrev | Source | Public Domain? | API Key? | Rate Limit | Attribution |
|---|--------|--------|---------------|----------|------------|-------------|
| 7 | YOUT | **YouTube Data API** | No | Yes | 10,000 units/day | **REQUIRED** |

### 💼 Google Services (8-10)

| # | Abbrev | Source | Public Domain? | API Key? | Rate Limit | Attribution |
|---|--------|--------|---------------|----------|------------|-------------|
| 8 | GBQR | **Google BigQuery** | Mixed | Yes | 1 TB/month free | **REQUIRED** |
| 9 | GCIV | **Google Civic API** | No | Yes | 25,000 req/day | **REQUIRED** |
| 10 | GDCM | **Google Data Commons** | Yes | No | None | **REQUIRED** |

### 🏢 Nonprofit Data Providers (11-18)

| # | Abbrev | Source | Public Domain? | API Key? | Rate Limit | Attribution |
|---|--------|--------|---------------|----------|------------|-------------|
| 11 | CHNV | **Charity Navigator** | No | Yes | **1,000 req/day** | **REQUIRED** (strict) |
| 12 | PPNP | **ProPublica Nonprofit** | Mixed | No | None | **REQUIRED** |
| 13 | PPCG | **ProPublica Congress** | Mixed | Yes | 5,000 req/day | **REQUIRED** |
| 14 | PPCF | **ProPublica Campaign $** | Mixed | Yes | 5,000 req/day | **REQUIRED** |
| 15 | PPVS | **ProPublica Vital Signs** | Mixed | Yes | 5,000 req/day | **REQUIRED** |
| 16 | EVRY | **Every.org** | No | Yes | Custom | **REQUIRED** |
| 17 | LOGO | **Logo.dev** | No | Yes | 1,000 req/month | Recommended |
| 18 | GT90 | **GivingTuesday 990** | Yes | No | AWS egress | **REQUIRED** |

### 🗳️ Civic & Open Data (19-21)

| # | Abbrev | Source | Public Domain? | API Key? | Rate Limit | Attribution |
|---|--------|--------|---------------|----------|------------|-------------|
| 19 | OPST | **Open States** | No | Yes | 50,000 req/month | **REQUIRED** |
| 20 | WKDT | **Wikidata** | Yes (CC0) | No | ~1 req/sec | No |
| 21 | DBPD | **DBpedia** | CC BY-SA | No | ~1-2 req/sec | **REQUIRED** |

### 🎓 Academic & Research (22-26)

| # | Abbrev | Source | Public Domain? | API Key? | Rate Limit | Attribution |
|---|--------|--------|---------------|----------|------------|-------------|
| 22 | MTBK | **MeetingBank** | Academic | No | None | **REQUIRED** (citation) |
| 23 | LCLV | **LocalView (Dataverse)** | Academic | Yes | Varies | **REQUIRED** |
| 24 | CDPR | **Council Data Project** | MIT License | No | None | **REQUIRED** |
| 25 | CTSC | **City Scrapers / Documenters** | MIT License | No | None | **REQUIRED** |
| 26 | ROPR | **Roper Center (iPoll)** | Academic | No** | N/A | **REQUIRED** |

### 🗳️ Election Data (27-28)

| # | Abbrev | Source | Public Domain? | API Key? | Rate Limit | Attribution |
|---|--------|--------|---------------|----------|------------|-------------|
| 27 | MITE | **MIT Election Lab** | Open Data | No | None | **REQUIRED** |
| 28 | OPEL | **OpenElections** | Varies | No | None | **REQUIRED** |

### 💰 Paid Services - NOT USED (29)

| # | Abbrev | Source | Public Domain? | API Key? | Rate Limit | Attribution |
|---|--------|--------|---------------|----------|------------|-------------|
| 29 | BLTP | **Ballotpedia** | No | Yes | **PAID** | **REQUIRED** |

### 🌐 Scraped Meeting Platforms (30-34)

These platforms are accessed via web scraping (no API):

| # | Abbrev | Platform | Jurisdictions | Public Data? | robots.txt | Attribution |
|---|--------|----------|--------------|--------------|------------|-------------|
| 30 | LEGI | **Legistar** | 3,000+ cities | Yes | Check each | Jurisdiction |
| 31 | GRAN | **Granicus** | 2,500+ cities | Yes | Check each | Jurisdiction |
| 32 | CVPL | **CivicPlus** | 2,000+ cities | Yes | Check each | Jurisdiction |
| 33 | MUNI | **Municode** | 1,500+ cities | Yes | Check each | Jurisdiction |
| 34 | YTMT | **YouTube (Meetings)** | Varies | Yes | API only | **REQUIRED** |

**Notes:**
- *Census: Without API key = 500 requests/IP/day. With free API key = much higher limits
- **Roper: Full data requires institutional membership; metadata is free

**📖 Full Terms:** [Data Provider Terms](./data-provider-terms.md)  
**📞 Provider Contacts:** [Contact Information](./data-provider-terms.md#-contact-information-for-providers)

---

## 🆘 Compliance Support

### How to Stay Compliant

1. **Read the Terms**
   - Review [Terms of Service](./terms-of-service.md)
   - Study [Data Provider Terms](./data-provider-terms.md) for sources you use
   - Understand rate limits and quotas

2. **Implement Required Attributions**
   - Use attribution templates from [Data Provider Terms](./data-provider-terms.md#compliance-summary-table)
   - Include all mandatory credits
   - Link to provider profiles where required

3. **Monitor Your Usage**
   - Track API calls against rate limits
   - Implement caching to reduce requests
   - Set up alerts for quota thresholds

4. **Document Your Compliance**
   - Keep records of attribution implementations
   - Log API usage and rate limiting
   - Maintain audit trail for data sources

### Need Help?

**For compliance questions:**
- **Email:** [contact email to be added]
- **GitHub Issues:** [Report compliance issues](https://github.com/getcommunityone/open-navigator-for-engagement/issues)

**For provider-specific questions:**
- Contact the data provider directly (see [Data Provider Terms](./data-provider-terms.md) for contact info)

---

## 📅 Updates & Maintenance

### How We Keep These Documents Current

- **Regular Review:** Quarterly review of all provider terms
- **Automated Monitoring:** Track provider ToS changes
- **Community Reports:** Users can report outdated information
- **Version Control:** All changes tracked on GitHub

### How You Stay Informed

**Subscribe to updates:**
1. Watch our [GitHub repository](https://github.com/getcommunityone/open-navigator-for-engagement)
2. Enable notifications for legal document updates
3. Check this page periodically

**Material changes:**
- Prominent notice on the Service
- Email notification (if you have an account)
- 30-day notice period before taking effect

---

## 📜 Software License

**Open Navigator** is open-source software licensed under the **MIT License**.

**Key Points:**
- ✅ Free for commercial and non-commercial use
- ✅ Modification and redistribution allowed
- ✅ Must include MIT License notice in distributions
- ✅ No warranty or liability

**Full License:** [GitHub Repository](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/LICENSE)

**Important:** The MIT License applies to our **software code**, not to the third-party **data** we aggregate. Each data source has its own license (see [Data Provider Terms](./data-provider-terms.md)).

---

## ⚠️ Disclaimers

### No Government Endorsement

This Service is **not affiliated with, endorsed by, or sponsored by:**
- U.S. Internal Revenue Service
- U.S. Census Bureau
- Any state or local government
- Any data source provider
- Charity Navigator, Inc.
- ProPublica, Inc.
- Google LLC

### No Professional Advice

This Service provides **information only**. It does NOT provide:
- Legal advice
- Medical or health advice
- Financial advice
- Tax advice
- Professional consultation services

**For specific advice, consult qualified professionals in the relevant field.**

### Data Accuracy

While we strive for accuracy:
- Data is sourced from authoritative public sources
- Data is provided "as is" without warranties
- Errors in source data may appear in our datasets
- Users should verify critical information with original sources

---

## 📞 Contact Information

**General Inquiries:**
- **Email:** [contact email to be added]
- **GitHub:** [Issues](https://github.com/getcommunityone/open-navigator-for-engagement/issues)

**Privacy Requests:**
- Subject: "Privacy Request" or "CCPA Request" or "GDPR Request"
- We respond within 30 days

**Compliance Questions:**
- Subject: "Compliance Question"
- Include specific data source and question

**Data Removal Requests:**
- Subject: "Data Removal Request"
- Include: Name, data to remove, reason, proof of identity
- Evaluated case-by-case

---

## 🔗 Related Documentation

- [Citations & Data Sources](../data-sources/citations.md) - Academic citations and BibTeX
- [Data Model & ERD](../data-sources/data-model-erd.md) - Database schema
- [HuggingFace Datasets](../data-sources/huggingface-datasets.md) - Published datasets
- [Development Documentation](../development/) - Technical implementation

---

:::tip[Quick Compliance Checklist]
Before redistributing data from this Service:

- [ ] Read [Terms of Service](./terms-of-service.md)
- [ ] Review [Data Provider Terms](./data-provider-terms.md) for sources you'll use
- [ ] Implement required attributions (especially Charity Navigator)
- [ ] Respect rate limits and quotas
- [ ] Set up caching where permitted
- [ ] Monitor compliance continuously
- [ ] Document your attribution and compliance measures

**When in doubt:** Provide attribution and contact the provider for clarification.
:::

---

**Last Updated:** April 28, 2026  
**Version:** 1.0
