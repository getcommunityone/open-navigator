---
sidebar_position: 5
sidebar_label: Adding New Data Sources
---

# Adding New Data Sources - Compliance Checklist

:::tip[Use This Checklist]
**Before integrating any new data source**, work through this checklist to ensure legal compliance, proper attribution, and best practices.
:::

## ✅ Pre-Integration Checklist

### 1. Legal Review

- [ ] **Find and read the Terms of Service**
  - API Terms of Service URL: _________________
  - Data Usage Policy URL: _________________
  - Last reviewed: _________________

- [ ] **Verify the data is legally accessible**
  - [ ] Public domain (U.S. Government data)
  - [ ] Open license (CC0, CC-BY, MIT, etc.)
  - [ ] Free API with terms of service
  - [ ] Paid API with commercial license

- [ ] **Check for usage restrictions**
  - [ ] No restrictions on commercial use
  - [ ] No restrictions on redistribution
  - [ ] No prohibition on caching/storage
  - [ ] No requirement for user consent/opt-in

- [ ] **Identify attribution requirements**
  - Required attribution text: _________________
  - Logo/trademark requirements: _________________
  - Link-back requirements: _________________

### 2. API Access & Rate Limits

- [ ] **API Key Requirements**
  - [ ] No API key required ✅
  - [ ] Free API key (document registration process)
  - [ ] Paid API key (not recommended for open-source project)

- [ ] **Rate Limits**
  - Requests per second: _________________
  - Requests per day: _________________
  - Requests per month: _________________
  - Recommended delay between requests: _________________

- [ ] **User-Agent Requirements**
  - [ ] Custom User-Agent required
  - [ ] Contact email required
  - [ ] Project URL required

### 3. Data Privacy & Personal Information

- [ ] **Data Type Classification**
  - [ ] Public records only (government data)
  - [ ] Aggregated statistics only (no individuals)
  - [ ] Individual-level data from public sources
  - [ ] Personal information requiring consent (AVOID)

- [ ] **Privacy Compliance**
  - [ ] Data is public record
  - [ ] No personal financial information
  - [ ] No health information (PHI)
  - [ ] No authentication required to access original data

- [ ] **GDPR Considerations**
  - [ ] Right to be forgotten process documented
  - [ ] Legal basis identified (public interest, legitimate interest)
  - [ ] Data minimization applied

### 4. Technical Requirements

- [ ] **API Documentation**
  - API documentation URL: _________________
  - SDK/client library available: _________________
  - Code examples available: _________________

- [ ] **Data Format**
  - Response format (JSON, XML, CSV): _________________
  - Pagination supported: Yes / No
  - Batch operations supported: Yes / No

- [ ] **Error Handling**
  - [ ] Rate limit error codes documented
  - [ ] Retry strategy defined
  - [ ] Timeout handling planned

---

## 📝 Implementation Checklist

### 1. Create Integration Module

Create file: `discovery/{source_name}_integration.py`

**Required docstring elements:**
```python
"""
[Source Name] Integration

[Brief description of what this source provides]

Data Source: [Official URL]
API Documentation: [API docs URL]
Terms of Use: [Terms of Service URL]
License: [Data license]

Key Features:
- Feature 1
- Feature 2
- Feature 3

Use Cases:
- Use case 1
- Use case 2

Author: Open Navigator
License: MIT
"""
```

### 2. Implement Rate Limiting

```python
import time
import asyncio

class DataSourceClient:
    def __init__(self):
        self.request_delay = 1.0  # seconds between requests
        self.last_request_time = 0
    
    async def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
```

### 3. Set User-Agent Header

```python
self.session.headers.update({
    'User-Agent': 'CommunityOne/1.0 (Civic Engagement Platform; https://communityone.com/)',
    'Accept': 'application/json',
})
```

### 4. Handle API Keys Securely

**Add to `.env.example`:**
```bash
# [Source Name] API Key
# Get your key at: [Registration URL]
# Free tier: [Quota details]
[SOURCE]_API_KEY=your-api-key-here
```

**Load from environment:**
```python
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('[SOURCE]_API_KEY')
if not api_key:
    logger.warning("⚠️  [SOURCE]_API_KEY not found")
```

### 5. Add Error Handling

```python
try:
    response = await self.session.get(url)
    response.raise_for_status()
    return response.json()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:  # Rate limited
        logger.warning(f"Rate limited, waiting...")
        await asyncio.sleep(60)
        return await self._fetch(url)  # Retry
    else:
        logger.error(f"HTTP error: {e}")
        raise
except Exception as e:
    logger.error(f"Failed to fetch data: {e}")
    raise
```

---

## 📚 Documentation Checklist

### 1. Update Legal Compliance Document

Add to: `website/docs/legal-compliance.md`

**Template:**
```markdown
### [Source Name]

**Data Type:** [Description]
**Source:** [Official URL]
**API Documentation:** [API docs URL]
**License:** [License type]
**Terms of Use:** [ToS URL]

**Compliance Status:** ✅ **COMPLIANT** / ⚠️ **NOT USED**
- [Key compliance point 1]
- [Key compliance point 2]
- API key requirement: Yes/No
- Rate limit: [Details]

**Implementation:** `discovery/[filename].py`

**Use Policy Key Points:**
- [Policy point 1]
- [Policy point 2]
- [Attribution requirements]

**Environment Variable:**
```bash
[SOURCE]_API_KEY=your-api-key-here
```
```

### 2. Update Citations Page

Add to: `website/docs/data-sources/citations.md`

**Template:**
```markdown
### [Source Name]

**Organization:** [Organization name]
**What we use:** [Description of how we use this data]

- **Source:** [Official URL]
- **API Documentation:** [API docs URL]
- **Coverage:** [Geographic/temporal coverage]
- **License:** [License details]
- **Access:** [API key requirements]

**BibTeX:**
```bibtex
@misc{[citation_key],
  author = {{[Organization Name]}},
  title = {[Dataset/API Name]},
  year = {2026},
  url = {[Official URL]},
  note = {Accessed: 2026}
}
```
```

### 3. Update API Integration Status

Add to: `docs/API_INTEGRATION_STATUS.md`

Document integration status, free vs paid, key requirements, and code examples.

### 4. Add Usage Examples

Create or update: `examples/demo_[source_name].py`

```python
#!/usr/bin/env python3
"""
Example: [Source Name] Integration

Demonstrates how to fetch data from [Source Name] API.
"""

import asyncio
from discovery.[source_name]_integration import [ClassName]

async def main():
    """Example usage"""
    client = [ClassName](api_key="your-key-here")
    
    # Example query
    results = await client.fetch_data(param="value")
    
    print(f"Found {len(results)} results")
    for item in results[:5]:
        print(f"  - {item}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🧪 Testing Checklist

### 1. Unit Tests

- [ ] Test API client initialization
- [ ] Test successful data fetch
- [ ] Test rate limiting
- [ ] Test error handling (404, 500, 429)
- [ ] Test API key validation

### 2. Integration Tests

- [ ] Test with real API (if free tier available)
- [ ] Test with demo/sandbox environment
- [ ] Verify data format matches schema
- [ ] Test pagination (if applicable)

### 3. Compliance Tests

- [ ] Verify User-Agent is set correctly
- [ ] Verify rate limiting is enforced
- [ ] Verify attribution is included in output
- [ ] Verify no API keys in logs or code

---

## 🚀 Pre-Deployment Checklist

### 1. Code Review

- [ ] Code follows project style guidelines
- [ ] Type hints added for all functions
- [ ] Docstrings complete and accurate
- [ ] No hardcoded credentials
- [ ] No debug print statements

### 2. Documentation Review

- [ ] Legal compliance doc updated
- [ ] Citations page updated
- [ ] API integration status updated
- [ ] Usage examples created
- [ ] README updated (if needed)

### 3. Security Review

- [ ] No API keys in code
- [ ] Environment variables documented in `.env.example`
- [ ] User-Agent identifies project
- [ ] Rate limiting prevents abuse
- [ ] Error messages don't leak sensitive info

### 4. License Review

- [ ] Data source license compatible with MIT
- [ ] Attribution requirements documented
- [ ] Terms of service compliance verified
- [ ] Commercial use permitted (or documented as reference only)

---

## 📋 Quick Reference: Data Source Types

### ✅ RECOMMENDED: Public Domain Government Data

**Examples:** IRS, Census Bureau, NCES, Grants.gov

**Characteristics:**
- No API key required (usually)
- Public domain - no restrictions
- Free unlimited access
- No attribution required (but recommended)

**Best for:** Production use, open-source projects

---

### ✅ RECOMMENDED: Free Public APIs (API Key Required)

**Examples:** Open States, Google Civic API, Wikidata, DBpedia

**Characteristics:**
- Free API key registration
- Generous free tier quotas
- Open license or public domain data
- Attribution required

**Best for:** Production use with proper attribution

---

### ⚠️ CAUTION: Free APIs with Restrictions

**Examples:** ProPublica, FEC (contributor restrictions)

**Characteristics:**
- Free access but with usage restrictions
- May prohibit commercial use of certain data
- May have low rate limits
- May require approval process

**Best for:** Research, education, limited production use

---

### ❌ AVOID: Paid Commercial APIs

**Examples:** Ballotpedia API, Cicero API

**Characteristics:**
- Requires paid subscription
- Not suitable for open-source projects
- May have restrictive terms

**Best for:** Reference implementations only, enterprise deployments

---

## 🔗 Resources

- [Legal Compliance Documentation](../legal-compliance.md)
- [Citations & Data Sources](../data-sources/citations.md)
- [API Integration Status](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/docs/API_INTEGRATION_STATUS.md)
- [Project License (MIT)](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/LICENSE)

---

## 📞 Questions?

If you're unsure about legal compliance for a data source:

1. **Check the Terms of Service** - Start here always
2. **Look for similar integrations** - See how other open-source projects use it
3. **Ask the community** - Open a GitHub Discussion
4. **Consult legal counsel** - When in doubt, especially for commercial use

---

:::warning[When in Doubt, Don't Integrate]
If you cannot clearly verify that a data source:
- Is legally accessible
- Permits commercial use and redistribution
- Has acceptable rate limits and API quotas
- Doesn't violate privacy laws

**DO NOT INTEGRATE IT.** Mark it as "reference only" or find a free alternative.
:::
