---
sidebar_position: 5
---

# State-Split Data Files (Deprecated)

:::warning Deprecated
This approach of splitting files into separate state files is **deprecated**. 

Use **[Partitioned Datasets](./partitioned-datasets.md)** instead for:
- Same efficiency as separate files
- Ability to query across states
- Better analytics tool support
- Simpler data management
:::

All gold parquet files with state information were previously split into state-specific files. This has been replaced by partitioned datasets which offer the same benefits with better queryability.

## What Changed

Instead of downloading one massive file with all states:
- ❌ `nonprofits_organizations.parquet` (72 MB, 1.9M records)

You can now download just the state(s) you need:
- ✅ `nonprofits_organizations_AL.parquet` (Alabama only, ~1 MB)
- ✅ `nonprofits_organizations_CA.parquet` (California only, ~8 MB)
- ✅ `nonprofits_organizations_TX.parquet` (Texas only, ~6 MB)

## Benefits

1. **Smaller Downloads**: Only download the data you need
2. **Faster Queries**: Load and analyze state-specific data faster
3. **Better Organization**: Easier to manage and share state-level datasets
4. **HuggingFace Friendly**: Avoids file size limits, enables state-specific repos

## File Structure

State-split files are located in `data/gold/by_state/`:

```
data/gold/by_state/
├── nonprofits_organizations_AL.parquet
├── nonprofits_organizations_AK.parquet
├── nonprofits_locations_AL.parquet
├── jurisdictions_cities_AL.parquet
├── jurisdictions_counties_AL.parquet
├── jurisdictions_school_districts_AL.parquet
└── ... (388 total files)
```

## Files That Were Split

### Nonprofit Data (62 states/territories each)
- `nonprofits_organizations_*.parquet` - Organization details
- `nonprofits_locations_*.parquet` - Geographic locations

### Jurisdiction Data (52 states each)
- `jurisdictions_cities_*.parquet` - Cities and municipalities
- `jurisdictions_counties_*.parquet` - Counties
- `jurisdictions_school_districts_*.parquet` - School districts
- `jurisdictions_townships_*.parquet` - Townships

### Other Data (56 states each)
- `domains_gsa_domains_*.parquet` - Government domains

## Usage

### Load Alabama Nonprofits
```python
import pandas as pd

# Load only Alabama data
df = pd.read_parquet('data/gold/by_state/nonprofits_organizations_AL.parquet')
print(f"Alabama nonprofits: {len(df):,}")
```

### Load Multiple States
```python
import pandas as pd
from pathlib import Path

# Load all southeastern states
states = ['AL', 'GA', 'FL', 'MS', 'TN', 'SC', 'NC']
dfs = []

for state in states:
    path = f'data/gold/by_state/nonprofits_organizations_{state}.parquet'
    df = pd.read_parquet(path)
    dfs.append(df)

# Combine into one DataFrame
southeast = pd.concat(dfs, ignore_index=True)
print(f"Southeast nonprofits: {len(southeast):,}")
```

### Recreate Full Dataset
```python
import pandas as pd
from pathlib import Path

# Load all nonprofit organization files
files = Path('data/gold/by_state').glob('nonprofits_organizations_*.parquet')
dfs = [pd.read_parquet(f) for f in files]

# Combine
full_dataset = pd.concat(dfs, ignore_index=True)
print(f"All nonprofits: {len(full_dataset):,}")
```

## Managing State Splits

### Create/Update State Splits
```bash
# Split all files by state
python scripts/split_gold_by_state.py --all

# Split specific file
python scripts/split_gold_by_state.py --file nonprofits_organizations.parquet

# Dry run (see what would happen)
python scripts/split_gold_by_state.py --all --dry-run

# View statistics
python scripts/split_gold_by_state.py --stats
```

### Upload to HuggingFace

Upload state-specific datasets to HuggingFace for public access:

```bash
# Upload all states
python scripts/upload_state_splits_to_hf.py --all

# Upload Alabama only
python scripts/upload_state_splits_to_hf.py --state AL

# Upload multiple states
python scripts/upload_state_splits_to_hf.py --states AL AK AZ CA

# Dry run
python scripts/upload_state_splits_to_hf.py --all --dry-run
```

This creates state-specific repos on HuggingFace:
- `CommunityOne/one-data-AL` - All Alabama data
- `CommunityOne/one-data-CA` - All California data
- `CommunityOne/one-data-TX` - All Texas data

## Statistics

**Total State-Split Files**: 388 files  
**Total Size**: 172 MB  
**States/Territories**: 62 (all US states, DC, territories, military addresses)

**File Breakdown**:
- 62 nonprofit organization files
- 62 nonprofit location files
- 56 government domain files
- 52 jurisdiction city files
- 52 jurisdiction county files
- 52 jurisdiction school district files
- 52 jurisdiction township files

## Notes

- Original monolithic files are still in `data/gold/` for backward compatibility
- State-split files use standard 2-letter state codes (AL, AK, AZ, etc.)
- Includes US territories: PR, VI, GU, AS, MP
- Includes military addresses: AA, AE, AP
- Some files have fewer states if no data exists for that state
