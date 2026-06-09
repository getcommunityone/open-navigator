---
sidebar_position: 1
---

# Model Context Protocol (MCP) Server

**Turn your Open Navigator data into an AI-accessible knowledge base!**

The Open Navigator MCP server exposes your entire civic data platform to AI assistants like Claude through the [Model Context Protocol](https://modelcontextprotocol.io/). This enables AI assistants to:

- 🏛️ Search 90,000+ U.S. jurisdictions
- 🏢 Query 3M+ nonprofit organizations
- 📜 Semantic search across 4.5M+ legislative documents
- 📊 Get real-time statistics and analytics
- 🔍 Vector search meetings and bills with natural language

## What is MCP?

**Model Context Protocol (MCP)** is an open protocol that standardizes how AI applications provide context to LLMs. Instead of manually copying data or writing custom integrations, MCP lets AI assistants directly access your data sources through a unified interface.

**Benefits:**
- ✅ **Live Data**: AI queries your latest data, not stale exports
- ✅ **Semantic Search**: Natural language queries with vector search
- ✅ **Type-Safe**: Structured tool definitions with validated inputs
- ✅ **Composable**: Combine multiple data sources in one query
- ✅ **Secure**: Run locally with no data leaving your machine

## Architecture

```
┌─────────────────────┐
│   Claude Desktop    │
│  (or other AI)      │
└──────────┬──────────┘
           │ MCP Protocol
┌──────────▼──────────┐
│  Open Navigator     │
│   MCP Server        │
├─────────────────────┤
│ ✓ HuggingFace Hub   │──► 90k jurisdictions
│ ✓ Qdrant Vector DB  │──► Semantic search
│ ✓ PostgreSQL        │──► Analytics & stats
└─────────────────────┘
```

## Quick Start

### 1. Install MCP SDK

```bash
# Activate virtual environment
source .venv/bin/activate

# Install MCP dependencies
pip install mcp anthropic-mcp-sdk
```

### 2. Start Required Services

```bash
# Start Qdrant (vector database)
docker-compose up -d qdrant

# Start PostgreSQL (if not already running)
docker-compose up -d postgres

# Verify services
curl http://localhost:6333/collections  # Qdrant
psql -h localhost -p 5433 -U postgres -d open_navigator -c "SELECT COUNT(*) FROM meetings"  # PostgreSQL
```

### 3. Run the MCP Server

```bash
# Test the server
python scripts/mcp/open_navigator_server.py
```

**Expected Output:**
```
🚀 Starting Open Navigator MCP Server...
   📊 HuggingFace Datasets: ✅
   🔍 Qdrant Vector Search: ✅
   💾 PostgreSQL Analytics: ✅

Ready to serve requests via MCP protocol
```

### 4. Configure Claude Desktop

Add to your Claude Desktop configuration file:

**macOS/Linux:** `~/.config/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "open-navigator": {
      "command": "python",
      "args": [
        "/absolute/path/to/open-navigator/scripts/mcp/open_navigator_server.py"
      ],
      "env": {
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333",
        "DATABASE_URL": "postgresql://postgres:password@localhost:5433/open_navigator"
      }
    }
  }
}
```

:::tip
Use absolute paths! Replace `/absolute/path/to/open-navigator` with your actual project path.
:::

### 5. Restart Claude Desktop

Close and reopen Claude Desktop. The MCP server will start automatically when you begin a conversation.

## Available Tools

### 🏛️ Jurisdiction Tools

#### `search_jurisdictions`

Search 90,000+ U.S. jurisdictions by name, type, or location.

**Parameters:**
- `query` (required): Search term (e.g., "San Francisco", "Orange County")
- `state` (optional): Filter by state code (e.g., "CA", "NY")
- `type` (optional): Filter by type ("city", "county", "state")
- `limit` (optional): Maximum results (default: 10)

**Example Claude Query:**
> "Find all cities named Springfield in the database"

**Returns:**
```json
[
  {
    "name": "Springfield",
    "state_code": "IL",
    "type": "city",
    "population": 116250,
    "fips_code": "1772000"
  },
  ...
]
```

---

### 🏢 Nonprofit Tools

#### `get_nonprofits`

Get nonprofit organizations with Form 990 data.

**Parameters:**
- `state` (required): State code (e.g., "CA", "NY", "TX")
- `city` (optional): Filter by city name
- `subsection` (optional): IRS subsection code (e.g., "03" for 501c3)
- `limit` (optional): Maximum results (default: 50)

**Example Claude Query:**
> "Show me 501c3 nonprofits in San Francisco, CA"

**Returns:**
```json
[
  {
    "ein": "941234567",
    "name": "Example Nonprofit",
    "city": "SAN FRANCISCO",
    "subsection": "03",
    "revenue": 1500000,
    "assets": 2000000
  },
  ...
]
```

---

### 📜 Legislative Tools

#### `vector_search_bills`

Semantic search across legislative bills using natural language.

**Parameters:**
- `query` (required): Natural language query
- `state` (optional): Filter by state code
- `limit` (optional): Maximum results (default: 10)

**Example Claude Query:**
> "Find bills related to oral health funding in California"

**Returns:**
```json
[
  {
    "bill_id": "CAB123",
    "title": "An Act relating to dental health services",
    "state": "CA",
    "session": "2025-2026",
    "score": 0.89,
    "summary": "Establishes funding for community dental clinics..."
  },
  ...
]
```

---

#### `vector_search_meetings`

Semantic search across meeting transcripts using natural language.

**Parameters:**
- `query` (required): Natural language query
- `municipality` (optional): Filter by city name
- `limit` (optional): Maximum results (default: 10)

**Example Claude Query:**
> "What did the Boston city council discuss about housing?"

**Returns:**
```json
[
  {
    "meeting_id": "MTG-2024-001",
    "title": "Boston City Council Meeting",
    "municipality": "Boston",
    "date": "2024-03-15",
    "score": 0.92,
    "excerpt": "Discussion on affordable housing initiatives..."
  },
  ...
]
```

---

### 📊 Analytics Tools

#### `get_bill_stats`

Get legislative statistics and aggregates by state/topic.

**Parameters:**
- `state` (optional): State code for state-specific stats
- `topic` (optional): Filter by topic/category

**Example Claude Query:**
> "Show me bill statistics for California"

**Returns:**
```json
[
  {
    "state": "CA",
    "topic": "Health",
    "total_bills": 1523,
    "bill_count": 1523
  },
  ...
]
```

---

#### `search_meetings`

Search meeting records by keyword, location, or date.

**Parameters:**
- `query` (optional): Search keyword
- `state` (optional): Filter by state
- `limit` (optional): Maximum results (default: 20)

**Example Claude Query:**
> "Find recent city council meetings in Massachusetts"

**Returns:**
```json
[
  {
    "name": "City Council Meeting",
    "organization_name": "Boston City Council",
    "state": "MA",
    "event_date": "2024-03-15",
    "description": "Regular meeting agenda..."
  },
  ...
]
```

## Example Use Cases

### 1. Multi-Source Research

**Query to Claude:**
> "Find nonprofits working on dental health in California cities with populations over 100k"

**What happens:**
1. Claude uses `search_jurisdictions` to find CA cities > 100k
2. Claude uses `get_nonprofits` to find dental health orgs
3. Claude combines results and filters
4. You get a comprehensive report!

---

### 2. Legislative Analysis

**Query to Claude:**
> "What oral health bills were introduced in 2024 and what did local governments say about them?"

**What happens:**
1. Claude uses `vector_search_bills` for oral health legislation
2. Claude uses `vector_search_meetings` for related discussions
3. Claude cross-references bills with meeting minutes
4. You get bill summaries + public sentiment!

---

### 3. Advocacy Targeting

**Query to Claude:**
> "Which California cities have discussed climate change but don't have major environmental nonprofits?"

**What happens:**
1. Claude searches meetings for climate discussions
2. Claude gets environmental nonprofits by city
3. Claude identifies gaps in nonprofit coverage
4. You get a list of cities to target for organizing!

## Troubleshooting

### Server Won't Start

**Check Python environment:**
```bash
source .venv/bin/activate
python --version  # Should be 3.11+
```

**Install missing dependencies:**
```bash
pip install mcp anthropic-mcp-sdk qdrant-client psycopg2-binary datasets
```

---

### Tools Show as Unavailable

**Verify services are running:**
```bash
# Check Qdrant
curl http://localhost:6333/collections

# Check PostgreSQL
psql -h localhost -p 5433 -U postgres -d open_navigator -c "SELECT 1"
```

**Check environment variables:**
- `QDRANT_HOST` (default: localhost)
- `QDRANT_PORT` (default: 6333)
- `DATABASE_URL` (default: postgresql://postgres:password@localhost:5433/open_navigator)

---

### Claude Can't Find Server

**Verify configuration path:**
```bash
# macOS/Linux
cat ~/.config/Claude/claude_desktop_config.json

# Windows
type %APPDATA%\Claude\claude_desktop_config.json
```

**Use absolute paths:**
- ❌ `./scripts/mcp/open_navigator_server.py`
- ✅ `/home/user/projects/open-navigator/scripts/mcp/open_navigator_server.py`

---

### HuggingFace Dataset Errors

**Authenticate with HuggingFace:**
```bash
# Login (if datasets are private)
huggingface-cli login

# Set token in environment
export HF_TOKEN=hf_...
```

**Check dataset availability:**
```bash
python -c "from datasets import load_dataset; ds = load_dataset('getcommunityone/open-navigator-census', split='train'); print(len(ds))"
```

## Advanced Configuration

### Environment Variables

All configurable via environment variables:

```json
{
  "mcpServers": {
    "open-navigator": {
      "command": "python",
      "args": ["/path/to/scripts/mcp/open_navigator_server.py"],
      "env": {
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333",
        "DATABASE_URL": "postgresql://postgres:password@localhost:5433/open_navigator",
        "HF_TOKEN": "hf_..."
      }
    }
  }
}
```

### Multiple Environments

Run different configurations for dev/prod:

```json
{
  "mcpServers": {
    "open-navigator-local": {
      "command": "python",
      "args": ["/path/to/scripts/mcp/open_navigator_server.py"],
      "env": {
        "DATABASE_URL": "postgresql://localhost:5433/open_navigator"
      }
    },
    "open-navigator-prod": {
      "command": "python",
      "args": ["/path/to/scripts/mcp/open_navigator_server.py"],
      "env": {
        "DATABASE_URL": "postgresql://prod-host:5432/open_navigator",
        "QDRANT_HOST": "prod-qdrant-host"
      }
    }
  }
}
```

## Performance Tips

### 1. Limit Result Sizes

Always specify `limit` parameters to avoid large payloads:

```
❌ "Find all nonprofits in California"
✅ "Find the top 50 largest nonprofits in California"
```

### 2. Use Vector Search for Semantic Queries

For natural language queries, prefer vector search over text search:

```
❌ search_meetings with keyword "education"
✅ vector_search_meetings with "What did they discuss about school funding?"
```

### 3. Filter Before Fetching

Apply filters early to reduce data transfer:

```
❌ Get all CA nonprofits, then filter by city
✅ get_nonprofits(state="CA", city="San Francisco")
```

### 4. Cache HuggingFace Datasets

Datasets are cached after first load (~1-2 min initial load, instant after):

```bash
# Pre-load datasets for faster queries
python -c "from datasets import load_dataset; load_dataset('getcommunityone/open-navigator-census')"
```

## Security Considerations

### Local-Only by Default

The MCP server runs **locally** and only responds to local processes (Claude Desktop). No data leaves your machine.

### Database Credentials

Store credentials securely:
- ✅ Use environment variables
- ✅ Use `.env` files (gitignored)
- ❌ Don't hardcode passwords in config

### Rate Limiting

For production deployments, add rate limiting:

```python
# In open_navigator_server.py
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=10, period=60)
@app.call_tool()
async def call_tool(name: str, arguments: dict):
    # ... existing code
```

## Next Steps

- 📖 Build Custom MCP Tools
- 🔍 Vector Search Optimization
- 🚀 Deploy MCP Server to Cloud
- 🤖 Integrate with Other AI Assistants

## Resources

- **MCP Protocol Spec:** https://modelcontextprotocol.io/
- **Anthropic MCP SDK:** https://github.com/anthropics/anthropic-sdk-python
- **Open Navigator GitHub:** https://github.com/getcommunityone/open-navigator
- **MCP Server Examples:** https://github.com/modelcontextprotocol/servers

---

**Questions?** Open an issue at [github.com/getcommunityone/open-navigator/issues](https://github.com/getcommunityone/open-navigator/issues)
