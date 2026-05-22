#!/usr/bin/env python3
"""
Finalize HuggingFace dataset structure by organizing all files.

Structure:
- data/gold/national/ - Full national datasets (consolidated)
- data/gold/states/ - State-by-state datasets
- data/gold/reference/ - Lookup tables and reference data
"""

import shutil
from pathlib import Path

from loguru import logger


def organize_files():
    """Organize files into logical directories."""
    logger.info("=" * 70)
    logger.info("🗂️  Finalizing HuggingFace dataset structure")
    logger.info("=" * 70)
    
    gold_dir = Path("data/gold")
    
    # 1. Move consolidated nonprofit files to national/
    logger.info("\n📦 Moving consolidated datasets to national/")
    national_dir = gold_dir / "national"
    national_dir.mkdir(exist_ok=True)
    
    national_files = [
        "nonprofits_organizations.parquet",
        "nonprofits_locations.parquet",
        "nonprofits_financials.parquet",
        "nonprofits_programs.parquet",
    ]
    
    for filename in national_files:
        src = gold_dir / filename
        if src.exists():
            dst = national_dir / filename
            shutil.move(str(src), str(dst))
            size = dst.stat().st_size / 1024 / 1024
            logger.info(f"   ✅ {filename} → national/ ({size:.1f} MB)")
    
    # 2. Move reference/lookup tables to reference/
    logger.info("\n📚 Moving reference data to reference/")
    reference_dir = gold_dir / "reference"
    reference_dir.mkdir(exist_ok=True)
    
    reference_files = [
        "causes_everyorg_causes.parquet",
        "causes_ntee_codes",
        "domains_gsa_domains.parquet",
        "jurisdictions_cities.parquet",
        "jurisdictions_counties.parquet",
        "jurisdictions_school_districts.parquet",
        "jurisdictions_townships.parquet",
    ]
    
    for filename in reference_files:
        src = gold_dir / filename
        if src.exists():
            dst = reference_dir / filename
            shutil.move(str(src), str(dst))
            size = dst.stat().st_size / 1024 / 1024
            logger.info(f"   ✅ {filename} → reference/ ({size:.2f} MB)")
    
    # 3. Create README for national directory
    logger.info("\n📝 Creating documentation")
    
    national_readme = national_dir / "README.md"
    national_readme.write_text("""# National Nonprofit Datasets

These files contain **all U.S. nonprofit organizations** in single consolidated files.

## Files

- **nonprofits_organizations.parquet** (~134 MB) - 3.9M nonprofits with core data
- **nonprofits_locations.parquet** (~86 MB) - 1.9M location records
- **nonprofits_financials.parquet** (~77 MB) - Financial data from Form 990
- **nonprofits_programs.parquet** (~65 MB) - Programs and services

## When to Use

✅ **Use this** if you need:
- Complete national analysis
- All states in one dataset
- Maximum convenience (single file per dataset)

❌ **Use states/ instead** if you need:
- Only specific states
- Smaller downloads
- State-by-state analysis

## Example

```python
import pandas as pd

# Load all 3.9M nonprofits
df = pd.read_parquet('national/nonprofits_organizations.parquet')
print(f"Total nonprofits: {len(df):,}")

# Filter to your state of interest
ca_orgs = df[df['state'] == 'CA']
print(f"California nonprofits: {len(ca_orgs):,}")
```

## Comparison

| Approach | File Size | Use Case |
|----------|-----------|----------|
| `national/nonprofits_organizations.parquet` | 134 MB | All 3.9M nonprofits |
| `states/CA/nonprofits_organizations.parquet` | 15 MB | Just California (~400K) |
| `states/*/nonprofits_organizations.parquet` | 347 MB total | All states (organized) |

**Note:** The `states/` directory contains the same data split by state for easier discovery and partial downloads.
""")
    logger.success(f"   ✅ Created {national_readme.name}")
    
    reference_readme = reference_dir / "README.md"
    reference_readme.write_text("""# Reference Data

Lookup tables and reference datasets for nonprofit analysis.

## Files

### Cause Codes
- **causes_ntee_codes** - National Taxonomy of Exempt Entities (NTEE) codes
- **causes_everyorg_causes.parquet** - Every.org cause categories

### Jurisdictions
- **jurisdictions_cities.parquet** - 19,495 incorporated cities
- **jurisdictions_counties.parquet** - 3,234 counties
- **jurisdictions_school_districts.parquet** - 13,362 school districts
- **jurisdictions_townships.parquet** - 16,360 townships

### Domains
- **domains_gsa_domains.parquet** - U.S. government domains from GSA

## Usage

These are small lookup tables (< 3 MB each) used to enrich nonprofit data.

```python
import pandas as pd

# Load NTEE codes
ntee = pd.read_parquet('reference/causes_ntee_codes.parquet')
print(ntee.head())

# Load cities
cities = pd.read_parquet('reference/jurisdictions_cities.parquet')
print(f"Total cities: {len(cities):,}")
```
""")
    logger.success(f"   ✅ Created {reference_readme.name}")
    
    # 4. Update main states README
    states_readme = gold_dir / "states" / "README.md"
    if states_readme.exists():
        content = states_readme.read_text()
        
        # Add note about national datasets
        if "national/" not in content:
            addition = """
## 🌎 National Datasets

Looking for **all states in one file**? See the [`national/`](../national/) directory for consolidated datasets containing all 3.9M nonprofits.

"""
            # Insert after the first header
            lines = content.split('\n')
            lines.insert(2, addition)
            states_readme.write_text('\n'.join(lines))
            logger.success(f"   ✅ Updated states/README.md")
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.success("✅ COMPLETE: HuggingFace dataset structure finalized")
    logger.info("=" * 70)
    logger.info("\n📁 Final structure:")
    logger.info("   data/gold/")
    logger.info("   ├── national/           # Full national datasets (362 MB)")
    logger.info("   │   ├── nonprofits_organizations.parquet")
    logger.info("   │   ├── nonprofits_locations.parquet")
    logger.info("   │   ├── nonprofits_financials.parquet")
    logger.info("   │   ├── nonprofits_programs.parquet")
    logger.info("   │   └── README.md")
    logger.info("   ├── states/             # State-by-state datasets (347 MB)")
    logger.info("   │   ├── AL/")
    logger.info("   │   ├── CA/")
    logger.info("   │   ├── ... (62 states)")
    logger.info("   │   └── README.md")
    logger.info("   └── reference/          # Lookup tables (6 MB)")
    logger.info("       ├── causes_ntee_codes")
    logger.info("       ├── jurisdictions_cities.parquet")
    logger.info("       ├── ... (7 files)")
    logger.info("       └── README.md")
    logger.info("\n💡 Users can choose:")
    logger.info("   - national/ → Complete datasets (best for national analysis)")
    logger.info("   - states/ → State-specific data (best for regional analysis)")
    logger.info("   - reference/ → Lookup tables (NTEE codes, jurisdictions, etc.)")


if __name__ == "__main__":
    organize_files()
