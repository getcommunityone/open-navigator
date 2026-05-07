# Scripts Directory

All scripts are organized into logical subdirectories by function.

## 📂 Directory Structure

```
scripts/
├── data/                    # Data processing and migration
├── datasources/             # Data source integrations and connectors
├── deployment/              # Deployment and setup
├── development/             # Development and debugging tools
├── discovery/               # Jurisdiction discovery and URL finding
├── enrichment/              # Data enrichment (990s, nonprofits)
├── enrichment_ai/           # AI-powered analysis (Intel Arc optimized)
├── huggingface/             # HuggingFace dataset management
├── localview/               # LocalView YouTube scraper
├── maintenance/             # Cleanup and maintenance
└── mcp/                     # Model Context Protocol server
```

## 📖 Folder Descriptions

### [data/](data/)
Data processing pipelines, migrations, and aggregations.
- Bill aggregations from PostgreSQL
- Gold table creation
- Contact extraction
- Data splits and partitioning

### [datasources/](datasources/)
Data source integrations and API connectors organized by external data source.

**Available Sources:**
- `openstates/` - OpenStates legislative data (bills, legislators, votes) - 8 scripts
  - ✅ **openstates_sources.py** - API integration for jurisdiction discovery
- `census/` - US Census Bureau geographic and demographic data - 3 scripts
- `irs/` - IRS nonprofit data (Form 990, Business Master File) - 5 scripts
  - ✅ **nonprofit_discovery.py** - Discover nonprofits by location/category
- `youtube/` - YouTube Data API integration - 1 script
  - ✅ **youtube_channel_discovery.py** - Discover municipal YouTube channels
- `social_media/` - Social media discovery (Facebook, Twitter, Instagram) - 1 script
  - ✅ **social_media_discovery.py** - Find social media accounts
- `fec/` - Federal Election Commission campaign finance data - 2 scripts
- `localview/` - LocalView meeting transcripts - 2 scripts
  - ✅ **dataverse_client.py** - Harvard Dataverse API client
- `google_data_commons/` - Google Data Commons demographic data - 1 script
- `gsa/` - GSA .gov domain registry - 1 script
- `ballotpedia/` - Ballotpedia election and official data - 1 script
- `google_civic/` - Google Civic Information API - 1 script
- `grants_gov/` - Grants.gov federal grant data - 1 script
- `meetingbank/` - MeetingBank research dataset - 1 script
- `nces/` - National Center for Education Statistics - 1 script
- `wikidata/` - Wikidata structured knowledge - 1 script
- `dbpedia/` - DBpedia structured Wikipedia data - 1 script
- `voter_data/` - Voter registration and turnout data - 1 script

See [datasources/README.md](datasources/README.md) for detailed documentation.

### [deployment/](deployment/)
Setup scripts for local development and production deployment.
- Local environment setup
- Database initialization
- Databricks deployment

### [development/](development/)
Development and debugging tools.
- Debug scripts for scrapers
- Testing utilities
- Development helpers

### [discovery/](discovery/)
Comprehensive jurisdiction discovery and data source identification.
- **Automated discovery** for all 90,000+ U.S. jurisdictions
- Official website URL finding
- YouTube channel discovery (with API integration)
- Meeting platform detection (Legistar, Granicus, SuiteOne)
- Social media account discovery
- Agenda portal identification
- Batch processing with quality metrics

**Key Scripts:**
- `comprehensive_discovery_pipeline.py` - Master discovery for all jurisdictions
- `youtube_channel_discovery.py` - Find municipal YouTube channels
- `platform_detector.py` - Detect meeting platforms
- `social_media_discovery.py` - Find social media accounts
- `batch_processor.py` - Process thousands of jurisdictions

See [discovery/README_NONPROFIT_DISCOVERY.md](discovery/README_NONPROFIT_DISCOVERY.md) for details.

### [enrichment/](enrichment/)
Scripts to enrich nonprofit data with additional metadata.
- 990 form downloads and processing
- Nonprofit profile enrichment
- Multiple data source integrations

### [enrichment_ai/](enrichment_ai/)
AI-powered legislative analysis using Intel Arc Graphics optimization.
- DuckDB + Vector Similarity Search
- Llama model inference (local)
- Intel IPEX and OpenVINO acceleration
- Bill and testimony analysis

See [enrichment_ai/README.md](enrichment_ai/README.md) for setup instructions.

### [huggingface/](huggingface/)
HuggingFace dataset preparation and upload.
- Dataset restructuring
- Multi-dataset uploads
- Finalization scripts

### [maintenance/](maintenance/)
System maintenance and cleanup utilities.
- Disk space cleanup
- File management
- Development utilities

## 🟫 Bronze Ingestion (`load_bronze.py`)

Runs all bronze-layer data loaders in sequence, then triggers dbt bronze models. Logs are written to `logs/load_bronze/<run_id>/`.

**Loaders (run in order):**
| Key | Source | Target Table(s) |
|---|---|---|
| `census` | Census Gazetteer | `bronze.bronze_jurisdictions_*` |
| `gsa` | GSA .gov Domains | `bronze.bronze_gov_domains` |
| `localview` | LocalView Meetings | `bronze.bronze_events_localview` |
| `irs` | IRS BMF Nonprofits | `bronze.bronze_organizations_nonprofits_irs` |

### Common usage

```bash
# Run all loaders + dbt bronze
python scripts/load_bronze.py

# Skip the dbt run at the end
python scripts/load_bronze.py --no-dbt

# Run only specific loaders
python scripts/load_bronze.py --only gsa census

# Skip specific loaders
python scripts/load_bronze.py --skip localview irs

# Clear supported tables before loading
python scripts/load_bronze.py --truncate

# Dry run — parse only, no DB writes (loaders that support it)
python scripts/load_bronze.py --dry-run
```

### Retrying failed steps

Each run saves a `results.json` in its log directory. Use `--retry-failed` to re-run only the steps that failed in the most recent run, or `--retry-run` to target a specific run by ID.

```bash
# Retry only failed steps from the most recent run
python scripts/load_bronze.py --retry-failed

# Retry only failed steps from a specific run
python scripts/load_bronze.py --retry-run 20260507_082303
```

To find recent run IDs:

```bash
ls logs/load_bronze/
```

The run ID is printed at the start of every run and in the summary. If the most recent run had no failures, `--retry-failed` exits immediately with a success message.

---

## 🔍 Finding Scripts

Use these commands to find scripts:

```bash
# List all scripts in a category
ls scripts/data/

# Search for a specific script
find scripts/ -name "*aggregate*"

# See what a script does
head -20 scripts/data/aggregate_bills_from_postgres.py
```

## ⚠️ Important Note

All scripts should be run from the project root directory:

```bash
# ✅ Correct
cd /home/developer/projects/open-navigator
python scripts/data/aggregate_bills_from_postgres.py

# ❌ Wrong
cd scripts/data
python aggregate_bills_from_postgres.py
```
