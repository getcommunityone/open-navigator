#!/usr/bin/env python3
"""
Open Navigator MCP Server
==========================

Model Context Protocol (MCP) server for Open Navigator data sources.

Provides AI assistants access to:
- 90,000+ U.S. jurisdictions (Census data)
- 1.8M nonprofit organizations (IRS data)
- 4.5M+ legislative documents (Open States)
- Vector search across bills and meetings
- Real-time statistics and aggregates

Usage:
    # Run locally
    python scripts/mcp/open_navigator_server.py
    
    # Configure in Claude Desktop (~/.config/Claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "open-navigator": {
          "command": "python",
          "args": ["/path/to/open-navigator/scripts/mcp/open_navigator_server.py"],
          "env": {
            "QDRANT_HOST": "localhost",
            "QDRANT_PORT": "6333",
            "DATABASE_URL": "postgresql://postgres:password@localhost:5433/open_navigator"
          }
        }
      }
    }
"""

import os
import sys
import json
import asyncio
from typing import Any, Optional
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent, Resource
except ImportError:
    print("❌ MCP SDK not installed. Install with: pip install mcp anthropic-mcp-sdk")
    sys.exit(1)

# Optional imports (graceful degradation)
try:
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("⚠️  Qdrant not available. Vector search tools disabled.")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    print("⚠️  PostgreSQL not available. Database tools disabled.")

try:
    from datasets import load_dataset
    DATASETS_AVAILABLE = True
except ImportError:
    DATASETS_AVAILABLE = False
    print("⚠️  HuggingFace datasets not available. Dataset tools disabled.")


# Initialize MCP server
app = Server("open-navigator")

# Initialize clients
qdrant_client = None
pg_conn = None

if QDRANT_AVAILABLE:
    try:
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
        print(f"✅ Connected to Qdrant at {qdrant_host}:{qdrant_port}")
    except Exception as e:
        print(f"⚠️  Failed to connect to Qdrant: {e}")
        QDRANT_AVAILABLE = False

if POSTGRES_AVAILABLE:
    try:
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5433/open_navigator")
        pg_conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        print(f"✅ Connected to PostgreSQL")
    except Exception as e:
        print(f"⚠️  Failed to connect to PostgreSQL: {e}")
        POSTGRES_AVAILABLE = False


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available datasets and collections"""
    resources = []
    
    if DATASETS_AVAILABLE:
        resources.extend([
            Resource(
                uri="hf://census-jurisdictions",
                name="U.S. Census Jurisdictions (90,000+)",
                description="Cities, counties, and states with geographic data",
                mimeType="application/x-parquet"
            ),
            Resource(
                uri="hf://nonprofits",
                name="Nonprofit Organizations (1.8M)",
                description="IRS-registered nonprofits with Form 990 data",
                mimeType="application/x-parquet"
            ),
        ])
    
    if QDRANT_AVAILABLE and qdrant_client:
        try:
            collections = qdrant_client.get_collections()
            for coll in collections.collections:
                resources.append(Resource(
                    uri=f"vector://{coll.name}",
                    name=f"{coll.name.title()} (Vector Search)",
                    description=f"Semantic search across {coll.points_count:,} documents",
                    mimeType="application/json"
                ))
        except Exception as e:
            print(f"⚠️  Error listing Qdrant collections: {e}")
    
    return resources


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    tools = []
    
    # HuggingFace dataset tools
    if DATASETS_AVAILABLE:
        tools.extend([
            Tool(
                name="search_jurisdictions",
                description="Search 90,000+ U.S. jurisdictions (cities, counties, states) by name, type, or location",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term (jurisdiction name)"
                        },
                        "state": {
                            "type": "string",
                            "description": "Filter by state code (e.g., CA, NY)"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["city", "county", "state"],
                            "description": "Filter by jurisdiction type"
                        },
                        "limit": {
                            "type": "number",
                            "default": 10,
                            "description": "Maximum results to return"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_nonprofits",
                description="Get nonprofit organizations in a location with Form 990 data",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "State code (e.g., CA, NY, TX)"
                        },
                        "city": {
                            "type": "string",
                            "description": "Filter by city name"
                        },
                        "subsection": {
                            "type": "string",
                            "description": "IRS subsection code (e.g., 03 for 501c3)"
                        },
                        "limit": {
                            "type": "number",
                            "default": 50,
                            "description": "Maximum results to return"
                        }
                    },
                    "required": ["state"]
                }
            ),
        ])
    
    # Vector search tools
    if QDRANT_AVAILABLE and qdrant_client:
        tools.extend([
            Tool(
                name="vector_search_bills",
                description="Semantic search across legislative bills using natural language",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query"
                        },
                        "state": {
                            "type": "string",
                            "description": "Filter by state code"
                        },
                        "limit": {
                            "type": "number",
                            "default": 10,
                            "description": "Maximum results to return"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="vector_search_meetings",
                description="Semantic search across meeting transcripts using natural language",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query"
                        },
                        "municipality": {
                            "type": "string",
                            "description": "Filter by city/municipality name"
                        },
                        "limit": {
                            "type": "number",
                            "default": 10,
                            "description": "Maximum results to return"
                        }
                    },
                    "required": ["query"]
                }
            ),
        ])
    
    # PostgreSQL analytics tools
    if POSTGRES_AVAILABLE and pg_conn:
        tools.extend([
            Tool(
                name="get_bill_stats",
                description="Get legislative statistics and aggregates by state/topic",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "State code (e.g., CA, NY)"
                        },
                        "topic": {
                            "type": "string",
                            "description": "Bill topic/category"
                        }
                    }
                }
            ),
            Tool(
                name="search_meetings",
                description="Search meeting records by keyword, location, or date",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword"
                        },
                        "state": {
                            "type": "string",
                            "description": "Filter by state"
                        },
                        "limit": {
                            "type": "number",
                            "default": 20,
                            "description": "Maximum results to return"
                        }
                    }
                }
            ),
        ])
    
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool"""
    
    # HuggingFace dataset tools
    if name == "search_jurisdictions" and DATASETS_AVAILABLE:
        try:
            ds = load_dataset("getcommunityone/open-navigator-census", split="train")
            
            # Filter by query
            query = arguments["query"].lower()
            results = ds.filter(lambda x: query in x["name"].lower())
            
            # Filter by state
            if arguments.get("state"):
                state = arguments["state"].upper()
                results = results.filter(lambda x: x.get("state_code") == state)
            
            # Filter by type
            if arguments.get("type"):
                jtype = arguments["type"].lower()
                results = results.filter(lambda x: jtype in x.get("type", "").lower())
            
            # Limit results
            limit = arguments.get("limit", 10)
            results = results.select(range(min(limit, len(results))))
            
            return [TextContent(
                type="text",
                text=json.dumps(results.to_pandas().to_dict('records'), indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "get_nonprofits" and DATASETS_AVAILABLE:
        try:
            state = arguments["state"].lower()
            ds = load_dataset(f"getcommunityone/open-navigator-nonprofits-{state}", split="train")
            df = ds.to_pandas()
            
            # Filter by city
            if arguments.get("city"):
                city = arguments["city"].lower()
                df = df[df['city'].str.lower().str.contains(city, na=False)]
            
            # Filter by subsection
            if arguments.get("subsection"):
                df = df[df['subsection'] == arguments["subsection"]]
            
            # Limit results
            limit = arguments.get("limit", 50)
            results = df.head(limit).to_dict('records')
            
            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    # Vector search tools
    elif name == "vector_search_bills" and QDRANT_AVAILABLE and qdrant_client:
        try:
            query_filter = None
            if arguments.get("state"):
                query_filter = {
                    "must": [{"key": "state", "match": {"value": arguments["state"]}}]
                }
            
            results = qdrant_client.search(
                collection_name="bills",
                query_text=arguments["query"],
                limit=arguments.get("limit", 10),
                query_filter=query_filter
            )
            
            formatted_results = [{
                "bill_id": r.payload.get("bill_id"),
                "title": r.payload.get("title"),
                "state": r.payload.get("state"),
                "session": r.payload.get("session"),
                "score": float(r.score),
                "summary": r.payload.get("summary", "")[:200]
            } for r in results]
            
            return [TextContent(
                type="text",
                text=json.dumps(formatted_results, indent=2)
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "vector_search_meetings" and QDRANT_AVAILABLE and qdrant_client:
        try:
            query_filter = None
            if arguments.get("municipality"):
                query_filter = {
                    "must": [{"key": "municipality", "match": {"value": arguments["municipality"]}}]
                }
            
            results = qdrant_client.search(
                collection_name="meetings",
                query_text=arguments["query"],
                limit=arguments.get("limit", 10),
                query_filter=query_filter
            )
            
            formatted_results = [{
                "meeting_id": r.payload.get("meeting_id"),
                "title": r.payload.get("title"),
                "municipality": r.payload.get("municipality"),
                "date": r.payload.get("date"),
                "score": float(r.score),
                "excerpt": r.payload.get("text", "")[:200]
            } for r in results]
            
            return [TextContent(
                type="text",
                text=json.dumps(formatted_results, indent=2)
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    # PostgreSQL tools
    elif name == "get_bill_stats" and POSTGRES_AVAILABLE and pg_conn:
        try:
            cur = pg_conn.cursor()
            
            if arguments.get("state"):
                cur.execute("""
                    SELECT 
                        state_code,
                        topic,
                        COUNT(*) as total_bills,
                        SUM(total_bills) as bill_count
                    FROM bill_map_aggregate
                    WHERE state_code = %s
                    GROUP BY state_code, topic
                    ORDER BY bill_count DESC
                    LIMIT 20
                """, (arguments["state"],))
            else:
                cur.execute("""
                    SELECT 
                        state_code,
                        COUNT(DISTINCT topic) as topics,
                        SUM(total_bills) as total_bills
                    FROM bill_map_aggregate
                    GROUP BY state
                    ORDER BY total_bills DESC
                    LIMIT 50
                """)
            
            results = cur.fetchall()
            return [TextContent(
                type="text",
                text=json.dumps([dict(r) for r in results], indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "search_meetings" and POSTGRES_AVAILABLE and pg_conn:
        try:
            cur = pg_conn.cursor()
            query = arguments.get("query", "")
            state = arguments.get("state")
            limit = arguments.get("limit", 20)
            
            if state:
                cur.execute("""
                    SELECT 
                        name, organization_name, state, event_date,
                        description
                    FROM meetings
                    WHERE state = %s 
                    AND (
                        name ILIKE %s 
                        OR organization_name ILIKE %s
                        OR description ILIKE %s
                    )
                    ORDER BY event_date DESC
                    LIMIT %s
                """, (state, f"%{query}%", f"%{query}%", f"%{query}%", limit))
            else:
                cur.execute("""
                    SELECT 
                        name, organization_name, state, event_date,
                        description
                    FROM meetings
                    WHERE name ILIKE %s 
                    OR organization_name ILIKE %s
                    OR description ILIKE %s
                    ORDER BY event_date DESC
                    LIMIT %s
                """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))
            
            results = cur.fetchall()
            return [TextContent(
                type="text",
                text=json.dumps([dict(r) for r in results], indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


async def main():
    """Run the MCP server"""
    print("🚀 Starting Open Navigator MCP Server...")
    print(f"   📊 HuggingFace Datasets: {'✅' if DATASETS_AVAILABLE else '❌'}")
    print(f"   🔍 Qdrant Vector Search: {'✅' if QDRANT_AVAILABLE and qdrant_client else '❌'}")
    print(f"   💾 PostgreSQL Analytics: {'✅' if POSTGRES_AVAILABLE and pg_conn else '❌'}")
    print()
    print("Ready to serve requests via MCP protocol")
    
    # Run the server
    async with app.run_async():
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
