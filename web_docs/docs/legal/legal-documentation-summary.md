---
sidebar_position: 11
---

# Legal Documentation Summary

**Created:** April 28, 2026  
**Purpose:** Comprehensive Terms of Service for Open Navigator

## 📋 What Was Created

### 1. Complete Legal Framework

Four comprehensive legal documents have been created in `website/docs/legal/`:

1. **index.md** - Legal Overview & Quick Reference
   - Landing page for legal section
   - Quick compliance checklist
   - Summary of critical requirements
   - Links to all legal documents

2. **terms-of-service.md** - Main Terms of Service
   - Comprehensive user agreement
   - Incorporates ALL third-party provider terms
   - Most restrictive terms apply principle
   - 18 sections covering all legal aspects

3. **data-provider-terms.md** - Data Provider Terms Documentation
   - Complete terms for 30+ data providers
   - Rate limits, attribution requirements, usage restrictions
   - Compliance summary table
   - Provider contact information

4. **privacy-policy.md** - Privacy Policy
   - CCPA and GDPR compliant
   - Public records exceptions
   - User privacy rights
   - Data retention policies

5. **README.md** - Documentation Guide
   - Maintenance procedures
   - Compliance philosophy
   - Update schedule

### 2. Key Compliance Achievements

The Terms of Service now incorporate the MOST RESTRICTIVE requirements from ALL data providers:

#### Charity Navigator (Most Restrictive)
- ✅ MANDATORY attribution: "Powered by Charity Navigator"
- ✅ MANDATORY linkbacks to CN profile pages
- ✅ MANDATORY trademark notice
- ❌ STRICT 1,000 API calls/day limit
- ❌ NO redistribution
- ❌ NO competing rating systems

#### Google Services
- ✅ Attribution: "Data provided by Google"
- ❌ Civic API: Cannot cache beyond 30 days
- ❌ Must comply with Google Cloud ToS

#### ProPublica
- ✅ Attribution to ProPublica required
- ❌ **CRITICAL:** FEC data cannot be used for commercial solicitation

#### Open States
- ✅ Attribution: "Powered by Open States"
- ❌ 50,000 requests/month free tier

#### DBpedia
- ✅ Attribution to DBpedia and Wikipedia
- ✅ CC BY-SA 3.0 share-alike license applies

### 3. Complete Provider Coverage

Terms documented for:

**U.S. Government (Public Domain):**
- IRS (EO-BMF, Form 990)
- U.S. Census Bureau
- NCES (National Center for Education Statistics)
- FEC / OpenFEC
- Grants.gov

**Google Services:**
- Google BigQuery IRS 990 Public Dataset
- Google Civic Information API
- Google Data Commons

**Nonprofit Data:**
- Charity Navigator (STRICT terms)
- ProPublica Nonprofit Explorer
- ProPublica Congress API
- ProPublica Campaign Finance API
- ProPublica Vital Signs API
- Every.org
- GivingTuesday 990 Data Lake

**Civic & Government APIs:**
- Open States API
- Wikidata
- DBpedia

**Academic & Research:**
- MeetingBank Dataset
- LocalView (Harvard Dataverse)
- Council Data Project
- City Scrapers / Documenters.org
- Roper Center for Public Opinion Research

**Election Data:**
- MIT Election Data + Science Lab
- OpenElections

**Reference (Not Used):**
- Ballotpedia (paid service - reference only)

## 🚨 Critical Restrictions Documented

### Cannot Do (Would Violate Terms)
1. ❌ Use FEC campaign finance contributor data for commercial solicitation or fundraising
2. ❌ Redistribute Charity Navigator data
3. ❌ Create competing rating systems using Charity Navigator data
4. ❌ Cache Google Civic API data beyond 30 days
5. ❌ Exceed rate limits (1,000/day for Charity Navigator, 50,000/month for Open States, etc.)
6. ❌ Remove or obscure required attribution notices
7. ❌ Claim endorsement by any data provider or government agency

### Must Do (Required by Terms)
1. ✅ Display "Powered by Charity Navigator" on ALL pages using CN data
2. ✅ Link charity names to Charity Navigator profile pages
3. ✅ Include Charity Navigator trademark notice
4. ✅ Display "Data provided by Google" for Google services
5. ✅ Display "Powered by Open States" for Open States data
6. ✅ Attribute to DBpedia and Wikipedia for DBpedia data
7. ✅ Provide attribution to ProPublica for all ProPublica APIs
8. ✅ Respect all rate limits and quotas
9. ✅ Set descriptive User-Agent headers for APIs

## 📊 Legal Structure

### Hierarchy
```
Terms of Service (main agreement)
├─ Incorporates → Data Provider Terms (all providers)
├─ References → Privacy Policy
└─ Links to → Legal Compliance (technical)
```

### Most Restrictive Principle
Where provider terms conflict, the MOST RESTRICTIVE applies:
- Example: If Provider A allows 10k/day and Provider B allows 1k/day
- Users must respect both limits for their respective data
- Cannot mix data to circumvent restrictions

## 🔒 Privacy Highlights

### What We Collect
- ✅ Public data only (government records, tax filings)
- ✅ Optional account data (email if you create account)
- ✅ Technical data (IP, browser for security)

### What We DON'T Collect
- ❌ Private financial information
- ❌ Health information
- ❌ Social Security numbers
- ❌ Any data requiring authentication

### User Rights
- ✅ Request data removal (case-by-case for public records)
- ✅ Delete account anytime
- ✅ Access and download your data
- ✅ Opt out of analytics
- ✅ CCPA rights (California residents)
- ✅ GDPR rights (EEA residents)

## 📁 File Locations

All legal documents are in: `website/docs/legal/`

```
website/docs/legal/
├── index.md                    # Legal Overview
├── terms-of-service.md         # Main ToS
├── data-provider-terms.md      # Provider terms
├── privacy-policy.md           # Privacy policy
└── README.md                   # Documentation guide
```

Updated existing file:
```
website/docs/legal-compliance.md  # Now links to new legal docs
```

## 🎯 Next Steps

### For Users
1. Read [Terms of Service](./terms-of-service.md)
2. Understand [Data Provider Terms](./data-provider-terms.md) for sources you use
3. Review [Privacy Policy](./privacy-policy.md) for privacy practices

### For Developers
1. Implement required attributions (especially Charity Navigator)
2. Set up rate limiting for all APIs
3. Configure User-Agent headers
4. Implement cache TTL enforcement
5. Add attribution UI components to frontend

### For Deployment
1. ✅ Replace placeholder contact information
2. ✅ Add physical mailing address
3. ✅ Specify governing jurisdiction
4. ✅ Configure DPO contact (if EU users)
5. ✅ Test all attribution displays
6. ✅ Verify rate limit enforcement
7. ✅ Review legal pages in production

## 🔗 Related Documents

- [Legal Documentation Complete](./legal-documentation-complete.md)
- [Legal Compliance Guide](../legal-compliance.md)
- [Data Sources Documentation](../data-sources/)
