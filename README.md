---
title: Open Navigator
emoji: 🏛️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# 🏛️ Open Navigator

> ## CommunityOne: One Map for Every Community
>
> Every person deserves to find the help they need and have a voice in the decisions that shape their lives. But public resources are scattered, gaps go unseen, and communities are left navigating alone.
>
> CommunityOne changes that. One platform connects residents, leaders, and funders to what's really happening on the ground — so no community has to fight just to be seen.

AI-powered civic engagement platform with React + FastAPI web interface

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/React-18.2-61DAFB.svg)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688.svg)](https://fastapi.tiangolo.com)

## � Quick Links

**[⚛️ Open Navigator →](https://www.communityone.com)** - **LIVE APPLICATION** (search, filters, heatmap, data exploration)

**[📖 Documentation →](https://www.communityone.com/docs)** - Complete guides, architecture, and feature details

The documentation site includes:
- Features and capabilities
- Data sources and integrations
- Architecture and deployment options
- Policy topics and advocacy tools
- API reference and examples

---

## Quick Start

### Three Services

This project runs three separate services:

| Service | Port (Local) | Live URL | Description |
|---------|------|----------|-------------|
| **⚛️ Open Navigator** 🚀 | 5173 | [www.communityone.com](https://www.communityone.com) | **MAIN APPLICATION** - Search, filters, heatmap, data exploration |
| **📚 Documentation** | 3000 | [www.communityone.com/docs](https://www.communityone.com/docs) | Docusaurus site with complete guides and tutorials |
| **🔥 API Backend** | 8000 | [www.communityone.com/api](https://www.communityone.com/api) | FastAPI server with AI agents |

> **💡 LIVE DEMO:** Visit **[www.communityone.com](https://www.communityone.com)** to use the application!
> 
> **💻 LOCAL DEV:** After running `./start-all.sh`, visit **http://localhost:5173**

## 🚀 Deployment

**Deploy to Hugging Face Spaces** in 3 commands:

```bash
echo "HF_USERNAME=your_username" >> .env
./deploy-huggingface.sh
# Configure hardware and secrets at https://huggingface.co/spaces/YOUR_USERNAME/www.communityone.com
```

**Full deployment guides:**
- **[Hugging Face Spaces](website/docs/deployment/huggingface-spaces.md)** - Docker deployment (~$22/month)
- **[Databricks Apps](website/docs/deployment/databricks-apps.md)** - Enterprise deployment
- **[Local Development](website/docs/deployment/)** - Complete deployment documentation

The `deploy-huggingface.sh` script automatically:
- ✅ Tests builds locally (catches errors before pushing)
- ✅ Creates the Space on Hugging Face  
- ✅ Pushes code and triggers automatic build (~10-15 min)


### Get Running Locally

```bash
# Clone, install, and launch all three services in tmux
git clone https://github.com/getcommunityone/open-navigator.git
cd open-navigator
./install.sh                        # Python backend (creates .venv + .env)
cd web_app && npm install && cd ..  # React app
cd web_docs && npm install && cd .. # Documentation
./start-all.sh                      # API (8000) + App (5173) + Docs (3000)
```

**On Windows**, use the PowerShell equivalents (the `.sh` scripts and `make`
targets are Unix-only):

```powershell
.\install.ps1                       # Python backend (creates .venv + .env)
cd web_app;  npm install; cd ..
cd web_docs; npm install; cd ..
.\start-all.ps1                     # API (8000) + App (5173) + Docs (3000)
```

> **Don't run `uv sync` to install the backend** — the root `pyproject.toml` is a
> uv *workspace* and `uv sync` skips the top-level `requirements.txt` (the
> `pytest`/`black`/`ruff` tooling and `yt-dlp`). Use `install.sh` / `install.ps1`
> / `pip install -r requirements.txt`.

**👉 See the [Quick Start Guide](http://localhost:3000/docs/quickstart) for full setup
instructions** — prerequisites, the `.env` configuration tiers, Makefile and manual
install options, access points, and how to stop the services.

---

## Usage

### Command Line Interface

Always activate the virtual environment first:

```bash
source .venv/bin/activate
```

**API Server**

```bash
python main.py serve --host 0.0.0.0 --port 8000
```

**Jurisdiction Discovery**

```bash
# Test run
python main.py discover-jurisdictions --limit 100

# Single state
python main.py discover-jurisdictions --state CA

# Full discovery (~30k jurisdictions)
python main.py discover-jurisdictions

# View statistics
python main.py discovery-stats
```

**Data Ingestion**

```bash
# Census data (90,000+ jurisdictions)
python -m discovery.census_ingestion

# Census shapefiles (geographic boundaries)
python scripts/datasources/census/download_shapefiles.py --year 2023 --extract

# NCES school districts (13,000+)
python -m discovery.nces_ingestion

# Pre-built meeting datasets
python scripts/discovery/meetingbank_ingestion.py
python scripts/datasources/cityscrapers/city_scrapers_urls.py
python scripts/discovery/openstates_sources.py

# LocalView (requires Dataverse API key)
python scripts/discovery/localview_ingestion.py
```

**Scraping & Analysis**

```bash
# Scrape batch from discovered sites
python main.py scrape-batch --source discovered --limit 50

# Scrape single source
python main.py scrape --url "https://city.legistar.com" \
                      --state "CA" \
                      --municipality "San Francisco"

# Run analysis pipeline
python main.py analyze --targets-file examples/targets.json

# Generate heatmap
python main.py generate-heatmap --output heatmap.html
```

**Publishing Datasets**

```bash
# Publish to HuggingFace (requires HF_TOKEN in .env)
python main.py publish-to-hf --dataset all
python main.py publish-to-hf --dataset discovered-urls
python main.py publish-to-hf --dataset census --sample
```

### API Usage

**Start a workflow:**

```bash
curl -X POST "http://localhost:8000/workflow/start" \
     -H "Content-Type: application/json" \
     -d '{
       "scrape_targets": [
         {
           "url": "https://example-city.legistar.com",
           "municipality": "Example City",
           "state": "CA",
           "platform": "legistar"
         }
       ]
     }'
```

**Query opportunities:**

```bash
curl "http://localhost:8000/opportunities?state=CA&urgency=critical"
```

**Get heatmap:**

```bash
curl "http://localhost:8000/heatmap" > heatmap.html
```

### Python API

```python
import asyncio
from agents.orchestrator import OrchestratorAgent
from agents.scraper import ScraperAgent
from agents.parser import ParserAgent
from agents.classifier import ClassifierAgent

# Initialize orchestrator
orchestrator = OrchestratorAgent()

# Register agents
orchestrator.register_agent(ScraperAgent())
orchestrator.register_agent(ParserAgent())
orchestrator.register_agent(ClassifierAgent())

# Execute pipeline
targets = [
    {
        "url": "https://city.legistar.com",
        "municipality": "Example City",
        "state": "CA",
        "platform": "legistar"
    }
]

results = await orchestrator.execute_pipeline(targets)
```

---

## Project Structure

```
open-navigator/
├── agents/                 # Multi-agent AI system
├── api/                   # FastAPI application
├── frontend/             # React application (Open Navigator)
├── website/              # Docusaurus documentation
├── discovery/            # Data discovery modules
├── extraction/           # Document extraction
├── pipeline/             # Data pipeline components
├── visualization/        # Heatmap and charts
├── config/               # Configuration
├── tests/                # Test suite
├── dbt_project/          # dbt transformations (Bronze → Production)
├── scripts/              # Data ingestion and processing
├── main.py              # CLI entry point
└── requirements.txt     # Python dependencies
```

---

## Data Pipelines

### Hybrid Python + dbt Architecture

Open Navigator uses a **hybrid ETL approach**:
- **Python scripts** (`scripts/datasources/*/load_*.py`) for data ingestion, API calls, and AI analysis
- **dbt** (`dbt_project/`) for SQL-based transformations and data quality testing

```bash
# 1. Load data with Python
python scripts/datasources/gemini/load_meeting_transcripts_bronze.py  # AI extraction
python scripts/datasources/openstates/load_openstates_bulk.py        # State legislation
python scripts/datasources/irs/load_irs_bmf.py                       # Nonprofit data

# 2. Transform with dbt
cd dbt_project
dbt run      # Bronze → Production transformations
dbt test     # Data quality checks
dbt docs serve  # Interactive documentation

# 3. Export (optional)
python scripts/data/export_to_gold_parquet.py  # For HuggingFace distribution
```

**Learn more:**
- [dbt ETL Strategy](website/docs/development/dbt-etl-strategy.md) - Full architecture
- [Bronze to Production Merge](website/docs/development/bronze-to-production-merge.md) - Entity resolution strategy
- [dbt Project README](dbt_project/README.md) - Quick start guide

---

## Deployment Options

### 1. Databricks Apps (Production)

```bash
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=dapi...
export OPENAI_API_KEY=sk-...

./scripts/deploy-databricks-app.sh
```

See [DATABRICKS_APP_GUIDE.md](DATABRICKS_APP_GUIDE.md) for details.

### 2. Docker

```bash
docker-compose up -d
```

Starts:
- API server (port 8000)
- Qdrant vector database (port 6333)
- Jupyter notebook (port 8888)

### 3. Local Development

See [Quick Start](#quick-start) above.

---

## ⚡ Intel Arc GPU Optimization

**Run Llama 4 at NVIDIA-like speeds on Intel Arc integrated graphics!**

If you have **Intel Core Ultra 7** (or similar) with Arc Graphics + NPU, you can use **DuckDB + VSS** for 10-50x faster legislative analysis:

```bash
# Setup Intel-optimized environment
./scripts/enrichment_ai/intel_llm_setup.sh
source .venv-intel/bin/activate

# Run DuckDB vector search demo
python scripts/enrichment_ai/duckdb_vss_demo.py

# Run legislative analysis with LLM
python scripts/enrichment_ai/legislative_analysis_intel.py
```

**Why DuckDB for Local AI?**
- ⚡ **10-50x faster** than Postgres for context injection
- 🎯 **< 20ms** vector similarity search across 10K bills
- 🧠 **Embedded** - no server needed, runs locally
- 🤗 **Hugging Face Integration** - query HF datasets directly

**Performance:**
- **Context Injection**: 20ms vs 500ms (Postgres) = **25x faster**
- **LLM Inference**: 1,200 tok/s (Arc GPU) vs 350 tok/s (CPU) = **3.4x faster**
- **Vector Search**: 18ms vs 800ms = **44x faster**

**Features:**
- Extract interest groups from legislative testimony
- Identify lobbyists and their positions
- Analyze support/oppose scores with confidence
- Detect tradeoffs and compromises

**See full guide:** [Intel Arc Optimization Guide](website/docs/guides/intel-arc-optimization.md)

---

## 🤖 AI Integration (MCP Server)

**Connect your civic data to Claude and other AI assistants!**

Open Navigator includes a **Model Context Protocol (MCP)** server that lets AI assistants directly access your data:

```bash
# Install MCP dependencies
pip install mcp anthropic-mcp-sdk

# Run the server
python scripts/mcp/open_navigator_server.py
```

**What AI assistants can do:**
- 🏛️ Search 90,000+ jurisdictions by name or location
- 🏢 Query 1.8M nonprofits with Form 990 data
- 📜 Semantic search across 4.5M+ legislative documents
- 📊 Get real-time statistics and analytics
- 🔍 Vector search meetings and bills with natural language

**Example queries to Claude:**
> "Find all cities named Springfield in the database"

> "Show me 501c3 nonprofits in San Francisco focused on education"

> "What bills related to oral health were introduced in California?"

**Configure Claude Desktop:**

Add to `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "open-navigator": {
      "command": "python",
      "args": ["/path/to/open-navigator/scripts/mcp/open_navigator_server.py"],
      "env": {
        "DATABASE_URL": "postgresql://postgres:password@localhost:5433/open_navigator"
      }
    }
  }
}
```

**See full guide:** [MCP Server Documentation](website/docs/integrations/mcp-server.md)

---

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=agents --cov=pipeline --cov=visualization

# Specific test file
pytest tests/test_agents.py
```

---

## Configuration

Create `.env` file:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Databricks (optional)
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...

# HuggingFace (optional)
HF_TOKEN=hf_...

# Dataverse (optional)
DATAVERSE_API_KEY=...
```

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Documentation

- **[Full Documentation](http://localhost:3000)** - Complete guides and API reference
- **[Architecture](http://localhost:3000/docs/architecture)** - System architecture overview
- **[Quick Start](http://localhost:3000/docs/quickstart)** - Detailed setup instructions
- **[Quick Reference](http://localhost:3000/docs/quick-reference)** - Command reference card
- **[MCP Server](http://localhost:3000/docs/integrations/mcp-server)** - AI assistant integration guide
- **[Deployment](http://localhost:3000/docs/deployment/databricks-apps)** - Production deployment guides
- **[Case Studies](http://localhost:3000/docs/case-studies/tuscaloosa-complete)** - Real-world examples
- [CONTRIBUTING.md](CONTRIBUTING.md) - How to contribute

---

## Citations

This project uses several open datasets and research contributions. **Please see [CITATIONS.md](CITATIONS.md) for complete citation information.**

**Key Dataset:**
- **MeetingBank**: Hu et al., "MeetingBank: A Benchmark Dataset for Meeting Summarization", ACL 2023
  - Used for meeting discovery and analysis
  - 1,366 city council meetings from 6 U.S. cities
  - See [CITATIONS.md](CITATIONS.md) for full citation and BibTeX

---

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.

---

## Support

- GitHub Issues: [github.com/getcommunityone/open-navigator-for-engagement/issues](https://github.com/getcommunityone/open-navigator-for-engagement/issues)
- Email: johnbowyer@communityone.com

---

**Note**: This system is designed to support advocacy efforts. All generated content should be reviewed by humans before use.
