# Open Navigator MCP Server

**Model Context Protocol (MCP) server for Open Navigator**

This directory contains the MCP server implementation that exposes Open Navigator's data sources to AI assistants like Claude.

## What's Here

- **`open_navigator_server.py`** - Main MCP server implementation

## Quick Start

### 1. Install Dependencies

```bash
pip install mcp anthropic-mcp-sdk
```

### 2. Run the Server

```bash
# From project root
python scripts/mcp/open_navigator_server.py
```

### 3. Configure Claude Desktop

Add to `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "open-navigator": {
      "command": "python",
      "args": ["/absolute/path/to/open-navigator/scripts/mcp/open_navigator_server.py"],
      "env": {
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333",
        "DATABASE_URL": "postgresql://postgres:password@localhost:5433/open_navigator"
      }
    }
  }
}
```

## Features

The MCP server provides AI assistants with access to:

- **90,000+ U.S. Jurisdictions** - Cities, counties, and states from Census data
- **1.8M Nonprofit Organizations** - IRS Form 990 data with financials
- **4.5M+ Legislative Documents** - Bills, versions, and documents from Open States
- **Vector Search** - Semantic search across bills and meetings using Qdrant
- **Real-time Analytics** - PostgreSQL queries for statistics and aggregates

## Available Tools

### Jurisdiction Tools
- `search_jurisdictions` - Search cities, counties, states by name/location

### Nonprofit Tools
- `get_nonprofits` - Query nonprofits with Form 990 data

### Legislative Tools
- `vector_search_bills` - Semantic search across bills
- `vector_search_meetings` - Semantic search across meeting transcripts

### Analytics Tools
- `get_bill_stats` - Legislative statistics by state/topic
- `search_meetings` - Keyword search meeting records

## Documentation

📖 **Full documentation:** [website/docs/integrations/mcp-server.md](../../website/docs/integrations/mcp-server.md)

Online: https://www.communityone.com/docs/integrations/mcp-server

## Architecture

```
┌─────────────────┐
│  Claude Desktop │
└────────┬────────┘
         │ MCP Protocol (stdio)
┌────────▼────────┐
│ open_navigator_ │
│    server.py    │
├─────────────────┤
│ Tools:          │
│ • Jurisdictions │──► HuggingFace Datasets
│ • Nonprofits    │──► HuggingFace Datasets
│ • Vector Search │──► Qdrant (localhost:6333)
│ • Analytics     │──► PostgreSQL (localhost:5433)
└─────────────────┘
```

## Requirements

**Python packages:**
- `mcp>=0.1.0`
- `anthropic-mcp-sdk>=0.1.0`
- `qdrant-client` (optional, for vector search)
- `psycopg2-binary` (optional, for analytics)
- `datasets` (optional, for HuggingFace datasets)

**Services:**
- Qdrant (vector database) - `docker-compose up -d qdrant`
- PostgreSQL (analytics) - `docker-compose up -d postgres`

## Example Queries to Claude

Once configured, you can ask Claude:

> "Find all cities named Springfield in the database"

> "Show me 501c3 nonprofits in San Francisco focused on education"

> "What bills related to oral health were introduced in California in 2024?"

> "Which Massachusetts cities discussed housing in recent meetings?"

Claude will automatically use the appropriate MCP tools to answer!

## Troubleshooting

**Server won't start?**
```bash
# Check Python version (need 3.11+)
python --version

# Install dependencies
pip install -r requirements.txt
```

**Tools unavailable?**
```bash
# Start Qdrant
docker-compose up -d qdrant

# Start PostgreSQL
docker-compose up -d postgres

# Verify
curl http://localhost:6333/collections
psql -h localhost -p 5433 -U postgres -d open_navigator -c "SELECT 1"
```

**Claude can't connect?**
- Use **absolute paths** in `claude_desktop_config.json`
- Restart Claude Desktop after config changes
- Check logs: `~/Library/Logs/Claude/mcp*.log` (macOS)

## Development

### Adding New Tools

1. Add tool definition to `list_tools()`:

```python
Tool(
    name="my_new_tool",
    description="What this tool does",
    inputSchema={
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        },
        "required": ["param"]
    }
)
```

2. Add handler to `call_tool()`:

```python
elif name == "my_new_tool":
    # Implementation
    return [TextContent(type="text", text=result)]
```

3. Test:

```bash
python scripts/mcp/open_navigator_server.py
```

### Testing with MCP Inspector

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Run inspector
mcp-inspector python scripts/mcp/open_navigator_server.py
```

Opens web UI to test tools interactively.

## Resources

- **MCP Protocol:** https://modelcontextprotocol.io/
- **Anthropic MCP SDK:** https://github.com/anthropics/anthropic-sdk-python
- **MCP Servers Repository:** https://github.com/modelcontextprotocol/servers
- **Open Navigator Docs:** https://www.communityone.com/docs

## License

MIT License - See [LICENSE](../../LICENSE)
