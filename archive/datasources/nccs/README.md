# NCCS (National Center for Charitable Statistics) Data Scripts

Scripts for downloading and working with nonprofit data from the National Center for Charitable Statistics at the Urban Institute.

## Data Source

- **Organization**: National Center for Charitable Statistics (NCCS), Urban Institute
- **Website**: https://nccs.urban.org/
- **Catalog**: https://urbaninstitute.github.io/nccs/catalogs/catalog-bmf.html
- **Coverage**: Tax-exempt organizations (1989-present)
- **Data Types**: Unified BMF, Transformed BMF, Raw BMF archives

## Scripts

### `bulk_download_nccs.py`
Download all NCCS BMF (Business Master File) datasets with organized directory structure.

**Features:**
- Downloads Unified BMF (by state or full file)
- Downloads Transformed BMF (monthly cleaned data)
- Downloads Raw BMF archives (unmodified IRS files)
- Resume interrupted downloads
- Progress tracking and logging
- Filter by states or months

**Usage:**
```bash
# Download everything to /mnt/d/nccs_data/
python bulk_download_nccs.py

# Download to custom directory
python bulk_download_nccs.py --base-dir /path/to/directory

# Download only Unified BMF
python bulk_download_nccs.py --dataset unified

# Download specific states only
python bulk_download_nccs.py --dataset unified --states CA,NY,TX,FL

# Download only recent transformed BMF
python bulk_download_nccs.py --dataset transformed --months 2025_12,2026_01

# Skip full unified file (only download state files)
python bulk_download_nccs.py --dataset unified --no-full --states CA,TX

# Resume interrupted download
python bulk_download_nccs.py --resume

# Dry run (show what would be downloaded)
python bulk_download_nccs.py --dry-run
```

**Output Structure:**
```
/mnt/d/nccs_data/
├── unified-bmf/
│   └── v1.2/
│       ├── full/
│       │   └── UNIFIED_BMF_V1.2.csv          (All states combined)
│       ├── by-state/
│       │   ├── AL.csv
│       │   ├── CA.csv
│       │   ├── NY.csv
        │   └── ...                           (56 files: 50 states + DC + 5 territories)
│       └── data-dictionary/
│           └── harmonized_data_dictionary.xlsx
├── transformed-bmf/
│   ├── 2023_06/
│   │   ├── bmf_2023_06_processed.csv
│   │   └── bmf_2023_06_data_dictionary.csv
│   ├── 2025_12/
│   │   ├── bmf_2025_12_processed.csv
│   │   └── bmf_2025_12_data_dictionary.csv
│   └── ...                                   (Monthly from June 2023-Jan 2026)
├── raw-bmf/
│   ├── 2023-06-BMF.csv
│   ├── 2025-12-BMF.csv
│   └── ...                                   (Monthly from June 2023-Jan 2026)
└── download_log.json
```

## Datasets

### Unified BMF (Recommended for Longitudinal Analysis)

**What it is:**
- Consolidates all historical BMF releases into a single file
- One row per organization that has ever held tax-exempt status
- Enables longitudinal analysis without merging multiple annual files

**Key Features:**
- `ORG_YEAR_FIRST` and `ORG_YEAR_LAST` variables tracking organizational lifecycle
- Most recent address geocoded to Census block
- FIPS codes at block, tract, county, and state levels
- Metropolitan area codes using current CBSA definitions
- AI/Lakehouse optimized format

**Coverage:** 1989 through mid-2025 (update pending)

**Use When:**
- You need to track organizations over time
- Building historical sampling frames
- Linking nonprofit data to Census geographies
- Analyzing organizational entry/exit patterns
- Metropolitan vs rural nonprofit analysis

**File Sizes:**
- Full file: ~1.5 GB (all states combined)
- By state: 0.1 MB (territories) to 149.5 MB (California)
- **Note:** 'ZZ' (Unmapped) is not available as a separate file from NCCS

### Transformed BMF (Recommended for Current Analysis)

**What it is:**
- Monthly IRS releases with standardized cleaning and validation
- Consistent column names and quality flags
- Documented transformations

**Key Features:**
- Standardized field names
- Quality flags identifying potential data issues
- Documentation of all transformations applied
- Monthly updates

**Coverage:** June 2023 to present (monthly snapshots)

**Use When:**
- You need current BMF data with consistent formatting
- You want documented quality checks
- Working with monthly snapshots

**File Sizes:** ~50-150 MB per month

### Raw BMF Archives (For Replication Studies)

**What it is:**
- Unmodified monthly BMF files as released by the IRS
- Original IRS schema and variable names

**Coverage:** June 2023 to present (monthly snapshots)

**Use When:**
- Replicating analysis built on raw IRS files
- Need data exactly as IRS published it
- Require specific point-in-time snapshot

**File Sizes:** ~100-200 MB per month

## Key Data Fields

### Geographic Fields (Unified BMF)
- **FIPS Codes**: Block, Tract, County, State
- **CBSA Codes**: Core Based Statistical Area (Metropolitan/Rural)
- **Geocoded Address**: Census block level precision

### Temporal Fields (Unified BMF)
- **ORG_YEAR_FIRST**: When organization first appeared in BMF
- **ORG_YEAR_LAST**: When organization last appeared (or current if still active)

### Organization Fields
- **EIN**: Employer Identification Number (unique ID)
- **NAME**: Organization name
- **NTEE_CODE**: National Taxonomy of Exempt Entities classification
- **SUBSECTION**: IRS subsection (501(c)(3), 501(c)(4), etc.)
- **FINANCIAL_DATA**: Revenue, assets, expenses
- **ADDRESS**: Street, city, state, ZIP

## Census Integration

The Unified BMF is specifically designed for Census data integration:

```python
import pandas as pd

# Load Unified BMF for a state
bmf = pd.read_csv('/mnt/d/nccs_data/unified-bmf/v1.2/by-state/CA.csv')

# Load Census data (example: ACS demographic data)
census = pd.read_csv('census_tract_data.csv')

# Merge on FIPS tract code
merged = bmf.merge(census, left_on='FIPS_TRACT', right_on='GEOID', how='left')

# Now analyze nonprofits by demographic characteristics
analysis = merged.groupby('NTEE_CODE').agg({
    'MEDIAN_INCOME': 'mean',
    'POPULATION': 'sum',
    'EIN': 'count'
})
```

## Related Resources

- **NCCS Data Archive**: https://nccs.urban.org/nccs-data-archive
- **NCCS Census Crosswalk**: For aggregating to additional geographic levels
- **BMF Processing Guide**: https://urbaninstitute.github.io/nccs-data-bmf/
- **Source Code**: https://github.com/UrbanInstitute/nccs-data-bmf
- **IRS Data Dictionary**: https://www.irs.gov/pub/irs-soi/eo-info.pdf

## Attribution

When using NCCS data, please cite:

1. **National Center for Charitable Statistics**, Urban Institute
2. **IRS Business Master File** (original data source)
3. Specify the **data vintage/update date** used

**Example Citation:**
```
National Center for Charitable Statistics (2026). Unified Business Master File (BMF), v1.2.
Retrieved from https://nccs.urban.org/. Original data: IRS Exempt Organizations Business Master File.
```

## Support

- **NCCS Contact**: https://nccs.urban.org/nccs/contact/
- **Documentation Issues**: https://github.com/UrbanInstitute/nccs-data-bmf/issues
