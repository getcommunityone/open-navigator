# OpenStates Data Scripts

Scripts for working with [OpenStates](https://openstates.org/) legislative data.

## Data Source

- **Website**: https://openstates.org/
- **API Docs**: https://docs.openstates.org/api-v3/
- **Bulk Data**: https://openstates.org/data/
- **Coverage**: 52 US states and territories
- **Data Types**: Bills, legislators, votes, committees

## Scripts

### Download & Import
- `bulk_legislative_download.py` - Download OpenStates bulk data dumps (PostgreSQL or CSV)
- `download_documents.py` - Download 4.5M+ bill documents from PostgreSQL database
- `load_openstates_csv.sh` - Load CSV exports into database
- `load_openstates_people.py` - Load legislator data from GitHub repo

### Schema & Export
- `create_openstates_schema.py` - Create PostgreSQL schema for OpenStates data
- `export_openstates_to_gold.py` - Export from PostgreSQL to Gold Parquet files

### Processing
- `aggregate_bills_from_postgres.py` - Aggregate bill statistics by state/topic
- `legislative_tracker.py` - Track legislative activity

## Usage Examples

```bash
# Download April 2026 bulk data to PostgreSQL
python bulk_legislative_download.py --postgres --month 2026-04

# Download bill documents from database (2025 only)
python download_documents.py --years 2025 --type documents

# Download all documents for recent years
python download_documents.py --years 2024,2025 --resume

# Test document download with limit
python download_documents.py --limit 100 --dry-run

# Create database schema
python create_openstates_schema.py

# Load legislator data
python load_openstates_people.py

# Export to Gold format
python export_openstates_to_gold.py

# Aggregate bill statistics
python aggregate_bills_from_postgres.py
```

## Document Downloader Details

The `download_documents.py` script downloads actual bill documents (PDFs, Word docs, etc.) from state legislature websites.

**Database Requirements:**
- PostgreSQL with OpenStates data (from `bulk_legislative_download.py`)
- Default: `postgresql://postgres:password@localhost:5433/openstates`

**Document Types:**
- **Bill Versions** (3.5M): Text of bills as introduced, amended, enrolled, etc.
- **Bill Documents** (1M): Fiscal notes, committee statements, amendments, etc.

**Features:**
- Organizes by year: `/mnt/d/openstates_documents/documents/2025/`
- Snake_case filenames: `hb_1234_fiscal_note_introduced.pdf`
- Resume capability with JSON logging
- Progress updates every 1,000 files
- Rate limiting (0.1s between requests)
- Handles 403/404 errors gracefully

**Output Structure:**
```
/mnt/d/openstates_documents/
├── versions/           # Bill version texts
│   ├── 2017/
│   ├── 2025/
│   └── ...
├── documents/          # Supporting documents
│   ├── 2025/
│   └── ...
└── download_log.json   # Progress tracking
```

**Recommended Usage:**
```bash
# Start with recent year (testing)
python download_documents.py --years 2025 --type documents --limit 1000

# Download all 2024-2025 documents
python download_documents.py --years 2024,2025 --resume

# Full download (WARNING: 4.5M files, ~2TB, takes days!)
python download_documents.py --resume
```

**Important Notes:**
- 4.5 million documents will take several days to download
- Estimated size: ~2TB (average 500KB per document)
- Use `--resume` to continue interrupted downloads
- Progress saved every 100 downloads
- Failed downloads logged separately

## Data License

OpenStates data is available under various open licenses. See https://openstates.org/data/ for details.
