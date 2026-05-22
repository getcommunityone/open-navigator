# NTEE (National Taxonomy of Exempt Entities) Data Source

## Overview

NTEE codes are used by the IRS and nonprofit sector to classify tax-exempt organizations by their mission and activities. This taxonomy helps categorize the 1.8 million nonprofits in the United States.

**Data Source:** IRS Publication 557 + NCCS (National Center for Charitable Statistics)  
**Records:** 196 classification codes  
**Update Frequency:** Annually (taxonomy is relatively stable)
**Database Table:** `cause_ntee` (with `cause_type = 'ntee'`)

## NTEE Code Structure

NTEE codes are hierarchical:

- **Level 1 - Major Groups** (26 codes): Single letters A-Z
  - Example: `A` = Arts, Culture, and Humanities
  - Example: `E` = Health
  - Example: `K` = Food, Agriculture, and Nutrition

- **Level 2 - Divisions** (10 per major group)
  - Example: `A20` = Arts, Cultural Organizations - Multipurpose
  - Example: `E20` = Hospitals and Primary Medical Care Facilities

- **Level 3 - Subdivisions** (More specific classifications)
  - Example: `A23` = Cultural, Ethnic Awareness
  - Example: `E24` = Hospitals

## Files in This Directory

### Scripts

- **`load_to_postgres.py`** - Load NTEE codes from parquet into PostgreSQL
  - Loads into `cause_ntee` table (with `cause_type = 'ntee'`)
  - Supports local and Neon cloud databases
  - Creates full-text search indexes

### Data Files

- **Input:** `data/gold/causes_ntee_codes`
- **Output:** `cause_ntee` table in PostgreSQL (196 NTEE codes with `cause_type = 'ntee'`)

## Usage

### Load NTEE Codes

```bash
# Load to local database (default)
python scripts/datasources/ntee/load_to_postgres.py

# Load to Neon (production)
python scripts/datasources/ntee/load_to_postgres.py --neon

# Preview data without loading
python scripts/datasources/ntee/load_to_postgres.py --dry-run

# Load to custom database
python scripts/datasources/ntee/load_to_postgres.py --db-url postgresql://user:pass@host:port/dbname
```

### Query Examples

```sql
-- Get all NTEE codes
SELECT code, name, category 
FROM cause_ntee 
WHERE cause_type = 'ntee'
ORDER BY code;

-- Get all major groups (single letter codes)
SELECT code, name 
FROM cause_ntee 
WHERE cause_type = 'ntee' AND length(code) = 1 
ORDER BY code;

-- Find health-related codes
SELECT code, name 
FROM cause_ntee 
WHERE cause_type = 'ntee' AND code LIKE 'E%' 
ORDER BY code;

-- Full-text search for education
SELECT code, name 
FROM cause_ntee 
WHERE cause_type = 'ntee' AND to_tsvector('english', name) @@ to_tsquery('education')
ORDER BY code;

-- Count codes by major group
SELECT substring(code, 1, 1) as major_group, COUNT(*) 
FROM cause_ntee 
WHERE cause_type = 'ntee'
GROUP BY major_group 
ORDER BY major_group;

-- Get both NTEE and EveryOrg causes
SELECT code, name, cause_type, category
FROM cause_ntee
ORDER BY cause_type, code
LIMIT 20;
```

## Database Schema

```sql
CREATE TABLE cause_ntee (
    code VARCHAR(100) PRIMARY KEY,              -- NTEE code (e.g., 'A', 'E20') or cause slug (e.g., 'animals', 'climate')
    name TEXT NOT NULL,                         -- Human-readable name
    description TEXT,                           -- Detailed description
    cause_type VARCHAR(20) NOT NULL,            -- 'ntee' or 'everyorg'
    parent_code VARCHAR(100),                   -- For hierarchical relationships
    category VARCHAR(100),                      -- Additional categorization
    subcategory VARCHAR(100),                   -- Additional subcategorization
    source VARCHAR(50) NOT NULL,                -- 'irs' or 'everyorg'
    last_updated TIMESTAMP DEFAULT NOW()        -- Last update timestamp
);

-- Indexes
CREATE INDEX idx_cause_ntee_type ON cause_ntee(cause_type);
CREATE INDEX idx_cause_ntee_parent ON cause_ntee(parent_code);
CREATE INDEX idx_cause_ntee_name_search ON cause_ntee USING GIN (to_tsvector('english', name));
CREATE INDEX idx_cause_ntee_description_search ON cause_ntee USING GIN (to_tsvector('english', description));
```

## Related Tables

NTEE codes are used to classify organizations in:

- **`organization_nonprofit`** - Main nonprofit search table
  - Column: `ntee_code` (references `cause_ntee.code` WHERE `cause_type = 'ntee'`)
  - Column: `ntee_major_group` (first letter of NTEE code)

- **`cause_ntee`** - Combined reference table
  - Contains both NTEE codes (`cause_type = 'ntee'`) and EveryOrg causes (`cause_type = 'everyorg'`)
  - Use `WHERE cause_type = 'ntee'` to get only NTEE codes

## Common NTEE Major Groups

| Code | Category | Description |
|------|----------|-------------|
| A | Arts | Arts, Culture, and Humanities |
| B | Education | Educational Institutions and Related Activities |
| C | Environment | Environmental Quality, Protection, and Beautification |
| D | Animals | Animal-Related |
| E | Health | Health - General and Rehabilitative |
| F | Mental Health | Mental Health, Crisis Intervention |
| G | Diseases | Diseases, Disorders, Medical Disciplines |
| H | Medical Research | Medical Research |
| I | Crime | Crime, Legal Related |
| J | Employment | Employment, Job Related |
| K | Food | Food, Agriculture, and Nutrition |
| L | Housing | Housing, Shelter |
| M | Public Safety | Public Safety, Disaster Preparedness |
| N | Recreation | Recreation, Sports, Leisure, Athletics |
| O | Youth Development | Youth Development |
| P | Human Services | Human Services - Multipurpose |
| Q | International | International, Foreign Affairs |
| R | Civil Rights | Civil Rights, Social Action, Advocacy |
| S | Community | Community Improvement, Capacity Building |
| T | Philanthropy | Philanthropy, Voluntarism, Grantmaking |
| U | Science | Science and Technology Research |
| V | Social Science | Social Science Research Institutes |
| W | Public Affairs | Public, Society Benefit - Multipurpose |
| X | Religion | Religion Related, Spiritual Development |
| Y | Mutual Membership | Mutual/Membership Benefit Organizations |
| Z | Unknown | Unknown, Unclassified |

## Data Pipeline

```
IRS Publication 557 + NCCS
         ↓
data/gold/causes_ntee_codes (196 codes)
         ↓
scripts/datasources/ntee/load_to_postgres.py
         ↓
cause_ntee table (PostgreSQL, cause_type='ntee')
         ↓
Used by organization_nonprofit table
```

## References

- [IRS Publication 557](https://www.irs.gov/pub/irs-pdf/p557.pdf) - Tax-Exempt Status for Your Organization
- [NCCS NTEE Documentation](https://nccs.urban.org/project/national-taxonomy-exempt-entities-ntee-codes)
- [Wikipedia: NTEE](https://en.wikipedia.org/wiki/National_Taxonomy_of_Exempt_Entities)

## Maintenance

### Updating NTEE Codes

NTEE taxonomy is relatively stable but may be updated annually:

1. Check NCCS website for new taxonomy versions
2. Update parquet file if changes detected
3. Reload data: `python scripts/datasources/ntee/load_to_postgres.py`

### Troubleshooting

**File not found error:**
```
❌ NTEE codes file not found: data/gold/causes_ntee_codes
```

Solution: The parquet file should already exist in your data/gold directory. If missing, it may have been excluded from git or needs to be regenerated.

**Connection error:**
```
❌ Load failed: could not connect to server
```

Solution: Check that PostgreSQL is running and credentials are correct in your `.env` file.
