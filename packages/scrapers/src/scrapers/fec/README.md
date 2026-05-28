# FEC Campaign Finance Scripts

Scripts for working with [Federal Election Commission](https://www.fec.gov/) campaign finance data.

## Local cache (this repo)

Bulk ZIPs and extracted files live under:

```text
data/cache/fec_data/
├── bulk-downloads/     # ZIPs from fec.gov (source)
├── unzipped/           # extracted CSV/TXT (after unzip_fec_data.py)
├── download_log.json
└── unzip_log.json
```

Override the base path with env `FEC_DATA_DIR` or `--base-dir`.

**Download (resume-safe):**

```bash
./scripts/datasources/fec/run_bulk_download.sh
# or
.venv/bin/python scripts/datasources/fec/python -m ingestion.fec.bulk --resume
```

## Data Source

- **Website**: https://www.fec.gov/
- **API**: https://api.open.fec.gov/developers/
- **Bulk Data**: https://www.fec.gov/data/browse-data/?tab=bulk-data
- **Coverage**: Federal candidates, committees, contributions
- **Data Types**: Candidates, committees, contributions, expenditures, filings

## Scripts

### `python -m ingestion.fec.bulk`
Download all FEC bulk data files and organize them by year and type.

**Features:**
- Downloads all bulk data from 1980-present
- Organizes files matching FEC website structure
- Resume interrupted downloads
- Progress tracking and logging
- Filter by year or file type

**Usage:**
```bash
# Download everything to data/cache/fec_data/
./scripts/datasources/fec/run_bulk_download.sh

# Download specific years / types
.venv/bin/python scripts/datasources/fec/python -m ingestion.fec.bulk --resume --years 2022,2024 --types indiv,cn,cm

# Dry run (show what would be downloaded)
.venv/bin/python scripts/datasources/fec/python -m ingestion.fec.bulk --dry-run
```

**File Types:**
- `cm` - Committee Master files
- `cn` - Candidate Master files
- `ccl` - Candidate-Committee Linkages
- `indiv` - Individual Contributions
- `pas2` - PAC Summary files
- `oth` - Other Transactions
- `oppexp` - Operating Expenditures
- `weball` - All Candidates
- `webk` / `webl` - Current House/Senate Campaigns

**Output Structure:**
```
data/cache/fec_data/
└── bulk-downloads/
    ├── candidate-master/          (Candidate master files)
    │   ├── 1980/cn80.zip
    │   ├── 2024/cn24.zip
    │   └── ...
    ├── all-candidates/            (All candidates files)
    │   ├── 1980/weball80.zip
    │   └── 2024/weball24.zip
    ├── house-senate-campaigns/    (Current campaigns)
    │   └── 2024/
    │       ├── webk24.zip
    │       └── webl24.zip
    ├── committee-master/          (Committee master files)
    │   └── 2024/cm24.zip
    ├── pac-summary/               (PAC summary files)
    │   └── 2024/pas224.zip
    ├── contributions-by-individuals/ (Individual contributions)
    │   └── 2024/indiv24.zip
    ├── candidate-committee-linkages/ (Linkages)
    │   └── 2024/ccl24.zip
    ├── committee-to-committee/    (Committee transactions)
    │   └── 2024/oth24.zip
    ├── operating-expenditures/    (Operating expenses)
    │   └── 2024/oppexp24.zip
    ├── summary-reports/           (Summary CSVs)
    │   └── 2024/
    │       ├── candidate_summary_2024.csv
    │       ├── independent_expenditure_2024.csv
    │       └── ...
    ├── headers/                   (Data dictionaries)
    │   ├── cm_header_file.csv
    │   └── ...
    └── special-files/             (Lobbyist data, etc.)
        ├── lobbyist.csv
        └── ...
```

### `unzip_fec_data.py` (High-Performance Edition)
Unzip all FEC bulk data files with parallel processing and 7-Zip support for maximum speed.

**Performance Modes:**
- **Parallel Processing**: 4-8x faster with `--workers 8`
- **7-Zip Extraction**: 2-3x faster than Python zipfile
- **Combined**: 10-15x faster with `--method 7z --workers 8`

**Features:**
- Multiple extraction methods (Python zipfile, 7-Zip, auto-detect)
- Parallel processing with configurable worker count
- Maintains same folder hierarchy as source
- Resume support (skip already unzipped files)
- Progress tracking and logging
- Optional: Remove ZIP files after extraction
- Filter by category or year

**Usage:**
```bash
# RECOMMENDED: Unzip latest 2 years only with 8 workers (FAST & QUICK)
python unzip_fec_data.py --latest 2 --workers 8 
# FASTEST: Use 7-Zip with 8 parallel workers (10-15x faster, all years)
python unzip_fec_data.py --method 7z --workers 8 
# Fast: Use parallel workers only (4-8x faster)
python unzip_fec_data.py --workers 8 
# Moderate: Use 7-Zip single-threaded (2-3x faster)
python unzip_fec_data.py --method 7z 
# Default: Python zipfile single-threaded (portable but slow)
python unzip_fec_data.py 
# Auto-detect best method and optimal workers
python unzip_fec_data.py --method auto --workers 0 
# Unzip specific category with parallel workers
python unzip_fec_data.py --category candidate-master --workers 4

# Unzip specific years with parallel workers
python unzip_fec_data.py --years 2020,2022,2024 --workers 4
    
# Unzip latest 5 years only (auto-detects 2020-2024)
python unzip_fec_data.py --latest 5 --workers 8

# Resume interrupted extraction
python unzip_fec_data.py --resume --workers 8

# Dry run (show what would be unzipped)
python unzip_fec_data.py --dry-run

# Remove ZIP files after successful extraction (saves 50% disk space)
python unzip_fec_data.py --remove-zips --workers 8
```

**Installation for 7-Zip (optional but recommended):**
```bash
# Ubuntu/Debian
sudo apt-get install p7zip-full

# macOS
brew install p7zip

# Verify installation
7z --help
```

**Output Structure:**
```
data/cache/fec_data/
├── bulk-downloads/          # Original ZIP files (source)
│   ├── candidate-master/
│   │   ├── 1980/cn80.zip
│   │   └── 2024/cn24.zip
│   └── ...
└── unzipped/                # Unzipped CSV/TXT files (destination)
    ├── candidate-master/
    │   ├── 1980/
    │   │   ├── cn80/
    │   │   │   ├── cn.txt
    │   │   │   ├── cn_header_file.csv
    │   │   │   └── ...
    │   └── 2024/
    │       └── cn24/
    │           ├── cn.txt
    │           └── ...
    ├── contributions-by-individuals/
    │   └── 2024/
    │       └── indiv24/
    │           ├── indiv.txt
    │           ├── indiv_header_file.csv
    │           └── ...
    └── ...
```

**Workflow:**
1. Download FEC bulk data: `./scripts/datasources/fec/run_bulk_download.sh`
2. **QUICK START** - Unzip latest 2 years: `python scripts/datasources/fec/unzip_fec_data.py --latest 2 --workers 8 --resume`
   - OR **FULL** - Unzip all (FAST): `python scripts/datasources/fec/unzip_fec_data.py --method 7z --workers 8 --resume`
3. (Optional) Remove ZIPs to save space: Add `--remove-zips` flag to step 2

**Performance Comparison:**

| Method | Workers | Speed | Time (100 files) |
|--------|---------|-------|------------------|
| Python zipfile | 1 | 1x | ~100 min |
| Python zipfile | 8 | 4-6x | ~15-20 min |
| 7-Zip | 1 | 2-3x | ~30-40 min |
| 7-Zip | 8 | 10-15x | ~7-10 min ⚡ |

**Recommended Settings:**
- **Maximum speed**: `--method 7z --workers 8` (requires 7z installed)
- **Good balance**: `--workers 4` (no additional software needed)
- **Portable**: Default (works everywhere, no setup)

### `fec_integration.py`
Integrate FEC API data for real-time queries.

## Key Datasets

### Candidates
- Federal candidates (President, Senate, House)
- Party affiliation
- Election years

### Committees
- Campaign committees
- PACs, Super PACs
- Party committees

### Financial Data
- Individual contributions
- Committee expenditures
- Independent expenditures
- Disbursements

## Usage Examples

```bash
# Download candidate data
python fec_integration.py --data-type candidates --state MA

# Download committee data
python fec_integration.py --data-type committees --cycle 2024
```

## API Key

Requires FEC API key. Set environment variable:
```bash
export FEC_API_KEY=your_key_here
```

Register at: https://api.data.gov/signup/

## Data License

FEC data is public domain.
