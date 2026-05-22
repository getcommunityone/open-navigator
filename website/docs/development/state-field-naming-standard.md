---
sidebar_position: 5
---

# State Field Naming Standard

## Overview

This document defines the **mandatory naming convention** for state-related fields across all Open Navigator databases, parquet files, and code.

## Standard

### Required Field Names

| Field Name | Data Type | Purpose | Example Values |
|------------|-----------|---------|----------------|
| `state_code` | VARCHAR(2) or string | Two-letter state abbreviation | `'AL'`, `'MA'`, `'WI'` |
| `state` | VARCHAR(50) or string | Full state name | `'Alabama'`, `'Massachusetts'`, `'Wisconsin'` |

### Rules

✅ **DO THIS:**
- Use `state_code` for all 2-letter state abbreviations
- Use `state` for all full state names
- Include BOTH fields when storing state information
- Use uppercase for `state_code` values

❌ **DON'T DO THIS:**
- ❌ Use `state` for 2-letter codes (legacy pattern - being phased out)
- ❌ Use `state_abbr`, `state_abbreviation`, or `st_abbr`
- ❌ Use `state_name` (use `state` instead)
- ❌ Store state codes in lowercase

## Code Examples

### Python/Pandas

```python
# ✅ CORRECT
df = pd.DataFrame({
    'jurisdiction_name': ['Mobile', 'Boston'],
    'state_code': ['AL', 'MA'],
    'state': ['Alabama', 'Massachusetts']
})

# Save to parquet
df.to_parquet('jurisdictions.parquet')

# ❌ WRONG
df_wrong = pd.DataFrame({
    'jurisdiction_name': ['Mobile'],
    'state': ['AL'],  # Don't use 'state' for 2-letter codes
    'state_name': ['Alabama']  # Don't use 'state_name'
})
```

### SQL Schema

```sql
-- ✅ CORRECT
CREATE TABLE jurisdiction (
    id SERIAL PRIMARY KEY,
    jurisdiction_name VARCHAR(200) NOT NULL,
    state_code VARCHAR(2) NOT NULL,
    state VARCHAR(50) NOT NULL,
    CONSTRAINT check_state_code_length CHECK (LENGTH(state_code) = 2),
    CONSTRAINT check_state_code_uppercase CHECK (state_code = UPPER(state_code))
);

-- ❌ WRONG
CREATE TABLE jurisdictions_legacy (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    state VARCHAR(2),  -- Ambiguous: is this a code or full name?
    state_abbr VARCHAR(2)  -- Don't use state_abbr
);
```

### API Queries

```python
# ✅ CORRECT - FastAPI
@app.get("/api/jurisdictions")
async def get_jurisdictions(
    state_code: Optional[str] = Query(None, regex="^[A-Z]{2}$", description="Two-letter state code"),
    state: Optional[str] = Query(None, description="Full state name")
):
    query = "SELECT * FROM jurisdiction WHERE 1=1"
    params = []
    
    if state_code:
        query += f" AND state_code = ${len(params)+1}"
        params.append(state_code)
    
    if state:
        query += f" AND state = ${len(params)+1}"
        params.append(state)
    
    # ... execute query

# ❌ WRONG
async def get_jurisdictions_wrong(state: str):  # Ambiguous parameter name
    query = f"SELECT * FROM jurisdictions WHERE state = '{state}'"  # SQL injection risk + ambiguous
```

## Migration Guide

### Current State (as of 2026-05)

Many existing tables and parquet files use the **legacy convention**:
- `state` = 2-letter code (e.g., 'AL', 'MA')
- `state_name` = full name (if exists) OR missing entirely

### Migration Steps

**For Database Tables:**

1. Add new `state_code` column:
   ```sql
   ALTER TABLE jurisdiction ADD COLUMN state_code VARCHAR(2);
   UPDATE jurisdiction SET state_code = state;
   ALTER TABLE jurisdiction ALTER COLUMN state_code SET NOT NULL;
   ```

2. Add/rename state name column:
   ```sql
   -- If state_name exists:
   ALTER TABLE jurisdiction RENAME COLUMN state_name TO state_temp;
   ALTER TABLE jurisdiction ADD COLUMN state VARCHAR(50);
   UPDATE jurisdiction SET state = state_temp;
   ALTER TABLE jurisdiction DROP COLUMN state_temp;
   
   -- If state_name doesn't exist:
   ALTER TABLE jurisdiction ADD COLUMN state VARCHAR(50);
   UPDATE jurisdiction SET state = (
       CASE state_code
           WHEN 'AL' THEN 'Alabama'
           WHEN 'AK' THEN 'Alaska'
           -- ... etc
       END
   );
   ```

3. Drop old `state` column and rename:
   ```sql
   ALTER TABLE jurisdiction DROP COLUMN state_old;
   ```

**For Parquet Files:**

```python
import pandas as pd
from pathlib import Path

def migrate_parquet(file_path: Path):
    """Migrate parquet file to new naming convention."""
    df = pd.read_parquet(file_path)
    
    # If using legacy convention
    if 'state' in df.columns and df['state'].str.len().max() == 2:
        # Rename state → state_code
        df.rename(columns={'state': 'state_code'}, inplace=True)
        
        # Add full state name
        state_map = {
            'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona',
            # ... full mapping
        }
        df['state'] = df['state_code'].map(state_map)
    
    # If state_name exists, rename to state
    if 'state_name' in df.columns:
        df.rename(columns={'state_name': 'state'}, inplace=True)
    
    # Save back
    df.to_parquet(file_path)
```

### Tables Requiring Migration

Based on current schema audit (2026-05-03):

| Table Name | Current | Needs Migration |
|------------|---------|----------------|
| `jurisdiction` | `state` (2-char) | ✅ Yes |
| `contact` | `state` (2-char) | ✅ Yes |
| `event` | `state` (2-char) | ✅ Yes |
| `organization_nonprofit` | `state` (2-char) | ✅ Yes |
| `bills_search` | `state` (2-char) | ✅ Yes |
| `bill_map_aggregate` | `state_code` (2-char) | ✅ Needs `state` added |
| `zip_county_mapping` | `state_abbr` (2-char) | ✅ Rename to `state_code` |
| `jurisdictions_details_search` | `state` (2-char) | ✅ Yes |

### Parquet Files Requiring Migration

```
data/gold/states/{STATE}/
├── contact_official.parquet         (✅ needs migration)
├── contacts_local_officials.parquet   (✅ needs migration)
├── events.parquet                     (✅ needs migration)
├── jurisdictions_details.parquet      (✅ needs migration)
└── nonprofits_organizations.parquet   (✅ needs migration)
```

## State Code → Full Name Mapping

### Complete U.S. State Mapping

```python
STATE_CODE_TO_NAME = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
    'PR': 'Puerto Rico', 'VI': 'U.S. Virgin Islands', 'GU': 'Guam',
    'AS': 'American Samoa', 'MP': 'Northern Mariana Islands'
}

STATE_NAME_TO_CODE = {v: k for k, v in STATE_CODE_TO_NAME.items()}
```

## Rationale

### Why This Standard?

1. **Clarity**: `state_code` and `state` are unambiguous
2. **Consistency**: Aligns with industry standards (LocalView dataset uses `state_name`)
3. **Prevents Errors**: No confusion about whether `state` contains 'AL' or 'Alabama'
4. **Better UX**: API consumers get both formats without needing conversion
5. **Query Optimization**: Can filter by either format efficiently

### Comparison with Other Standards

| Standard | 2-Letter Code | Full Name | Notes |
|----------|---------------|-----------|-------|
| **Open Navigator** | `state_code` | `state` | ✅ Recommended |
| LocalView (Harvard) | (none) | `state_name` | Good, but incomplete |
| Legacy databases | `state` or `state_abbr` | `state_name` | ❌ Ambiguous |
| Census Bureau | `STUSAB` | `NAME` | Federal standard |

## Enforcement

### Pre-commit Checks

Add to `.github/workflows/ci-build-test.yml`:

```yaml
- name: Check State Field Naming
  run: |
    python scripts/validation/check_state_naming.py
```

### Linting Rules

For new code:
- Reject PRs with `state VARCHAR(2)` in SQL
- Reject PRs with `state_name` or `state_abbr` fields
- Require both `state_code` and `state` when state info is included

## See Also

- [Database Schema Documentation](../data-sources/database-schema.md)
- [Migration Scripts](../../scripts/migrations/)
- [Data Pipeline Standards](./data-pipeline-standards.md)
