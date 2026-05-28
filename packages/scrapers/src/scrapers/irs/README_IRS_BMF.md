# IRS EO-BMF Ingestion Module

Download and process **all 1.9M+ U.S. nonprofits** from the IRS Exempt Organizations Business Master File.

## Quick Start

```python
from discovery.irs_bmf_ingestion import IRSBMFIngestion

# Initialize
irs = IRSBMFIngestion()

# Download ALL U.S. nonprofits (1.9M+)
df = irs.download_all_regions()
# Result: 1,952,238 organizations in ~30 seconds

# Or download specific state
df_alabama = irs.download_state_file("AL")
# Result: 26,148 Alabama nonprofits

# Filter by NTEE code
health_orgs = irs.filter_by_ntee(df, ["E"])
# Result: ~80,000 health organizations

# Convert to ProPublica-compatible format
standardized = irs.standardize_to_propublica_format(df)
```

## Command Line Usage

```bash
# Download ALL nonprofits
python scripts/create_all_gold_tables.py \
  --nonprofits-only \
  --use-irs \
  --download-all-irs

# Download specific states
python scripts/create_all_gold_tables.py \
  --nonprofits-only \
  --states AL GA FL \
  --use-irs

# Filter by NTEE codes
python scripts/create_all_gold_tables.py \
  --nonprofits-only \
  --states AL \
  --ntee-codes E P \
  --use-irs
```

## Data Source

- **URL**: https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
- **Format**: CSV (converted to Parquet for caching)
- **Records**: 1,952,238 organizations (April 2026)
- **Update Frequency**: Monthly
- **License**: Public domain

## Features

✅ **Complete coverage** - All 1.9M+ U.S. tax-exempt organizations  
✅ **Fast download** - 4 regional files in ~30 seconds  
✅ **Automatic caching** - Parquet format for instant reloading  
✅ **NTEE filtering** - Filter by nonprofit type  
✅ **State filtering** - Download specific states  
✅ **ProPublica compatibility** - Seamless integration with existing pipeline  

## Comparison: IRS vs ProPublica API

| Metric | ProPublica API | IRS EO-BMF |
|--------|----------------|------------|
| **Alabama nonprofits** | 25 | 26,148 |
| **Total available** | 3M+ (paginated) | 1,952,238 |
| **Results per request** | 25 max | All |
| **Download speed** | Slow (API) | Fast (bulk) |
| **Pagination** | ❌ Not available | ✅ Complete dataset |

**IRS provides 1,000x more data per request!**

## Full Documentation

See [website/docs/data-sources/irs-bulk-data.md](../../website/docs/data-sources/irs-bulk-data.md) for complete documentation.
