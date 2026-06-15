---
sidebar_position: 1
displayed_sidebar: developersSidebar
---

# For Developers & Technical Users

Welcome! This section contains **technical documentation** for developers, data scientists, and system administrators working with Open Navigator.

## Platform Scale & Data Volume

Open Navigator processes data at scale across the United States:

| Category | Count | Source |
|----------|-------|--------|
| **Total Jurisdictions** | 90,000+ | Census Bureau Gazetteer 2024 |
| **Counties** | 3,144 | All U.S. counties (FIPS coded) |
| **Municipalities** | 19,500+ | Cities, towns, villages, boroughs |
| **Townships** | 36,000+ | County subdivisions, census divisions |
| **School Districts** | 13,000+ | NCES Common Core of Data |
| **Nonprofit Organizations** | 3,000,000+ | IRS TEOS + ProPublica Nonprofit Explorer |
| **State Legislatures** | 50 | All U.S. states |
| **Video Channels** | 50+ | YouTube state legislature channels |
| **Meeting Datasets** | 1,000+ | MeetingBank, LocalView, City Scrapers |
| **.gov Domains** | 15,000+ | CISA validated government websites |

### Storage & Processing Requirements

**Estimated Data Volumes:**
- **Meeting Minutes**: 10-100 MB per municipality × 1,000+ cities = 10-100 GB
- **Financial Documents**: 5-50 MB per jurisdiction × 90,000 = 450 GB - 4.5 TB
- **Nonprofit 990s**: 1-5 MB per org × 3M = 3-15 TB
- **Video Content**: Variable (streaming recommended over storage)

**Medallion Architecture (Delta Lake):**
- **Bronze Layer**: Raw scraped data (largest storage footprint)
- **Silver Layer**: Cleaned/standardized (50-70% compression)
- **Gold Layer**: Analyzed/aggregated (90%+ compression)

### API Rate Limits & Quotas

**Free Tier (No Cost):**
- Census Bureau: Unlimited downloads
- NCES: Unlimited bulk downloads
- ProPublica API: Respectful use (~1 req/sec suggested)
- IRS TEOS: Bulk data downloads (monthly updates)
- CISA .gov Domains: GitHub dataset (updated daily)

**Paid/Limited:**
- OpenAI API: Pay per token (required for LLM features)
- Harvard Dataverse: API key recommended (free registration)

:::info[Complete Technical Citations & Standards]
For full citations, licenses, API documentation, and technical specifications:

**[Citations & Data Sources](/docs/data-sources/citations)**

Includes:
- **Academic Research**: MeetingBank (ACL 2023), LocalView (Harvard), Council Data Project, City Scrapers
- **Government APIs**: U.S. Census, NCES, IRS, Open States
- **Standards**: OCD-ID (OCDEP 2), Popolo Project, Schema.org, CEDS, OMOP CDM (OHDSI), IATI v2.03
- **Data Models**: Microsoft CDM for Nonprofits, OMOP vocabulary system
- **Fact-Checking**: N/A (not currently integrated)
- **Nonprofit Data**: IRS BMF (43,726 orgs from 5 states)
- **Churches & Faith-Based**: 4,372 congregations from IRS data
- **Enterprise Tech**: Microsoft (Nonprofit CDM), Google (Data Commons), AWS (Open Data), Databricks (Unity Catalog, MLflow), Snowflake, Salesforce (NPSP)
- **BibTeX citations** for academic papers and research use
:::

---

## What You'll Find Here

### 🚀 Setup & Quick Start

Get the platform running:
- **[Quick Start](/docs/quickstart)** - Detailed installation instructions
- **[Quick Reference](/docs/quick-reference)** - CLI commands cheat sheet
- **[Architecture](/docs/architecture)** - System design and components

### 📊 Data Sources (Technical)

Technical details on data ingestion:
- **[Jurisdiction Discovery](/docs/data-sources/jurisdiction-discovery)** - Finding 90,000+ government websites
- **[Census Data](/docs/data-sources/census-data)** - Ingesting Census Bureau datasets
- **[HuggingFace Datasets](/docs/data-sources/huggingface-datasets)** - Pre-built meeting collections
- **[YouTube Discovery](/docs/data-sources/youtube-discovery)** - Video channel scraping

### 🛠️ How-To Guides

Step-by-step technical guides:
- **[Jurisdiction Setup](/docs/guides/jurisdiction-setup)** - Configure discovery for your area
- **[HuggingFace Publishing](/docs/guides/huggingface-publishing)** - Publish datasets to HuggingFace Hub
- **[Handling Formats](/docs/guides/handling-formats)** - Process different document types
- **[Scraper Improvements](/docs/guides/scraper-improvements)** - Enhance scraping capabilities

### 🔌 Integrations

Connect external services:
- **[Dataverse Integration](/docs/integrations/dataverse)** - Harvard Dataverse API
- **[Frontend Integration](/docs/integrations/frontend)** - React application setup
- **[LocalView](/docs/integrations/localview)** - LocalView dataset ingestion

### 🚀 Deployment

Production deployment:
- **[Databricks Apps](/docs/deployment/databricks-apps)** - Deploy to Databricks
- **[Scale Deployment](/docs/deployment/scale)** - Handle large datasets
- **[Cost Management](/docs/deployment/costs)** - Optimize expenses

### 💻 Development

Contributing and development:
- **[Changelog](/docs/development/changelog)** - Version history
- **[Migration Guides](/docs/development/migration-v2)** - Upgrading between versions
- **[Refactoring Summary](/docs/development/refactoring-summary)** - Recent changes

## Quick Start (TL;DR)

**macOS / Linux:**

```bash
# Clone and install
git clone https://github.com/getcommunityone/open-navigator.git
cd open-navigator
./install.sh

# Install frontend and docs
cd web_app && npm install && cd ..
cd web_docs && npm install && cd ..

# Start all services
./start-all.sh

# Visit:
# - Main App:  http://localhost:5173
# - API Docs:  http://localhost:8001/docs
# - This Site: http://localhost:3000
```

**Windows (PowerShell)** — the `.sh` scripts are Unix-only (`start-all.sh` uses
`tmux`); use the PowerShell equivalents:

```powershell
git clone https://github.com/getcommunityone/open-navigator.git
cd open-navigator
.\install.ps1                       # Python backend (creates .venv + .env)

cd web_app;  npm install; cd ..
cd web_docs; npm install; cd ..

.\start-all.ps1                     # API (8001) + App (5173) + Docs (3000)
```

> **Don't use `uv sync` to install the backend** — the root `pyproject.toml` is a
> uv *workspace*, so `uv sync` installs only the `packages/*` libraries and skips
> the top-level `requirements.txt` (the `pytest`/`black`/`ruff` tooling and
> `yt-dlp`). Use `install.sh` / `install.ps1` / `pip install -r requirements.txt`.
> See the [Quick Start → Option 4: Windows (PowerShell)](/docs/quickstart#option-4-windows-powershell)
> for the ExecutionPolicy fix and details.

## Architecture Overview

```
┌─────────────────────────────────────────┐
│         Open Navigator Platform         │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────┐   ┌──────────────┐  │
│  │  React App   │   │  FastAPI     │  │
│  │  (Frontend)  │──▶│  (Backend)   │  │
│  │  Port 5173   │   │  Port 8001   │  │
│  └──────────────┘   └──────┬───────┘  │
│                             │           │
│  ┌──────────────────────────▼────────┐ │
│  │      Delta Lake (Data Storage)   │ │
│  │  • Bronze: Raw data              │ │
│  │  • Silver: Cleaned data          │ │
│  │  • Gold: Analyzed data           │ │
│  └──────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## Common Tasks

### Run Jurisdiction Discovery

```bash
source .venv/bin/activate

# Test run (100 jurisdictions)
python main.py discover-jurisdictions --limit 100

# Single state
python main.py discover-jurisdictions --state CA

# Full discovery (~30k jurisdictions)
python main.py discover-jurisdictions
```

### Ingest Reference Data

```bash
# Census jurisdictions (90,000+ entities)
python -m discovery.census_ingestion

# NCES school districts (13,000+)
python -m discovery.nces_ingestion

# Pre-built datasets
python scripts/discovery/meetingbank_ingestion.py
python scripts/datasources/cityscrapers/city_scrapers_urls.py
python scripts/discovery/openstates_sources.py
```

### Scrape Meeting Minutes

```bash
# Batch scraping from discovered sites
python main.py scrape-batch --source discovered --limit 50

# Single jurisdiction
python main.py scrape --url "https://chicago.legistar.com" \
                      --state "IL" \
                      --municipality "Chicago"
```

### Publish to HuggingFace

```bash
# Requires HF_TOKEN in .env
python main.py publish-to-hf --dataset all
python main.py publish-to-hf --dataset discovered-urls
python main.py publish-to-hf --dataset census --sample
```

## Technology Stack

### Backend
- **Python 3.11+** - Core language
- **FastAPI** - REST API framework
- **Delta Lake** - Data lakehouse storage
- **Databricks** - Production data platform
- **OpenAI API** - LLM capabilities

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool
- **TypeScript** - Type safety
- **Leaflet** - Interactive maps

### Data Processing
- **Pandas** - Data manipulation
- **BeautifulSoup** - HTML parsing
- **PyPDF2** - PDF extraction
- **Tesseract OCR** - Image to text

### Deployment
- **Docker** - Containerization
- **tmux** - Session management
- **Databricks Apps** - Production hosting

## API Reference

### Start API Server

```bash
python main.py serve --host 0.0.0.0 --port 8001
```

Visit http://localhost:8001/docs for interactive API documentation.

### Example: Start Workflow

```bash
curl -X POST "http://localhost:8001/workflow/start" \
     -H "Content-Type: application/json" \
     -d '{
       "scrape_targets": [
         {
           "url": "https://chicago.legistar.com",
           "municipality": "Chicago",
           "state": "IL",
           "platform": "legistar"
         }
       ]
     }'
```

### Example: Query Opportunities

```bash
curl "http://localhost:8001/opportunities?state=CA&urgency=critical"
```

## Development Workflow

### 1. Local Development

```bash
# Terminal 1: API (with hot reload)
source .venv/bin/activate
python main.py serve --reload

# Terminal 2: Frontend (with hot reload)
cd frontend
npm run dev

# Terminal 3: Documentation
cd website
npm start
```

### 2. Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=agents --cov=pipeline --cov=visualization

# Specific test file
pytest tests/test_agents.py
```

### 3. Deployment

```bash
# Deploy to Databricks
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=dapi...
./scripts/deploy-databricks-app.sh
```

## Data Pipeline

### Medallion Architecture

```
Bronze (Raw)          Silver (Cleaned)       Gold (Analyzed)
────────────────────────────────────────────────────────────
Scraped PDFs     →    Extracted text    →    Classifications
Meeting videos   →    Transcripts       →    Sentiment scores
Budget docs      →    Line items        →    Budget analysis
Form 990s        →    Financial data    →    Spending patterns
```

### File Locations

- **Bronze**: `data/bronze/` - Raw downloaded files
- **Silver**: `data/silver/` - Cleaned and standardized
- **Gold**: `data/gold/` - Enriched with analysis
- **Cache**: `cache/` - Temporary processing files

## Configuration

### Environment Variables

Create `.env` file:

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional (for production)
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...

# Optional (for publishing)
HF_TOKEN=hf_...

# Optional (for Harvard Dataverse)
DATAVERSE_API_KEY=...
```

### Settings File

Edit `config/settings.py` for:
- Delta Lake paths
- Scraping rate limits
- Batch sizes
- Model configurations

## Contributing

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR-USERNAME/oral-health-policy-pulse.git
cd oral-health-policy-pulse
git remote add upstream https://github.com/getcommunityone/open-navigator-for-engagement.git
```

### 2. Create Branch

```bash
git checkout -b feature/your-feature-name
```

### 3. Make Changes

- Add tests for new features
- Update documentation
- Follow existing code style
- Keep commits focused and atomic

### 4. Submit PR

```bash
git push origin feature/your-feature-name
# Then create PR on GitHub
```

See [CONTRIBUTING.md](https://github.com/getcommunityone/open-navigator-for-engagement/blob/main/CONTRIBUTING.md) for details.

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :8001
lsof -i :5173
lsof -i :3000

# Kill process
kill -9 <PID>
```

### Dependencies Not Installing

```bash
# Clear cache and reinstall
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Scraping Failures

Check logs:
```bash
tail -f logs/scraper.log
```

Adjust rate limits in `config/settings.py`.

## Next Steps

1. **Read Architecture** → [System Design](/docs/architecture)
2. **Set Up Environment** → [Quick Start](/docs/quickstart)
3. **Run Discovery** → [Jurisdiction Setup](/docs/guides/jurisdiction-setup)
4. **Deploy to Production** → [Databricks Apps](/docs/deployment/databricks-apps)
5. **Contribute** → [GitHub Issues](https://github.com/getcommunityone/open-navigator-for-engagement/issues)

## Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/getcommunityone/open-navigator-for-engagement/issues)
- **Documentation**: Browse the sidebar
- **API Docs**: http://localhost:8001/docs
- **Email**: johnbowyer@communityone.com
