# Discovery Scripts

Scripts for discovering government data sources across U.S. jurisdictions.

For **meeting PDFs**, agendas, and optional contact extraction into `data/cache/scraped_meetings`, use **`comprehensive_discovery_pipeline_jurisdiction.py`** (see its module docstring for `python -m` examples).

## Comprehensive Discovery Pipeline (legacy master discovery)

**Script:** `scripts/discovery/archive/comprehensive_discovery_pipeline.py`

Automates discovery of data sources for all U.S. cities and counties (22,000+ jurisdictions):

- Government websites
- YouTube channels (with statistics)
- Vimeo channels
- Meeting platforms (Legistar, SuiteOne, Granicus, etc.)
- Agenda portals and document systems
- Social media accounts
- Meeting schedules and archives

**Features:**
- **Wikidata Enrichment** - Automatically fills in missing data (websites, social media) from Wikidata for jurisdictions with incomplete discovery
- **Incremental Mode** - Skips already-discovered jurisdictions to save time and API costs
- **LocalView Integration** - Automatically includes known YouTube channels from LocalView database

### Usage

**Run for all jurisdictions (incremental mode):**
```bash
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --all
```

**Run for specific state:**
```bash
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state AL
```

**Run for the 6 in-scope oral health states (AL, GA, IN, MA, WA, WI):**
```bash
# Automated script runs all 6 states sequentially with incremental mode
bash scripts/discovery/discover_oral_health_states.sh
```

Or run individual states manually:
```bash
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state AL
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state GA
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state IN
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state MA
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state WA
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state WI
```

**Run for top N cities by population:**
```bash
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --top 100
```

**Disable incremental mode (rediscover all):**
```bash
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --all --no-incremental
```

**Change refresh threshold (default 90 days):**
```bash
python scripts/discovery/archive/comprehensive_discovery_pipeline.py --all --refresh-days 30
```

### Incremental Mode

By default, the script runs in **incremental mode**:
- Skips jurisdictions already discovered
- Only re-processes jurisdictions with stale data (older than 90 days by default)
- Significantly reduces API costs and processing time
- Use `--no-incremental` to force rediscovery of all jurisdictions

### Wikidata Enrichment

The pipeline automatically enriches incomplete discoveries using **Wikidata** (free, no API key required):

**What Wikidata Provides:**
- Official government website URLs
- Population data
- Social media accounts (Facebook, Twitter, YouTube channel IDs)

**When It's Used:**
- Automatically applied when primary discovery fails or is incomplete
- Especially helpful for smaller jurisdictions (CDPs, small cities)
- Example: "Alexandria CDP, AL" might have no direct .gov domain, but Wikidata may have its official Facebook page

**Benefits:**
- ✅ Completely free (no API limits)
- ✅ Community-maintained (Wikipedia's structured data)
- ✅ High quality for major cities
- ⚠️ May have gaps for very small jurisdictions

### Options

- `--state` - Filter to specific state (e.g., AL, CA, TX)
- `--top N` - Limit to top N jurisdictions by population
- `--all` - Process all jurisdictions (warning: 20,000+)
- `--youtube-api-key` - YouTube Data API v3 key for accurate statistics
- `--max-concurrent` - Maximum concurrent requests (default: 10)
- `--no-incremental` - Disable incremental mode (rediscover all)
- `--refresh-days` - Days before discovery is considered stale (default: 90)

### Output

Discovery results are saved to:
- `data/gold/jurisdictions_details.parquet` - Consolidated jurisdiction details including:
  - Website URLs
  - YouTube channel counts and data
  - Meeting platforms detected
  - Social media accounts
  - Discovery timestamps
  - Completeness scores
- `data/bronze/discovered_sources/discovery_results_*.json` - Detailed JSON output
- `data/bronze/discovered_sources/discovery_summary_*.csv` - Summary CSV reports

## Other Discovery Tools

### Discover Oral Health States
**Script:** `discover_oral_health_states.sh`

Convenience script that runs comprehensive discovery for all 6 in-scope oral health states (AL, GA, IN, MA, WA, WI) sequentially with incremental mode enabled.

```bash
bash scripts/discovery/discover_oral_health_states.sh
```

### URL Discovery Agent
**Script:** `url_discovery_agent.py`

Agent-based URL discovery using web search and scraping.

### Platform Detector
**Script:** `platform_detector.py`

Detects meeting platforms (Legistar, Granicus, etc.) from URLs.

### Batch Processor
**Script:** `batch_processor.py`

Batch processing for large-scale jurisdiction discovery operations.

### External URL Datasets
**Script:** `external_url_datasets.py`

Imports URLs from external curated datasets (City Scrapers, LocalView, etc.).

### Curated Sources
**Script:** `curated_sources.py`

Manages manually curated high-quality data sources.
