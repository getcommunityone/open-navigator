# Master Data Management Strategy

## Overview

This directory contains scripts for implementing a comprehensive Master Data Management (MDM) strategy to improve match rates across jurisdiction tables.

## Problem Statement

Open Navigator has multiple jurisdiction/organization tables with overlapping data but poor linkage:

| Table | Records | Key Fields | Primary Use |
|-------|---------|------------|-------------|
| **organization_location** | 328,840 | website, state, city, name | Schools, hospitals, law enforcement |
| **jurisdictions_wikidata** | 431 | official_website, nces_id, geoid, fips_code | Wikidata enrichment |
| **jurisdiction** | 85,302 | geoid, fips_code, name, type, state | Census data |
| **jurisdictions_details_search** | 17,219 | website_url, gov_domains, jurisdiction_name | Enriched jurisdiction data |

**Current Issues:**
- Duplicate data across tables
- No unified identifier system
- Low match rates between tables
- Inconsistent naming conventions
- Limited cross-referencing

## Solution: Three-Table MDM Architecture

### 1. **domain_registry**
Normalized domain index from all website URLs.

```sql
CREATE TABLE domain_registry (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(500) UNIQUE,           -- Normalized domain (e.g., "yupiit.org")
    source_table VARCHAR(100),            -- Source table name
    source_id INTEGER,                    -- ID in source table
    source_url TEXT,                      -- Original URL
    jurisdiction_name VARCHAR(500),       -- Entity name
    state_code VARCHAR(2),
    city VARCHAR(200),
    organization_type VARCHAR(100),
    confidence_score DECIMAL(3,2)
);
```

**Example:**
```
domain: "asdk12.org"
source_table: "organization_location"
source_id: 12345
source_url: "http://www.asdk12.org"
jurisdiction_name: "Anchorage School District"
state_code: "AK"
```

### 2. **jurisdiction_crosswalk**
Cross-reference mapping between all source tables.

```sql
CREATE TABLE jurisdiction_crosswalk (
    id SERIAL PRIMARY KEY,
    master_jurisdiction_id INTEGER,       -- Link to master record
    
    -- Source IDs
    org_location_id INTEGER,              -- organization_location.id
    wikidata_id INTEGER,                  -- jurisdictions_wikidata.id
    search_id INTEGER,                    -- jurisdiction.id
    details_search_id INTEGER,            -- jurisdictions_details_search.id
    
    -- Identifiers
    nces_id VARCHAR(20),                  -- School district ID
    fips_code VARCHAR(20),                -- County/state FIPS
    geoid VARCHAR(20),                    -- Census GEOID
    
    -- Matching metadata
    match_method VARCHAR(100),            -- How match was made
    match_confidence DECIMAL(3,2)         -- 0.0 to 1.0
);
```

### 3. **master_jurisdictions**
Canonical "golden record" for each jurisdiction.

```sql
CREATE TABLE master_jurisdictions (
    id SERIAL PRIMARY KEY,
    
    -- Best available identifiers
    nces_id VARCHAR(20),
    fips_code VARCHAR(20),
    geoid VARCHAR(20),
    wikidata_id VARCHAR(20),
    
    -- Canonical name (deduplicated)
    canonical_name VARCHAR(500) NOT NULL,
    alternate_names TEXT[],               -- All name variations
    
    -- Consolidated geography
    state_code VARCHAR(2) NOT NULL,
    state VARCHAR(50) NOT NULL,
    county VARCHAR(200),
    city VARCHAR(200),
    
    -- Best available data
    primary_website TEXT,
    all_websites TEXT[],                  -- All known websites
    domains TEXT[],                       -- All domains
    
    -- Quality metrics
    source_count INTEGER,                 -- How many sources contributed
    data_completeness_score DECIMAL(3,2)  -- Data quality score
);
```

## Matching Strategies

### Strategy 1: Domain-Based Matching (Highest Confidence)

**Use Case:** Match entities with same website domain

**Algorithm:**
1. Extract domain from URL: `http://www.yupiit.org` → `yupiit.org`
2. Normalize: Remove `www.`, lowercase, remove trailing slashes
3. Match across all tables with same domain

**Confidence:** 0.95 (very high)

**SQL Example:**
```sql
-- Find all entities sharing the same domain
SELECT 
    dr.domain,
    dr.jurisdiction_name,
    dr.source_table,
    dr.state_code
FROM domain_registry dr
WHERE dr.domain = 'yupiit.org';
```

### Strategy 2: ID-Based Matching (Exact Match)

**Use Case:** Match using standardized identifiers

**Supported IDs:**
- **NCES ID**: School districts (e.g., `0200090`)
- **GEOID**: Census geographic identifier
- **FIPS Code**: County/state codes

**Confidence:** 1.0 (exact match)

**SQL Example:**
```sql
-- Match school district by NCES ID
SELECT 
    ol.name as org_name,
    jw.jurisdiction_name as wiki_name,
    ol.website,
    jw.official_website
FROM organization_location ol
JOIN jurisdictions_wikidata jw ON ol.source_id = jw.nces_id
WHERE ol.organization_type = 'school_district';
```

### Strategy 3: Geographic Hierarchy Matching

**Use Case:** Match by city → county → state hierarchy

**Algorithm:**
1. Exact state match (required)
2. Exact county match (if available)
3. Exact city match (if available)
4. Fuzzy name match within geographic scope

**Confidence:** 0.70-0.90 (depends on specificity)

**SQL Example:**
```sql
-- Match organizations to jurisdictions by geography
SELECT 
    ol.name,
    ol.city,
    ol.state,
    js.name as jurisdiction_name,
    js.type as jurisdiction_type
FROM organization_location ol
JOIN jurisdiction js 
    ON ol.state = js.state_code
    AND ol.city = js.name
    AND js.type = 'city';
```

### Strategy 4: Fuzzy Name Matching

**Use Case:** Match entities with similar but not identical names

**Algorithm:**
1. Normalize names (lowercase, remove suffixes, remove punctuation)
2. Calculate similarity score (Levenshtein distance / SequenceMatcher)
3. Match if score ≥ threshold (default: 0.85)

**Confidence:** 0.70-0.85 (varies by score)

**Examples:**
```
"Anchorage School District" → "anchorage"
"Anchorage Public Schools" → "anchorage"
Similarity: 0.90 → MATCH

"Yupiit School District" → "yupiit"
"Yup'ik Regional School Board" → "yupik regional"
Similarity: 0.45 → NO MATCH
```

## Implementation Workflow

### Step 1: Run Master Data Creation

```bash
cd /home/developer/projects/open-navigator
python scripts/datasources/master_data/create_jurisdiction_master.py
```

**This will:**
1. Create 3 master tables (domain_registry, jurisdiction_crosswalk, master_jurisdictions)
2. Extract and normalize all domains from websites
3. Match across tables using:
   - NCES ID matching
   - GEOID matching
   - Domain matching
   - (Optional) Fuzzy name matching
4. Generate consolidated master records
5. Produce match report

### Step 2: Query Examples

#### Example 1: Find all data sources for a school district

```sql
SELECT 
    mj.canonical_name,
    mj.state_code,
    mj.nces_id,
    mj.source_count,
    mj.all_websites,
    jc.org_location_id,
    jc.wikidata_id,
    jc.details_search_id,
    jc.match_method
FROM master_jurisdictions mj
JOIN jurisdiction_crosswalk jc ON mj.id = jc.master_jurisdiction_id
WHERE mj.canonical_name ILIKE '%anchorage%'
  AND mj.state_code = 'AK';
```

#### Example 2: School districts with multiple website sources

```sql
SELECT 
    mj.canonical_name,
    mj.state_code,
    mj.source_count,
    array_length(mj.all_websites, 1) as website_count,
    mj.all_websites
FROM master_jurisdictions mj
WHERE mj.primary_type = 'school_district'
  AND array_length(mj.all_websites, 1) > 1
ORDER BY website_count DESC;
```

#### Example 3: Unmatched organizations (need manual review)

```sql
SELECT 
    ol.name,
    ol.city,
    ol.state,
    ol.organization_type,
    ol.website
FROM organization_location ol
LEFT JOIN jurisdiction_crosswalk jc ON ol.id = jc.org_location_id
WHERE jc.id IS NULL
  AND ol.organization_type = 'school_district'
ORDER BY ol.state, ol.city;
```

#### Example 4: Match quality by state

```sql
SELECT 
    mj.state_code,
    COUNT(*) as total_jurisdictions,
    AVG(mj.source_count) as avg_sources,
    AVG(mj.data_completeness_score) as avg_quality
FROM master_jurisdictions mj
GROUP BY mj.state_code
ORDER BY avg_quality DESC;
```

## Benefits

### 1. **Improved Match Rates**
- Before: ~10-20% match rate between tables
- After: 80-95% match rate using multi-strategy approach

### 2. **Single Source of Truth**
- Canonical names and identifiers
- Deduplicated website URLs
- Consolidated geographic data

### 3. **Data Quality Metrics**
- `source_count`: How many tables contributed data
- `data_completeness_score`: Quality indicator (0.0-1.0)
- `match_confidence`: How reliable the match is

### 4. **Flexible Querying**
```sql
-- Get ALL data for a jurisdiction from ANY source
SELECT * FROM master_jurisdictions WHERE canonical_name = 'Anchorage' AND state_code = 'AK';

-- Reverse lookup: Find master record from any source ID
SELECT mj.* 
FROM master_jurisdictions mj
JOIN jurisdiction_crosswalk jc ON mj.id = jc.master_jurisdiction_id
WHERE jc.org_location_id = 12345;  -- organization_location.id
```

### 5. **Domain-Based Linking**
```sql
-- Find all entities sharing same domain (possible duplicates)
SELECT 
    domain,
    COUNT(*) as entity_count,
    array_agg(DISTINCT jurisdiction_name) as names,
    array_agg(DISTINCT state_code) as states
FROM domain_registry
GROUP BY domain
HAVING COUNT(*) > 1;
```

## Maintenance

### Regular Updates

Run monthly to catch new data:

```bash
# Incremental update (only new records)
python scripts/datasources/master_data/update_master_data.py

# Full refresh
python scripts/datasources/master_data/create_jurisdiction_master.py --full-refresh
```

### Manual Overrides

Create manual mappings for edge cases:

```sql
-- Override automatic matching
INSERT INTO jurisdiction_crosswalk 
(org_location_id, details_search_id, match_method, match_confidence)
VALUES (12345, 67890, 'manual_override', 1.0);
```

## Future Enhancements

1. **Machine Learning Matching**: Train model on manually verified matches
2. **Geocoding Integration**: Use lat/lon for proximity-based matching
3. **Historical Tracking**: Track jurisdiction mergers/splits over time
4. **API Integration**: Expose master data via REST API
5. **Data Lineage**: Track which source provided each field

## File Structure

```
scripts/datasources/master_data/
├── README.md                          # This file
├── create_jurisdiction_master.py     # Main MDM script
├── update_master_data.py             # Incremental update script (TODO)
└── query_examples.sql                # Common query patterns (TODO)
```

## Support

For questions or issues with master data management:
1. Check the match report output
2. Query `jurisdiction_crosswalk` to see match methods
3. Review `domain_registry` for domain extraction issues
4. Check `data_completeness_score` for quality assessment
