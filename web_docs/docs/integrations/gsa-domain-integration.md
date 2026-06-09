---
title: GSA .gov Domain Integration
---

# GSA .gov Domain Integration

## Overview

This document describes the integration of **GSA (General Services Administration) .gov domain data** into the `jurisdictions_details_search` table.

**Data Source:** https://github.com/cisagov/dotgov-data

**Type of Load:** **ENRICHMENT/UPDATE LOAD**
- Does **NOT** create new jurisdiction records
- **Adds** official .gov domain information to existing jurisdictions
- **Updates** records with GSA-verified government contact data

---

## Data Fields Added

### New Columns in `jurisdictions_details_search`

| Column | Type | Description |
|--------|------|-------------|
| `gov_domains` | JSONB | Array of all official .gov domains registered to this jurisdiction |
| `security_contact_email` | TEXT | Official security/technical contact email from GSA registry |
| `gsa_organization_name` | TEXT | Official organization name as registered with GSA |
| `gsa_domain_type` | TEXT | GSA classification (City, County, State, Special District, etc.) |
| `gsa_last_updated` | TIMESTAMP | When GSA data was last loaded |

### GSA Source Data Fields

The GSA dataset contains:
- **Domain name** (e.g., "bostonma.gov")
- **Domain type** (Federal, State, County, City, Township, Special District, School District)
- **Organization name** (official registered name)
- **Suborganization name** (departments, divisions)
- **City** (jurisdiction location)
- **State** (2-letter code)
- **Security contact email** (technical/security contact)

---

## Matching Strategy

### City Matching
Matches by **normalized city name + state code**:
```python
# Examples:
"Town of Abington, MA" -> normalized to "abington" + "MA"
"City of Boston, MA" -> normalized to "boston" + "MA"
```

Common prefixes removed during normalization:
- "City of "
- "Town of "
- "Village of "
- "Township of "
- "Borough of "

### County Matching
Matches by **county name + state code**:
```python
# Examples:
"King County, WA" -> normalized to "king county" + "WA"
"Suffolk County, MA" -> normalized to "suffolk county" + "MA"
```

---

## Coverage Statistics (6 Dev States)

### Overall Summary
- **Total jurisdictions checked:** 4,383
- **Matched with GSA domains:** 679 (15.5%)
- **No GSA match found:** 3,704 (84.5%)

### By State and Type

| State | Type | Total | With GSA | Coverage | With Contact Email |
|-------|------|-------|----------|----------|-------------------|
| **AL** | City | 594 | 115 | **19.4%** | 75 |
| AL | County | 67 | 0 | 0.0% | 0 |
| **GA** | City | 675 | 174 | **25.8%** | 104 |
| GA | County | 159 | 0 | 0.0% | 0 |
| **IN** | City | 976 | 85 | **8.7%** | 54 |
| IN | County | 92 | 0 | 0.0% | 0 |
| **MA** | City | 248 | 36 | **14.5%** | 29 |
| MA | County | 14 | 0 | 0.0% | 0 |
| **WA** | City | 639 | 124 | **19.4%** | 94 |
| WA | County | 39 | 0 | 0.0% | 0 |
| **WI** | City | 808 | 143 | **17.7%** | 102 |
| WI | County | 72 | 2 | 2.8% | 1 |

### Key Insights

✅ **Cities:** 8-26% have official .gov domains registered
- Best coverage: **Georgia (25.8%)**, **Alabama (19.4%)**, **Washington (19.4%)**
- Lowest coverage: **Indiana (8.7%)**

⚠️ **Counties:** Very low .gov domain registration
- Only **2 out of 443 counties** have .gov domains (0.5%)
- Counties typically use state-run websites or no dedicated domain

---

## Example Enriched Records

### City with Multiple Domains

```json
{
  "jurisdiction_name": "Monroe",
  "state_code": "WI",
  "jurisdiction_type": "city",
  "gov_domains": [
    "cityofmonroewi.gov",
    "pdmonroewi.gov",
    "townofclarnowi.gov",
    "townofjordanwi.gov",
    "townofmonroewi.gov",
    "townofsylvesterwi.gov"
  ],
  "security_contact_email": "rjacobson@cityofmonroe.org",
  "gsa_organization_name": "City of Monroe",
  "gsa_domain_type": "City",
  "website_url": "https://cityofmonroewi.gov"
}
```

### City with Security Contact

```json
{
  "jurisdiction_name": "Beloit",
  "state_code": "WI",
  "jurisdiction_type": "city",
  "gov_domains": [
    "beloitwi.gov",
    "newarkwi.gov",
    "townofbeloitwi.gov",
    "townofturtlewi.gov"
  ],
  "security_contact_email": "adminnotification@beloitwi.gov",
  "gsa_organization_name": "City of Beloit",
  "gsa_domain_type": "City"
}
```

---

## Scripts

### Main Loading Script
**File:** `scripts/datasources/gsa/load_gsa_domains_to_postgres.py`

**Usage:**
```bash
# Load all states
python scripts/datasources/gsa/load_gsa_domains_to_postgres.py

# Load specific states
python scripts/datasources/gsa/load_gsa_domains_to_postgres.py --states AL,GA,MA,WA

# Dry run (preview without updating)
python scripts/datasources/gsa/load_gsa_domains_to_postgres.py --states AL,GA --dry-run
```

**Features:**
- ✅ Downloads latest GSA data from GitHub (cached for 24 hours)
- ✅ Normalizes jurisdiction names for matching
- ✅ Batch updates with ON CONFLICT handling
- ✅ Dry-run mode for testing
- ✅ Comprehensive statistics and logging

### Database Schema Updates
```sql
-- Add columns (idempotent)
ALTER TABLE jurisdictions_details_search 
  ADD COLUMN IF NOT EXISTS gov_domains JSONB DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS security_contact_email TEXT,
  ADD COLUMN IF NOT EXISTS gsa_organization_name TEXT,
  ADD COLUMN IF NOT EXISTS gsa_domain_type TEXT,
  ADD COLUMN IF NOT EXISTS gsa_last_updated TIMESTAMP;

-- Create index for domain lookups
CREATE INDEX IF NOT EXISTS idx_jurisdiction_details_gov_domains 
  ON jurisdictions_details_search USING gin(gov_domains);
```

---

## Use Cases

### 1. Find Jurisdictions with Official Government Domains
```sql
SELECT 
    jurisdiction_name,
    state_code,
    gov_domains,
    website_url
FROM jurisdictions_details_search
WHERE jsonb_array_length(gov_domains) > 0
ORDER BY state_code, jurisdiction_name;
```

### 2. Get Security Contact for a Jurisdiction
```sql
SELECT 
    jurisdiction_name,
    security_contact_email,
    gsa_organization_name
FROM jurisdictions_details_search
WHERE jurisdiction_name ILIKE '%boston%'
  AND state_code = 'MA';
```

### 3. Find Jurisdictions with Multiple Domains
```sql
SELECT 
    jurisdiction_name,
    state_code,
    jsonb_array_length(gov_domains) as domain_count,
    gov_domains
FROM jurisdictions_details_search
WHERE jsonb_array_length(gov_domains) > 3
ORDER BY domain_count DESC;
```

### 4. Validate Website URLs Against GSA Registry
```sql
SELECT 
    jurisdiction_name,
    website_url,
    gov_domains,
    CASE 
        WHEN website_url IS NULL THEN 'No website'
        WHEN gov_domains ? REPLACE(REPLACE(website_url, 'https://', ''), 'http://', '') THEN 'GSA verified'
        ELSE 'Not in GSA registry'
    END as verification_status
FROM jurisdictions_details_search
WHERE jsonb_array_length(gov_domains) > 0
LIMIT 20;
```

---

## Limitations

### Low County Coverage
- **Only 0.5% of counties** have registered .gov domains
- Most counties use state-operated websites (e.g., `county.state.gov`)
- Some counties have no dedicated web presence

### City Name Variations
Some jurisdictions may not match due to:
- Inconsistent naming (GSA: "City of X" vs Census: "X city")
- Merged jurisdictions (one domain, multiple census places)
- Special characters or apostrophes

### Domain Ownership
- GSA data shows **registered** domains, not necessarily **active** websites
- Some domains may redirect to other sites
- Multiple domains may point to the same website

---

## Maintenance

### Update Frequency
- GSA updates the domain list **continuously** as new domains are registered
- Recommend running enrichment load: **Monthly** or **Quarterly**
- Cache is valid for **24 hours** to avoid excessive downloads

### Re-running the Load
The load is **idempotent** and safe to re-run:
```bash
# Updates existing records with latest GSA data
python scripts/datasources/gsa/load_gsa_domains_to_postgres.py --states AL,GA,IN,MA,WA,WI
```

### Monitoring
Check for stale data:
```sql
SELECT 
    state_code,
    COUNT(*) as jurisdictions_with_gsa,
    MAX(gsa_last_updated) as most_recent_update,
    MIN(gsa_last_updated) as oldest_update
FROM jurisdictions_details_search
WHERE gov_domains IS NOT NULL
GROUP BY state_code
ORDER BY state_code;
```

---

## Next Steps

### Potential Enhancements

1. **Expand to All 50 States**
   ```bash
   python scripts/datasources/gsa/load_gsa_domains_to_postgres.py
   # (no --states filter = all states)
   ```

2. **Domain Validation**
   - Check if domains are actually active (HTTP status)
   - Verify SSL certificates
   - Update `website_url` with verified primary domain

3. **County Domain Discovery**
   - Scrape state government portals for county websites
   - Check for `<county-name>.<state>.gov` patterns
   - Alternative sources: Wikipedia, county associations

4. **Integration with YouTube Discovery**
   - Cross-reference .gov domains with YouTube channel URLs
   - Identify official government channels
   - Flag non-governmental channels

---

## References

- **GSA Domain Data:** https://github.com/cisagov/dotgov-data
- **GSA .gov Registry:** https://get.gov/
- **CISA Domain Security:** https://www.cisa.gov/topics/cyber-threats-and-advisories/federal-network-resilience/dotgov-program
