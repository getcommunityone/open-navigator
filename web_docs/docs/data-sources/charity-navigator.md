---
sidebar_position: 6
title: Charity Navigator API
description: Enrich nonprofit profiles with independent Charity Navigator star ratings, mission statements, websites, and active advisories.
tags: [data-source, nonprofits, commercial, api]
---

# Charity Navigator API

**Powered by Charity Navigator**

Enrich nonprofit profiles with independent ratings, mission statements, and organizational metrics from Charity Navigator's comprehensive database.

:::info At a glance
| | |
|---|---|
| **Provider** | Charity Navigator, Inc. |
| **Coverage** | U.S. registered nonprofits — all 1.9M with basics; ~200K rated |
| **Update cadence** | Annual rating refresh |
| **License** | Charity Navigator API Terms — attribution & link-back required (see "Legal & Compliance" below and the [Legal index](../legal/index.md)) |
| **Cost** | Free, capped at 1,000 API calls/day |
| **Access method** | GraphQL — `https://api.charitynavigator.org/graphql` (Bearer token) |
| **Our pipeline** | On-demand enrichment keyed by EIN; cached locally before merge into gold nonprofit tables |
:::

## Overview

Charity Navigator is America's largest and most-utilized independent nonprofit evaluator. Their API provides access to:

- **Star Ratings**: Independent 0-4 star ratings (Encompass Rating System)
- **Mission Statements**: Organization purpose and activities
- **Website URLs**: Official organization websites
- **Organizational Metrics**: Financial health, accountability, transparency
- **Active Advisories**: Important alerts about organization status

## Data Available

### Data Fields

The Charity Navigator GraphQL API provides the following fields for all registered nonprofits:

| Field | Description | Coverage |
|-------|-------------|----------|
| **EIN** | Employer Identification Number | 100% |
| **Charity Name** | Official organization name | 100% |
| **Mission** | Organization mission statement | Rated orgs only* |
| **Website URL** | Official website address | ~80% |
| **Charity Navigator URL** | Link to CN profile page | Rated orgs only* |
| **Category** | Nonprofit category | Rated orgs only* |
| **Cause** | Primary cause area | Rated orgs only* |
| **Address** | Street, City, State, Zip, Country | 100% |
| **Active Advisories** | Status alerts | All orgs |
| **Encompass Star Rating** | 0-4 star rating | Rated orgs only* |
| **Encompass Score** | Numerical rating score | Rated orgs only* |
| **Rating Publication Date** | When rating was published | Rated orgs only* |

*Fields marked with asterisk are only available for organizations that have been rated by Charity Navigator.

## Usage Limits & Compliance

### Rate Limits

- **Maximum**: 1,000 API calls per day
- **No bulk downloads**: Use incremental enrichment
- **Caching allowed**: For performance only (not redistribution)

### Attribution Requirements

**MANDATORY on all pages displaying Charity Navigator data:**

1. **Text Credit**: "Powered by Charity Navigator"
2. **Source Citation**: "Data provided by Charity Navigator"
3. **Linkback**: All charity names link to their Charity Navigator profile:
   ```html
   <a href="https://www.charitynavigator.org/ein/[EIN]">
     [Organization Name]
   </a>
   ```

4. **Trademark Notice** (once per page or in credits):
   ```
   CHARITY NAVIGATOR and the CHARITY NAVIGATOR logo are registered trademarks 
   of Charity Navigator. All rights reserved. Used with permission.
   ```

### Link Requirements

- Use descriptive anchor text (not "click here")
- Do NOT use `rel="nofollow"` on Charity Navigator links
- Allow search engines to crawl all links to charitynavigator.org

**✅ Correct:**
```html
<a href="https://www.charitynavigator.org/ein/134141945">
  Michael J. Fox Foundation for Parkinson's Research
</a>
```

**❌ Incorrect:**
```html
<a href="https://www.CharityNavigator.org/ein/134141945" rel="nofollow">
  Click here
</a>
```

## Star Rating Display

When displaying Charity Navigator star ratings, use official images:

### Star Images (PNG format, 239×54px)

| Rating | Image URL |
|--------|-----------|
| 4-Star | `https://www.charitynavigator.org/content/dam/cn/cn/icons/four_star.png` |
| 3-Star | `https://www.charitynavigator.org/content/dam/cn/cn/icons/three_star.png` |
| 2-Star | `https://www.charitynavigator.org/content/dam/cn/cn/icons/two_star.png` |
| 1-Star | `https://www.charitynavigator.org/content/dam/cn/cn/icons/one_star.png` |
| 0-Star | `https://www.charitynavigator.org/content/dam/cn/cn/icons/zero_star.png` |

### SVG Format (Vectors)

Replace `.png` with `.svg` in the URLs above for scalable vector graphics.

### Display Guidelines

- Star images **MUST** link to the charity's Charity Navigator profile page
- Do NOT stretch or skew images (maintain aspect ratio)
- Prefer full-color versions; ensure knockout (white) versions pass accessibility tests

**Example HTML:**
```html
<a href="https://www.charitynavigator.org/ein/134141945">
  <img src="https://www.charitynavigator.org/content/dam/cn/cn/icons/four_star.png" 
       alt="Four-star rating by Charity Navigator" />
</a>
```

## Integration Example

### Python with Requests

```python
import requests

# GraphQL API endpoint
url = "https://api.charitynavigator.org/graphql"

# Example query
query = """
query {
  charity(ein: "134141945") {
    ein
    charityName
    mission
    websiteUrl
    charityNavigatorUrl
    category
    cause
    mailingAddress {
      streetAddress1
      city
      state
      postalCode
    }
    currentRating {
      rating
      ratingDate
    }
  }
}
"""

headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

response = requests.post(url, json={"query": query}, headers=headers)
data = response.json()

print(f"Charity: {data['data']['charity']['charityName']}")
print(f"Rating: {data['data']['charity']['currentRating']['rating']} stars")
print(f"Mission: {data['data']['charity']['mission']}")
```

### Enrichment Workflow

1. **Extract EINs** from your nonprofit dataset
2. **Batch requests** (max 1,000/day)
3. **Cache responses** locally to avoid re-fetching
4. **Merge data** into your gold tables
5. **Track update date** to know when to refresh

## Data Comparison

### Charity Navigator vs Other Sources

| Data Field | Charity Navigator | IRS EO-BMF | Form 990 XML | BigQuery |
|------------|-------------------|------------|--------------|----------|
| **Star Rating** | ✅ (0-4 stars) | ❌ | ❌ | ❌ |
| **Mission** | ✅ (Rated orgs) | ❌ | ✅ (30-40%) | ✅ (30-40%) |
| **Website** | ✅ (~80%) | ❌ | ❌ | ✅ (30-40%) |
| **Financials** | ✅ (Summary) | ❌ | ✅ (Detailed) | ✅ (Detailed) |
| **Coverage** | ~200K rated | 1.9M orgs | ~300K/year | 5M+ records |
| **Update Freq** | Annual | Monthly | Annual | Annual |
| **Independent Rating** | ✅ **UNIQUE** | ❌ | ❌ | ❌ |

**Key Advantages:**
- ✅ **Only source** with independent star ratings
- ✅ High-quality mission statements (manually reviewed)
- ✅ Better website URL coverage than Form 990
- ✅ Active advisories (warnings, alerts)
- ✅ Nonprofit evaluation methodology is transparent

**Limitations:**
- Only ~200K organizations have ratings (largest orgs prioritized)
- Smaller nonprofits may not have Charity Navigator profiles
- 1,000 API calls/day limit (use caching strategically)

## Best Practices

### Rate Limit Management

```python
import time
from datetime import datetime, timedelta

class CharityNavigatorClient:
    def __init__(self, api_key, daily_limit=1000):
        self.api_key = api_key
        self.daily_limit = daily_limit
        self.call_count = 0
        self.reset_time = datetime.now() + timedelta(days=1)
    
    def query(self, ein):
        # Check if we've hit the daily limit
        if self.call_count >= self.daily_limit:
            wait_seconds = (self.reset_time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                print(f"Rate limit reached. Waiting {wait_seconds:.0f}s...")
                time.sleep(wait_seconds)
                self.call_count = 0
                self.reset_time = datetime.now() + timedelta(days=1)
        
        # Make API call
        response = self._make_request(ein)
        self.call_count += 1
        
        return response
```

### Caching Strategy

Cache responses to avoid redundant API calls:

```python
import json
from pathlib import Path

cache_dir = Path("data/cache/charity_navigator/")
cache_dir.mkdir(parents=True, exist_ok=True)

def get_charity_data(ein, api_client):
    cache_file = cache_dir / f"{ein}.json"
    
    # Check cache first
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    
    # Fetch from API
    data = api_client.query(ein)
    
    # Save to cache
    with open(cache_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data
```

### Incremental Updates

Only fetch new/updated ratings:

```python
import pandas as pd
from datetime import datetime, timedelta

def needs_update(last_updated, max_age_days=90):
    """Check if rating needs refresh (default: every 90 days)"""
    if pd.isna(last_updated):
        return True
    
    age = datetime.now() - pd.to_datetime(last_updated)
    return age > timedelta(days=max_age_days)

# Filter nonprofits needing updates
nonprofits = pd.read_parquet("data/gold/nonprofits.parquet")
needs_refresh = nonprofits[
    nonprofits['cn_updated_date'].apply(needs_update)
]

print(f"Need to refresh: {len(needs_refresh):,} organizations")
```

## Schema

### Fields to Add to Gold Tables

When enriching your nonprofit dataset, add these fields:

```python
enriched_fields = {
    'cn_star_rating': 'int64',          # 0-4 stars
    'cn_encompass_score': 'float64',    # Numerical score
    'cn_rating_date': 'datetime64',     # When rated
    'cn_mission': 'string',             # Mission statement
    'cn_website': 'string',             # Website URL
    'cn_category': 'string',            # Category
    'cn_cause': 'string',               # Cause area
    'cn_profile_url': 'string',         # Link to CN profile
    'cn_advisory_status': 'string',     # Active advisories
    'cn_updated_date': 'datetime64',    # When we fetched data
}
```

## Cost

**FREE** with the following limits:
- 1,000 API calls per day
- Beta offering (no fees)
- Nonprofit use case

For commercial use or higher volume, contact Charity Navigator: api@charitynavigator.org

## Legal & Compliance

### API Terms of Use

By using the Charity Navigator API, you agree to:

1. **Rate Limits**: Max 1,000 calls/day
2. **Attribution**: Display "Powered by Charity Navigator" on all pages
3. **Linkbacks**: Link all charity names to their CN profiles
4. **Trademark**: Include trademark notice
5. **No Redistribution**: Cannot resell or redistribute CN data
6. **No Derivative Ratings**: Cannot create competing rating systems
7. **Caching**: Only for performance, not redistribution
8. **Termination**: CN can terminate access for violations

### Intellectual Property

- All Charity Navigator data and ratings are proprietary
- API and database owned by Charity Navigator, Inc.
- Users have no ownership rights to cached data
- Feedback/suggestions become CN property

### Full Terms

Complete API Terms of Use: https://www.charitynavigator.org/partner/api-terms

## Troubleshooting

### "No rating available"

Not all nonprofits have Charity Navigator ratings. The service prioritizes:
- Larger organizations (>$1M revenue)
- National/regional nonprofits
- Organizations with public interest

**Solution**: Check for `null` ratings and gracefully handle unrated orgs.

### "Rate limit exceeded"

```
Error: Maximum daily API calls (1,000) reached
```

**Solution**: 
- Implement caching (see above)
- Process in batches over multiple days
- Prioritize most important organizations first

### "Invalid EIN"

```
Error: Organization not found
```

**Possible causes:**
- EIN typo or formatting error
- Organization not in CN database
- Inactive/dissolved organization

**Solution**: Validate EINs before querying, handle 404s gracefully.

## Support

- **API Documentation**: https://www.charitynavigator.org/partner/api
- **Technical Support**: api@charitynavigator.org
- **Website**: https://www.charitynavigator.org
- **Phone**: (201) 818-1288

## Related Documentation

- [IRS Form 990 XML](./form-990-xml.md)
- [GivingTuesday Data Lake](https://github.com/getcommunityone/open-navigator/blob/main/scripts/enrichment/enrich_nonprofits_gt990.py)
- [BigQuery Integration](https://github.com/getcommunityone/open-navigator/blob/main/docs/BIGQUERY_ENRICHMENT.md)
- [Citations](./citations.md)

---

**Trademark Notice:** CHARITY NAVIGATOR and the CHARITY NAVIGATOR logo are registered trademarks of Charity Navigator. All rights reserved. Used with permission.
