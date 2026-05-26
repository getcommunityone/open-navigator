"""
FastAPI application for the Oral Health Policy Pulse system.

Provides REST API endpoints for:
- Initiating policy analysis workflows
- Querying advocacy opportunities
- Retrieving generated materials
- Accessing visualizations
- System status and monitoring
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import sys
import time
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel, Field
from loguru import logger
import os

from agents.orchestrator import OrchestratorAgent
from agents.scraper import ScraperAgent
from agents.parser import ParserAgent
from agents.classifier import ClassifierAgent
from agents.sentiment import SentimentAnalyzerAgent
from agents.advocacy import AdvocacyWriterAgent
from pipeline.delta_lake import DeltaLakePipeline
from visualization.heatmap import AdvocacyHeatmap
from config import settings

# Configure logging with rotation and retention
# Output to both file (with rotation) and stderr (for HuggingFace container logs)
logger.remove()  # Remove default handler

# Add console output (shows in HuggingFace container logs)
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level
)

# Add file output with rotation and retention
logger.add(
    settings.log_file,
    rotation="500 MB",      # Create new file when size exceeds 500MB
    retention="10 days",    # Delete logs older than 10 days
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}"
)

# Initialize FastAPI app
app = FastAPI(
    title="Open Navigator API",
    description="Multi-agent system for analyzing local government oral health policy discussions",
    version="1.0.0",
    docs_url=None,  # Disable default docs to use custom
    redoc_url="/redoc",  # Keep ReDoc at /redoc
    openapi_tags=[
        {
            "name": "auth",
            "description": "Authentication and user management"
        },
        {
            "name": "social",
            "description": "Social features - follow users, leaders, organizations, and causes"
        },
        {
            "name": "workflows",
            "description": "Policy analysis workflows"
        },
        {
            "name": "opportunities",
            "description": "Advocacy opportunities"
        }
    ]
)

# Custom OpenAPI schema with logo
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add custom logo
    openapi_schema["info"]["x-logo"] = {
        "url": "/static/communityone_logo.svg",
        "altText": "CommunityOne Logo"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests with timing and response info"""
    start_time = time.time()
    
    # Get client info
    client_host = request.client.host if request.client else "unknown"
    
    # Log incoming request
    logger.info(f"➡️  {request.method} {request.url.path} - Client: {client_host}")
    
    # Process request
    try:
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Get response size if available
        response_size = response.headers.get("content-length", "unknown")
        
        # Log response with appropriate emoji based on status
        if response.status_code < 400:
            logger.info(
                f"✅ {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Duration: {duration_ms:.2f}ms - "
                f"Size: {response_size} bytes"
            )
        elif response.status_code < 500:
            logger.warning(
                f"⚠️  {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Duration: {duration_ms:.2f}ms"
            )
        else:
            logger.error(
                f"❌ {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Duration: {duration_ms:.2f}ms"
            )
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"💥 {request.method} {request.url.path} - "
            f"Error: {str(e)} - "
            f"Duration: {duration_ms:.2f}ms"
        )
        raise

# Mount static files for logo
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "public")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    census_map_dir = Path(static_dir) / "data" / "census-map"
    if census_map_dir.is_dir():
        app.mount("/data/census-map", StaticFiles(directory=census_map_dir), name="census_map_public")
    else:
        logger.warning(f"Census map static bundle missing (expected {census_map_dir})")
else:
    logger.warning(f"Static directory not found: {static_dir}")

# Serve favicon at root
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon"""
    from fastapi.responses import FileResponse
    api_static = Path(__file__).parent / "static" / "favicon.ico"
    if api_static.exists():
        return FileResponse(api_static)
    # Fallback to frontend public
    frontend_favicon = Path(static_dir) / "favicon.ico"
    if frontend_favicon.exists():
        return FileResponse(frontend_favicon)
    raise HTTPException(status_code=404, detail="Favicon not found")


# Custom Exception Handlers for better error messages
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with user-friendly messages"""
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "message": f"The requested resource '{request.url.path}' was not found.",
                "path": request.url.path,
                "suggestion": "Check the URL and try again, or visit /docs for available endpoints.",
                "documentation": "/docs",
                "support": "johnbowyer@communityone.com"
            }
        )
    elif exc.status_code == 401:
        return JSONResponse(
            status_code=401,
            content={
                "error": "Unauthorized",
                "message": exc.detail or "Authentication required to access this resource.",
                "suggestion": "Please log in or provide valid credentials.",
                "login": "/api/auth/google"
            }
        )
    elif exc.status_code == 403:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Forbidden",
                "message": exc.detail or "You don't have permission to access this resource.",
                "suggestion": "Contact support if you believe this is an error.",
                "support": "johnbowyer@communityone.com"
            }
        )
    else:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail or "An error occurred",
                "status_code": exc.status_code,
                "path": request.url.path
            }
        )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed, user-friendly messages"""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": "The request data is invalid. Please check the fields below.",
            "errors": errors,
            "suggestion": "Review the error details and correct the invalid fields.",
            "documentation": "/docs"
        }
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """Handle internal server errors with generic message (hide details from users)"""
    logger.error(f"Internal server error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Something went wrong on our end. We've been notified and are working to fix it.",
            "path": request.url.path,
            "suggestion": "Please try again later or contact support if the problem persists.",
            "support": "johnbowyer@communityone.com"
        }
    )


# Include authentication routes
from api.routes import auth as auth_routes
from api.routes import social as social_routes
from api.routes import search as search_routes
# Use Neon database for fast stats queries (500x faster than parquet)
from api.routes import stats_neon as stats_routes  # Was: stats
from api.routes import contact as contact_routes
# Use hybrid approach for bills: Neon for map, parquet for drill-down (saves space)
from api.routes import bills_neon as bills_routes  # Was: bills
from api.routes import data_deletion as data_deletion_routes
from api.routes import trending as trending_routes
from api.routes import lighthouse_reports as lighthouse_reports_routes
from api.routes import jurisdiction_mapping as jurisdiction_mapping_routes
from api.routes import batch_jobs as batch_jobs_routes
from api.routes import locations as locations_routes
from api.database import init_db

app.include_router(auth_routes.router, prefix="/api")
app.include_router(social_routes.router, prefix="/api")
app.include_router(search_routes.router, prefix="/api")
app.include_router(stats_routes.router, prefix="/api", tags=["stats"])
app.include_router(contact_routes.router, prefix="/api")
app.include_router(bills_routes.router, prefix="/api")
app.include_router(data_deletion_routes.router, prefix="/api", tags=["privacy"])
app.include_router(trending_routes.router)
app.include_router(lighthouse_reports_routes.router, prefix="/api")
app.include_router(jurisdiction_mapping_routes.router, prefix="/api")
app.include_router(batch_jobs_routes.router, prefix="/api")
app.include_router(locations_routes.router, prefix="/api")

# Custom Swagger UI with logo
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with CommunityOne logo"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Documentation",
        swagger_favicon_url="/static/communityone_logo_64.png",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "docExpansion": "list",
            "filter": True,
            "syntaxHighlight.theme": "monokai"
        }
    )

# Initialize database on startup
@app.on_event("startup")
async def init_database():
    """Initialize authentication database"""
    try:
        init_db()
        logger.info("✅ Authentication database initialized")
    except Exception as e:
        logger.warning(f"⚠️  Database initialization skipped: {e}")

# Initialize components
orchestrator = OrchestratorAgent()
pipeline = DeltaLakePipeline()
heatmap_generator = AdvocacyHeatmap()


# Pydantic models for API
class ScrapeTarget(BaseModel):
    """Configuration for a scraping target."""
    url: str
    municipality: str
    state: str
    platform: str = "generic"


class WorkflowRequest(BaseModel):
    """Request to start a new analysis workflow."""
    scrape_targets: List[ScrapeTarget]
    date_range: Optional[Dict[str, str]] = None
    description: Optional[str] = None


class WorkflowResponse(BaseModel):
    """Response for workflow operations."""
    workflow_id: str
    status: str
    message: str


class OpportunityFilter(BaseModel):
    """Filters for querying opportunities."""
    state: Optional[str] = None
    municipality: Optional[str] = None
    topic: Optional[str] = None
    urgency: Optional[str] = None
    min_date: Optional[date] = None
    max_date: Optional[date] = None


class OpportunityResponse(BaseModel):
    """Response containing advocacy opportunities."""
    opportunities: List[Dict[str, Any]]
    total_count: int
    filters_applied: Dict[str, Any]


class SystemStatus(BaseModel):
    """System status information."""
    status: str
    active_workflows: int
    agent_status: Dict[str, Any]
    last_update: datetime


# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with API information."""
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Open Navigator API</title>
            <style>
                body { 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    max-width: 900px; 
                    margin: 50px auto; 
                    padding: 20px;
                    line-height: 1.6;
                }
                .header {
                    display: flex;
                    align-items: center;
                    gap: 20px;
                    margin-bottom: 30px;
                    border-bottom: 2px solid #1976d2;
                    padding-bottom: 20px;
                }
                .logo {
                    width: 80px;
                    height: 80px;
                }
                h1 { 
                    color: #1976d2;
                    margin: 0;
                }
                .tagline {
                    color: #666;
                    font-size: 1.1em;
                }
                .endpoint { 
                    background: linear-gradient(135deg, #f5f5f5 0%, #e8f4f8 100%);
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 8px;
                    border-left: 4px solid #1976d2;
                }
                .endpoint strong {
                    color: #1976d2;
                }
                code { 
                    background: #e0e0e0;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-family: 'Courier New', monospace;
                }
                .docs-link {
                    display: inline-block;
                    background: #1976d2;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 6px;
                    margin-top: 20px;
                    transition: background 0.3s;
                }
                .docs-link:hover {
                    background: #1565c0;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <img src="/static/communityone_logo.svg" alt="CommunityOne Logo" class="logo">
                <div>
                    <h1>Open Navigator API</h1>
                    <p class="tagline">CommunityOne: The open path to everything local</p>
                </div>
            </div>
            
            <h2>🔑 Key Endpoints:</h2>
            <div class="endpoint">
                <strong>POST /workflow/start</strong> - Start a new analysis workflow
            </div>
            <div class="endpoint">
                <strong>GET /opportunities</strong> - Query advocacy opportunities
            </div>
            <div class="endpoint">
                <strong>GET /heatmap</strong> - Get advocacy heatmap visualization
            </div>
            <div class="endpoint">
                <strong>GET /status</strong> - System status and health
            </div>
            <div class="endpoint">
                <strong>POST /auth/login/{provider}</strong> - OAuth login (HuggingFace, Google, Facebook, GitHub)
            </div>
            
            <a href="/docs" class="docs-link">📚 View Full API Documentation</a>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/workflow/start", response_model=WorkflowResponse)
async def start_workflow(
    request: WorkflowRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new policy analysis workflow.
    
    This initiates the full multi-agent pipeline:
    1. Scrape meeting minutes from specified sources
    2. Parse and structure the data
    3. Classify by oral health topics
    4. Analyze sentiment and policy stance
    5. Generate advocacy materials
    """
    try:
        # Register agents with orchestrator
        orchestrator.register_agent(ScraperAgent())
        orchestrator.register_agent(ParserAgent())
        orchestrator.register_agent(ClassifierAgent())
        orchestrator.register_agent(SentimentAnalyzerAgent())
        orchestrator.register_agent(AdvocacyWriterAgent())
        
        # Convert targets to dict format
        targets = [target.dict() for target in request.scrape_targets]
        
        # Start workflow in background
        background_tasks.add_task(
            orchestrator.execute_pipeline,
            targets,
            request.date_range
        )
        
        return WorkflowResponse(
            workflow_id="wf-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S"),
            status="started",
            message=f"Workflow started with {len(targets)} targets"
        )
        
    except Exception as e:
        logger.error(f"Error starting workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """Get the status of a specific workflow."""
    # Query workflow status from orchestrator
    # This is a placeholder - would query actual workflow state
    return {
        "workflow_id": workflow_id,
        "status": "running",
        "stage": "classification",
        "progress": 0.6
    }


@app.get("/opportunities", response_model=OpportunityResponse)
async def get_opportunities(
    state: Optional[str] = Query(None, description="Filter by state code"),
    municipality: Optional[str] = Query(None, description="Filter by municipality"),
    topic: Optional[str] = Query(None, description="Filter by policy topic"),
    urgency: Optional[str] = Query(None, description="Filter by urgency level"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return")
):
    """
    Query advocacy opportunities.
    
    Returns a list of identified opportunities for advocacy action
    based on the specified filters.
    """
    try:
        # Query from Delta Lake
        opportunities = pipeline.query_opportunities_by_state(state, urgency)
        
        # Apply additional filters
        if municipality:
            opportunities = [
                opp for opp in opportunities
                if opp.get("municipality", "").lower() == municipality.lower()
            ]
        
        if topic:
            opportunities = [
                opp for opp in opportunities
                if opp.get("topic") == topic
            ]
        
        # Limit results
        opportunities = opportunities[:limit]
        
        return OpportunityResponse(
            opportunities=opportunities,
            total_count=len(opportunities),
            filters_applied={
                "state": state,
                "municipality": municipality,
                "topic": topic,
                "urgency": urgency
            }
        )
        
    except Exception as e:
        logger.error(f"Error querying opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# React frontend endpoints with /api/ prefix
@app.get("/api/opportunities")
async def get_api_opportunities(
    state: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    limit: int = Query(100)
):
    """API endpoint for React frontend opportunities page - returns fluoridation bills as advocacy opportunities."""
    try:
        import duckdb
        from pathlib import Path
        import random
        
        # State center coordinates for mapping
        STATE_COORDS = {
            'AL': (32.806671, -86.791130),
            'GA': (33.040619, -83.643074),
            'IN': (39.849426, -86.258278),
            'MA': (42.230171, -71.530106),
            'WA': (47.400902, -121.490494),
            'WI': (44.268543, -89.616508)
        }
        
        # Build query for fluoridation-related bills
        states = [state] if state else list(STATE_COORDS.keys())
        opportunities = []
        
        # Use consolidated parquet file
        parquet_path = Path("data/gold/bills_bills.parquet")
        if not parquet_path.exists():
            return {"opportunities": [], "total": 0}
        
        # Build state filter
        state_filter = f"state IN ({','.join(repr(s) for s in states)})"
        
        # Query for fluoridation-related bills
        query = f"""
            SELECT 
                state,
                title,
                identifier,
                session,
                latest_action,
                created_at,
                updated_at
            FROM read_parquet('{parquet_path}')
            WHERE ({state_filter})
                AND (LOWER(title) LIKE '%fluorid%' 
                   OR LOWER(title) LIKE '%dental%'
                   OR LOWER(title) LIKE '%oral health%'
                   OR LOWER(title) LIKE '%water treat%')
            LIMIT {limit}
        """
        
        result = duckdb.query(query).fetchall()
        
        # Convert to opportunities format
        for row in result:
                state_code, title, identifier, session, latest_action, created_at, updated_at = row
                
                # Determine urgency based on keywords
                title_lower = title.lower() if title else ""
                # Check for fluoride topics (both pro and anti fluoride are critical)
                if 'fluoride' in title_lower or 'fluorin' in title_lower or 'water' in title_lower:
                    urgency_level = 'critical'
                    confidence = 0.9
                    topic_type = 'water_fluoridation'
                elif 'dental' in title_lower:
                    urgency_level = 'high'
                    confidence = 0.75
                    topic_type = 'school_dental_screening'
                else:
                    urgency_level = 'medium'
                    confidence = 0.6
                    topic_type = 'medicaid_dental_expansion'
                
                # Filter by topic if specified
                if topic and topic_type != topic:
                    continue
                
                # Filter by urgency if specified
                if urgency and urgency_level != urgency:
                    continue
                
                # Get state coordinates with slight random offset for multiple bills
                base_lat, base_lon = STATE_COORDS[state_code]
                lat_offset = random.uniform(-0.5, 0.5)
                lon_offset = random.uniform(-0.5, 0.5)
                
                opportunities.append({
                    'state': state_code,
                    'municipality': f'{state_code} Legislature',
                    'latitude': base_lat + lat_offset,
                    'longitude': base_lon + lon_offset,
                    'topic': topic_type,
                    'urgency': urgency_level,
                    'confidence': confidence,
                    'meeting_date': updated_at.isoformat() if updated_at else created_at.isoformat(),
                    'title': title,
                    'bill_id': identifier,
                    'session': session,
                    'latest_action': latest_action
                })
        
        return {"opportunities": opportunities[:limit]}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"opportunities": []}


@app.get("/api/documents")
async def get_api_documents(
    search: Optional[str] = Query(None),
    page: int = Query(1),
    limit: int = Query(20)
):
    """API endpoint for React frontend documents page."""
    try:
        # Get all opportunities (documents)
        documents = pipeline.query_opportunities_by_state(None, None)
        
        # Apply search filter
        if search:
            search_lower = search.lower()
            documents = [
                d for d in documents
                if search_lower in d.get("title", "").lower() or
                   search_lower in d.get("municipality", "").lower() or
                   search_lower in d.get("content", "").lower()
            ]
        
        # Paginate
        start = (page - 1) * limit
        end = start + limit
        
        return {
            "documents": documents[start:end],
            "total": len(documents),
            "page": page,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"documents": [], "total": 0}


@app.get("/opportunities/{opportunity_id}")
async def get_opportunity_detail(opportunity_id: str):
    """Get detailed information about a specific opportunity."""
    # Query specific opportunity
    document = pipeline.get_document_by_id(opportunity_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    
    return document


@app.get("/opportunities/{opportunity_id}/materials")
async def get_advocacy_materials(opportunity_id: str):
    """Get generated advocacy materials for an opportunity."""
    # Query materials from Delta Lake
    # This is a placeholder
    return {
        "opportunity_id": opportunity_id,
        "materials": {
            "email": {
                "subject": "Support Oral Health Policy",
                "body": "..."
            },
            "talking_points": [],
            "social_media": {}
        }
    }


@app.get("/heatmap", response_class=HTMLResponse)
async def get_heatmap(
    urgency: Optional[str] = Query(None, description="Filter by urgency level")
):
    """
    Get interactive heatmap visualization.
    
    Returns an HTML page with an interactive map showing
    advocacy opportunities across the country.
    """
    try:
        # Query opportunities
        opportunities = pipeline.query_opportunities_by_state(None, urgency)
        
        # Generate map
        m = heatmap_generator.create_folium_map(
            opportunities,
            title="Open Navigator - Advocacy Heatmap"
        )
        
        # Return HTML
        return HTMLResponse(content=m._repr_html_())
        
    except Exception as e:
        logger.error(f"Error generating heatmap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard")
async def get_dashboard():
    """
    Get complete dashboard data including statistics and visualizations.
    """
    try:
        # Query all opportunities
        opportunities = pipeline.query_opportunities_by_state(None, None)
        
        # Generate dashboard
        dashboard = heatmap_generator.create_dashboard(opportunities)
        
        # Convert visualizations to JSON-serializable format
        return {
            "statistics": dashboard["statistics"],
            "topic_distribution": dashboard["topic_distribution"].to_json(),
            "timeline": dashboard["timeline"].to_json()
        }
        
    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard")
async def get_api_dashboard():
    """
    Get dashboard statistics for React frontend.
    Returns data in format expected by frontend Dashboard component.
    """
    try:
        # Query all opportunities
        opportunities = pipeline.query_opportunities_by_state(None, None)
        
        # Count topics
        topics_count = {}
        for opp in opportunities:
            topic = opp.get("topic", "unknown")
            topics_count[topic] = topics_count.get(topic, 0) + 1
        
        # Get unique states
        states = set(opp.get("state") for opp in opportunities if opp.get("state"))
        
        # Get recent opportunities (last 10)
        recent = sorted(
            opportunities,
            key=lambda x: x.get("meeting_date", ""),
            reverse=True
        )[:10]
        
        return {
            "total_documents": len(opportunities),
            "total_opportunities": len(opportunities),
            "states_monitored": len(states),
            "topics": topics_count,
            "recent_opportunities": recent
        }
        
    except Exception as e:
        logger.error(f"Error generating API dashboard: {e}")
        # Return mock data if there's an error
        return {
            "total_documents": 0,
            "total_opportunities": 0,
            "states_monitored": 0,
            "topics": {},
            "recent_opportunities": []
        }


@app.get("/topics")
async def get_topics():
    """Get list of all policy topics being tracked."""
    return {
        "topics": settings.policy_topics,
        "count": len(settings.policy_topics)
    }


@app.get("/states")
async def get_states():
    """Get list of all states with active opportunities."""
    # Query distinct states from database
    states = ["CA", "NY", "TX", "FL", "IL"]  # Placeholder
    
    return {
        "states": states,
        "count": len(states)
    }


@app.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get current system status and health."""
    try:
        agent_status = orchestrator.get_all_agent_states()
        
        return SystemStatus(
            status="operational",
            active_workflows=len(orchestrator.active_workflows),
            agent_status=agent_status,
            last_update=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return SystemStatus(
            status="error",
            active_workflows=0,
            agent_status={},
            last_update=datetime.utcnow()
        )


@app.get("/nonprofits")
async def search_nonprofits(
    location: str = Query("Tuscaloosa, AL", description="City, State format"),
    keyword: Optional[str] = Query(None, description="Service keyword (e.g., 'dental', 'health')"),
    state: Optional[str] = Query(None, description="2-letter state code (e.g., 'AL')"),
    ntee_code: Optional[str] = Query(None, description="NTEE code (e.g., 'E' for health)"),
    source: Optional[str] = Query(None, description="Data source: 'propublica', 'everyorg', 'all'")
):
    """
    Search for nonprofits using free open data APIs.
    
    Integrates data from:
    - ProPublica Nonprofit Explorer (financial data, NTEE codes)
    - Every.org (mission statements, logos)
    - IRS TEOS (official tax-exempt status)
    
    Example: /nonprofits?location=Tuscaloosa,AL&keyword=dental&ntee_code=E
    """
    try:
        from scripts.datasources.irs.nonprofit_discovery import NonprofitDiscovery
        
        discovery = NonprofitDiscovery()
        results = []
        
        # Parse location for state/city
        location_parts = location.split(',')
        city = location_parts[0].strip() if len(location_parts) > 0 else None
        state_from_location = location_parts[1].strip() if len(location_parts) > 1 else None
        state_code = state or state_from_location or "AL"
        
        # Determine which sources to query
        sources_to_query = ['propublica', 'everyorg'] if source == 'all' or not source else [source]
        
        # Query ProPublica
        if 'propublica' in sources_to_query:
            try:
                propublica_results = discovery.search_propublica(
                    state=state_code,
                    city=city,
                    ntee_code=ntee_code
                )
                results.extend(propublica_results)
                logger.info(f"ProPublica: Found {len(propublica_results)} organizations")
            except Exception as e:
                logger.warning(f"ProPublica search failed: {e}")
        
        # Query Every.org
        if 'everyorg' in sources_to_query:
            try:
                causes = []
                if keyword:
                    # Map keywords to causes
                    keyword_lower = keyword.lower()
                    if 'health' in keyword_lower or 'dental' in keyword_lower or 'medical' in keyword_lower:
                        causes.append('health')
                    if 'education' in keyword_lower or 'school' in keyword_lower:
                        causes.append('education')
                
                everyorg_results = discovery.search_everyorg(
                    location=location,
                    causes=causes if causes else None
                )
                results.extend(everyorg_results)
                logger.info(f"Every.org: Found {len(everyorg_results)} organizations")
            except Exception as e:
                logger.warning(f"Every.org search failed: {e}")
        
        # Filter by keyword if provided
        if keyword and results:
            keyword_lower = keyword.lower()
            filtered_results = []
            for org in results:
                # Search in name, description, mission, ntee_description
                searchable_text = ' '.join([
                    str(org.get('name', '')),
                    str(org.get('description', '')),
                    str(org.get('mission', '')),
                    str(org.get('ntee_description', ''))
                ]).lower()
                
                if keyword_lower in searchable_text:
                    filtered_results.append(org)
            
            results = filtered_results
        
        return {
            "location": location,
            "keyword": keyword,
            "state": state_code,
            "ntee_code": ntee_code,
            "count": len(results),
            "nonprofits": results,
            "data_sources": {
                "propublica": "https://projects.propublica.org/nonprofits/api",
                "everyorg": "https://www.every.org/nonprofit-api",
                "irs_teos": "https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads"
            }
        }
        
    except Exception as e:
        logger.error(f"Nonprofit search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/nonprofits")
async def search_nonprofits_api(
    location: str = Query("Tuscaloosa, AL", description="City, State format"),
    keyword: Optional[str] = Query(None, description="Service keyword (e.g., 'dental', 'health')"),
    state: Optional[str] = Query(None, description="2-letter state code (e.g., 'AL')"),
    ntee_code: Optional[str] = Query(None, description="NTEE code (e.g., 'E' for health)"),
    source: Optional[str] = Query(None, description="Data source: 'propublica', 'everyorg', 'all'")
):
    """
    Search for nonprofits using free open data APIs (API-prefixed endpoint for frontend).
    
    This is a duplicate of /nonprofits with /api prefix for frontend routing.
    """
    return await search_nonprofits(location, keyword, state, ntee_code, source)


@app.get("/data/status")
async def get_data_ingestion_status():
    """
    Get status of reference data ingestions.
    
    Shows Census jurisdictions, NCES school districts, and nonprofit cache status.
    """
    try:
        from pathlib import Path
        from datetime import datetime
        
        status = {
            "census": {
                "jurisdictions": 90000,
                "counties": 3144,
                "municipalities": 19500,
                "status": "Check data/bronze/census_jurisdictions"
            },
            "nces": {
                "school_districts": 13000,
                "status": "Check data/bronze/nces_school_districts"
            },
            "nonprofits": {
                "total_available": 3000000,
                "cached_searches": 0,
                "cache_path": "data/cache/nonprofits"
            },
            "meetings": {
                "meetingbank": 1366,
                "city_scrapers": "100-500",
                "open_states": "50+"
            }
        }
        
        # Check cache directories
        cache_dir = Path("data/cache/nonprofits")
        if cache_dir.exists():
            cached_files = list(cache_dir.glob("*.json"))
            status["nonprofits"]["cached_searches"] = len(cached_files)
        
        return status
        
    except Exception as e:
        logger.error(f"Data status error: {e}")
        return {"error": str(e)}


@app.post("/data/ingest/nonprofits")
async def bulk_ingest_nonprofits(
    state: str = Query(..., description="State code (e.g., AL)"),
    ntee_code: Optional[str] = Query("E", description="NTEE code (default: E for Health)")
):
    """
    Bulk ingest nonprofit data for a state.
    
    Caches ProPublica API results for offline use.
    """
    try:
        from scripts.datasources.irs.nonprofit_discovery import NonprofitDiscovery
        
        discovery = NonprofitDiscovery()
        orgs = discovery.search_propublica(state=state, ntee_code=ntee_code)
        
        return {
            "message": f"Ingested {len(orgs)} nonprofits for {state}",
            "state": state,
            "ntee_code": ntee_code,
            "count": len(orgs),
            "cache_location": "data/cache/nonprofits"
        }
        
    except Exception as e:
        logger.error(f"Nonprofit ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/api/health")
async def api_health_check():
    """Health check endpoint for monitoring (API path)."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.post("/admin/initialize")
async def initialize_system():
    """Initialize Delta Lake tables and system components."""
    try:
        pipeline.initialize_tables()
        
        return {
            "status": "success",
            "message": "System initialized successfully"
        }
        
    except Exception as e:
        logger.error(f"Error initializing system: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Startup event
@app.post("/api/debate-grade")
async def grade_decision_with_debate_framework(
    document_id: Optional[str] = Query(None, description="Document ID to grade"),
    text: Optional[str] = Query(None, description="Text to grade directly"),
    title: Optional[str] = Query("", description="Document title")
):
    """
    Grade a government decision using debate framework (Harms/Solvency/Topicality).
    
    Translates debate concepts for laypeople:
    - Harms → "The Problem": Why is this a crisis?
    - Solvency → "The Fix": How does this solution work?
    - Topicality → "The Scope": Does the government have authority?
    
    Example: /api/debate-grade?text=The city council approved funding for dental screening...
    """
    try:
        from agents.debate_grader import DebateGraderAgent
        
        grader = DebateGraderAgent()
        
        # Get document content
        if document_id:
            document = pipeline.get_document_by_id(document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
        elif text:
            document = {
                "content": text,
                "title": title,
                "id": "custom_text"
            }
        else:
            raise HTTPException(status_code=400, detail="Provide either document_id or text")
        
        # Grade the document
        grade = await grader._grade_document(document)
        
        return {
            "document_id": document.get("id"),
            "title": document.get("title", ""),
            "debate_grade": grade,
            "explanation": {
                "harms": "This measures how well the decision identifies and documents the problem using data and evidence",
                "solvency": "This measures how clearly the solution is defined and whether it will actually fix the problem",
                "topicality": "This measures whether the government body has the legal authority to take this action"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debate grading error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/debate-grade/batch")
async def grade_decisions_batch(
    state: Optional[str] = Query(None, description="Filter by state"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    limit: int = Query(50, description="Number of documents to grade")
):
    """
    Grade multiple government decisions using debate framework.
    
    Returns aggregate insights about decision quality across dimensions.
    """
    try:
        from agents.debate_grader import DebateGraderAgent
        from agents.base import AgentMessage, MessageType, AgentRole
        
        grader = DebateGraderAgent()
        
        # Get documents to grade
        documents = pipeline.query_opportunities_by_state(state, None)
        
        if topic:
            documents = [d for d in documents if d.get("topic") == topic]
        
        documents = documents[:limit]
        
        # Create message and process
        message = AgentMessage(
            message_id=f"batch_grade_{datetime.utcnow().timestamp()}",
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.DEBATE_GRADER,
            message_type=MessageType.COMMAND,
            payload={"documents": documents}
        )
        
        result = await grader.process(message)
        graded_documents = result[0].payload.get("documents", [])
        insights = result[0].payload.get("insights", {})
        
        return {
            "graded_count": len(graded_documents),
            "documents": graded_documents,
            "insights": insights,
            "explanation": {
                "average_scores": "Average scores across all three debate dimensions (out of 5)",
                "strongest_dimension": "Which dimension governments perform best on",
                "weakest_dimension": "Which dimension needs the most improvement"
            }
        }
        
    except Exception as e:
        logger.error(f"Batch debate grading error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Initialize system on startup with data validation."""
    logger.info("="*80)
    logger.info("🚀 STARTING Open Navigator API")
    logger.info("="*80)
    logger.info(f"Configuration: {settings.catalog_name}.{settings.schema_name}")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info(f"Log File: {settings.log_file}")
    
    # Check if running on HuggingFace Spaces
    IS_HF_SPACES = os.getenv("HF_SPACES") == "1"
    if IS_HF_SPACES:
        logger.info(f"🤗 Running on HuggingFace Spaces")
    else:
        logger.info(f"💻 Running in local/standard environment")
    
    # Validate critical data files
    logger.info("")
    logger.info("📊 VALIDATING DATA AVAILABILITY...")
    logger.info("-" * 80)
    
    data_dir = Path("data/gold")
    critical_files = []
    optional_files = []
    
    # Check reference data (critical)
    reference_checks = [
        "reference/jurisdictions_cities.parquet",
        "reference/jurisdictions_counties.parquet",
        "reference/causes_ntee_codes.parquet",
    ]
    
    for file_pattern in reference_checks:
        file_path = data_dir / file_pattern
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            try:
                import pandas as pd
                df = pd.read_parquet(file_path)
                logger.info(f"  ✅ {file_pattern}: {len(df):,} records ({size_mb:.2f} MB)")
                critical_files.append(file_pattern)
            except Exception as e:
                logger.error(f"  ❌ {file_pattern}: ERROR - {e}")
        else:
            logger.warning(f"  ⚠️  {file_pattern}: NOT FOUND")
    
    # Check state data (optional - shows what's available)
    logger.info("")
    logger.info("📍 STATE DATA AVAILABILITY:")
    
    states_dir = data_dir / "states"
    if states_dir.exists():
        state_dirs = sorted([d for d in states_dir.iterdir() if d.is_dir()])
        states_with_data = []
        
        for state_dir in state_dirs[:10]:  # Show first 10 states
            state = state_dir.name
            files_found = []
            
            # Check for key files
            key_files = [
                "nonprofits_organizations.parquet",
                "contact_official.parquet",
                "events.parquet",
            ]
            
            for filename in key_files:
                file_path = state_dir / filename
                if file_path.exists():
                    files_found.append(filename.split('.')[0].split('_')[-1])
            
            if files_found:
                logger.info(f"  ✅ {state}: {', '.join(files_found)}")
                states_with_data.append(state)
        
        total_states = len(state_dirs)
        if total_states > 10:
            logger.info(f"  ... and {total_states - 10} more states")
        
        logger.info(f"")
        logger.info(f"  📊 Total states with data: {total_states}")
    else:
        logger.warning("  ⚠️  No state data directory found")
    
    # Validate HuggingFace datasets if running on HF Spaces
    if IS_HF_SPACES:
        logger.info("")
        logger.info("🤗 VALIDATING HUGGINGFACE DATASETS...")
        logger.info("-" * 80)
        
        # Check a sample of critical datasets (using new consolidated datasets)
        import requests
        
        test_datasets = [
            ("https://huggingface.co/datasets/CommunityOne/one-bills/resolve/main/data/train-00000-of-00001.parquet", "Bills (Consolidated)"),
            ("https://huggingface.co/datasets/CommunityOne/one-local-officials/resolve/main/data/train-00000-of-00001.parquet", "Local Officials (Consolidated)"),
            ("https://huggingface.co/datasets/CommunityOne/one-nonprofits-organizations/resolve/main/data/train-00000-of-00001.parquet", "Nonprofits (Consolidated)"),
        ]
        
        hf_datasets_ok = 0
        for url, display_name in test_datasets:
            try:
                response = requests.head(url, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    logger.info(f"  ✅ {display_name}: Accessible")
                    hf_datasets_ok += 1
                else:
                    logger.error(f"  ❌ {display_name}: HTTP {response.status_code}")
                    logger.error(f"     URL: {url}")
            except Exception as e:
                logger.error(f"  ❌ {display_name}: {type(e).__name__} - {e}")
                logger.error(f"     URL: {url}")
        
        logger.info("")
        logger.info(f"  📊 HuggingFace datasets validated: {hf_datasets_ok}/{len(test_datasets)}")
        
        if hf_datasets_ok < len(test_datasets):
            logger.warning("  ⚠️  Some datasets are not accessible - API may have limited functionality")
    
    logger.info("")
    logger.info("="*80)
    logger.info(f"✅ API READY - {len(critical_files)}/{len(reference_checks)} critical files available")
    if IS_HF_SPACES:
        logger.info(f"✅ HuggingFace datasets validated")
    logger.info("="*80)
    logger.info("")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Oral Health Policy Pulse API")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers
    )
