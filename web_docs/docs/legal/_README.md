# Legal Documentation

This directory contains all legal policies and terms of service for Open Navigator.

## 📋 Documents

### User-Facing Legal Policies

1. **[index.md](./index.md)** - Legal Overview & Quick Reference
   - Landing page for legal section
   - Quick compliance checklist
   - Summary of all legal requirements

2. **[terms-of-service.md](./terms-of-service.md)** - Terms of Service
   - Main legal agreement governing use of the Service
   - Incorporates all third-party provider terms
   - Acceptable use policies
   - Limitation of liability
   - **CRITICAL:** Most restrictive terms from all providers apply

3. **[data-provider-terms.md](./data-provider-terms.md)** - Data Provider Terms of Service
   - Comprehensive documentation of ALL third-party provider terms
   - Rate limits, attribution requirements, usage restrictions
   - Compliance summary table
   - Contact information for each provider

4. **[privacy-policy.md](./privacy-policy.md)** - Privacy Policy
   - How we collect, use, and protect information
   - Your privacy rights (CCPA, GDPR)
   - Public records exceptions
   - Data retention policies

## 🚨 Critical Compliance Requirements

### Charity Navigator (MOST RESTRICTIVE)
- ✅ **MUST** display "Powered by Charity Navigator" on ALL pages using their data
- ✅ **MUST** link charity names to CN profile pages
- ✅ **MUST** include trademark notice
- ❌ Maximum 1,000 API calls per day (STRICT)
- ❌ NO redistribution of CN data
- ❌ NO competing rating systems

### Google Services
- ✅ **MUST** display "Data provided by Google"
- ❌ Civic API data CANNOT be cached beyond 30 days
- ❌ Must comply with Google Cloud Terms of Service

### ProPublica
- ✅ **MUST** provide attribution to ProPublica
- ❌ **CRITICAL:** FEC Campaign Finance data CANNOT be used for commercial solicitation

### Open States
- ✅ **MUST** display "Powered by Open States"
- ❌ 50,000 requests/month free tier

### DBpedia
- ✅ **MUST** attribute to DBpedia and Wikipedia
- ✅ CC BY-SA 3.0 (share-alike applies to derivative works)

## 📊 Compliance Philosophy

**Most Restrictive Terms Apply:**
- Our Terms of Service incorporate requirements from ALL data providers
- Where multiple providers have conflicting terms, the MOST RESTRICTIVE applies
- Users must comply with ALL applicable provider terms

**Example:**
- If Provider A allows 10,000 API calls/day
- And Provider B allows only 1,000 API calls/day
- And you use both: You must respect the 1,000/day limit for Provider B's data

## 🔄 Maintenance

### Review Schedule
- **Quarterly:** Review all provider terms for changes
- **As needed:** Update when providers announce ToS changes
- **Version control:** All changes tracked via Git

### How to Update

1. **Check provider websites** for updated terms
2. **Update corresponding section** in data-provider-terms.md
3. **Update version date** and last review date
4. **Test documentation build** to ensure no broken links
5. **Commit with clear message** describing changes

### Monitoring Provider Changes

**Automated monitoring (planned):**
- GitHub Actions to check provider ToS pages
- Alerts when changes detected
- Quarterly reminder to review all terms

**Manual monitoring:**
- Subscribe to provider newsletters
- Watch provider GitHub repositories
- Monitor civic tech forums for ToS discussions

## 📞 Questions & Issues

**For users asking about compliance:**
- Direct to [Legal Overview](./index.md) first
- Specific questions → [Data Provider Terms](./data-provider-terms.md)
- Privacy questions → [Privacy Policy](./privacy-policy.md)

**For reporting compliance issues:**
- GitHub Issues: https://github.com/getcommunityone/open-navigator-for-engagement/issues
- Label: `legal` or `compliance`
- Email: [contact email] for sensitive matters

## 🎯 Quick Links

**For Developers:**
- [Legal Overview](./index.md) - Start here
- [Data Provider Terms](./data-provider-terms.md) - Technical details
- [../legal-compliance.md](../legal-compliance.md) - Implementation details

**For Users:**
- [Terms of Service](./terms-of-service.md) - Your agreement
- [Privacy Policy](./privacy-policy.md) - Your privacy
- [Legal Overview](./index.md) - Quick reference

**For Data Users:**
- [Data Provider Terms](./data-provider-terms.md) - All provider requirements
- [../data-sources/citations.md](../data-sources/citations.md) - Academic citations
- [Terms of Service](./terms-of-service.md) - Your obligations

## 📚 Related Documentation

- **[Citations & Data Sources](../data-sources/citations.md)** - Academic citations
- **[Legal Compliance (Technical)](../legal-compliance.md)** - Implementation details
- **[GitHub LICENSE](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/LICENSE)** - Software license (MIT)

---

**Last Updated:** April 28, 2026  
**Version:** 1.0
