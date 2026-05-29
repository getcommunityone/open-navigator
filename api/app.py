"""
FastAPI application optimized for Databricks Apps deployment.
Serves React frontend and provides REST API for agent interactions.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger
import os

from agents.orchestrator import OrchestratorAgent
from pipeline.delta_lake import DeltaLakePipeline
from config import settings

# Initialize FastAPI app
app = FastAPI(
    title="Open Navigator",
    description="AI-powered advocacy opportunity finder",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
orchestrator = OrchestratorAgent()
pipeline = DeltaLakePipeline()

# Pydantic models
class WorkflowRequest(BaseModel):
    """Request to start a new analysis workflow."""
    targets: List[Dict[str, str]]
    topics: Optional[List[str]] = None

class OpportunityFilter(BaseModel):
    """Filter criteria for advocacy opportunities."""
    state: Optional[str] = None
    topic: Optional[str] = None
    urgency: Optional[str] = None
    min_confidence: Optional[float] = 0.7


# API Routes
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/dashboard")
async def get_dashboard_stats():
    """Get dashboard statistics and recent opportunities."""
    try:
        # Query Delta Lake for stats
        stats = await pipeline.get_dashboard_stats()
        return stats
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/opportunities")
async def get_opportunities(
    state: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    limit: int = Query(100, le=1000)
):
    """Get advocacy opportunities with optional filters."""
    try:
        opportunities = await pipeline.query_opportunities(
            state=state,
            topic=topic,
            urgency=urgency,
            limit=limit
        )
        return {"opportunities": opportunities, "count": len(opportunities)}
    except Exception as e:
        logger.error(f"Query opportunities error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents")
async def get_documents(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100)
):
    """Get analyzed documents with pagination."""
    try:
        offset = (page - 1) * limit
        documents = await pipeline.query_documents(
            search=search,
            limit=limit,
            offset=offset
        )
        total = await pipeline.count_documents(search=search)
        return {
            "documents": documents,
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    except Exception as e:
        logger.error(f"Query documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/")
async def search_all(
    q: str = Query(..., min_length=1, description="Search query"),
    types: Optional[str] = Query("contacts,organizations,causes", description="Comma-separated types to search"),
    state: Optional[str] = Query(None, description="Filter by state code (e.g. MA, AL)"),
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    ntee_code: Optional[str] = Query(None, description="NTEE category code")
):
    """
    Unified search across contacts, organizations, causes, and jurisdictions.
    Returns results grouped by type with pagination.
    """
    try:
        offset = (page - 1) * limit
        search_types = [t.strip() for t in types.split(',') if t.strip()]
        
        # Initialize results structure
        results = {
            "contacts": [],
            "organizations": [],
            "causes": [],
            "meetings": [],
            "jurisdictions": []
        }
        
        # Search logic (placeholder - implement actual search)
        # For now, return mock results for demonstration
        if "contacts" in search_types:
            results["contacts"] = [
                {
                    "type": "contact",
                    "title": f"Sample Contact matching '{q}'",
                    "subtitle": "Government Official",
                    "description": "Contact information for local official",
                    "url": "/contact/1",
                    "score": 0.9,
                    "metadata": {"state": state or "MA"}
                }
            ]
        
        if "organizations" in search_types:
            results["organizations"] = [
                {
                    "type": "organization",
                    "title": f"Sample Organization matching '{q}'",
                    "subtitle": "Nonprofit Organization",
                    "description": "Community health organization",
                    "url": "/org/1",
                    "score": 0.85,
                    "metadata": {"state": state or "MA", "ntee": ntee_code}
                }
            ]
        
        if "causes" in search_types:
            results["causes"] = [
                {
                    "type": "cause",
                    "title": f"Sample Cause matching '{q}'",
                    "subtitle": "Health & Wellness",
                    "description": "Advocacy for community health",
                    "url": "/cause/1",
                    "score": 0.8,
                    "metadata": {}
                }
            ]
        
        # Calculate total results
        total_results = sum(len(v) for v in results.values())
        total_pages = max(1, (total_results + limit - 1) // limit)
        
        return {
            "query": q,
            "total_results": total_results,
            "results": results,
            "pagination": {
                "page": page,
                "limit": limit,
                "offset": offset,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "filters": {
                "state": state,
                "ntee_code": ntee_code,
                "types": search_types
            }
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflow/start")
async def start_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
    """Start a new analysis workflow."""
    try:
        workflow_id = f"workflow_{datetime.utcnow().timestamp()}"
        
        # Start workflow in background
        background_tasks.add_task(
            orchestrator.execute_pipeline,
            workflow_id=workflow_id,
            targets=request.targets,
            topics=request.topics
        )
        
        return {
            "workflow_id": workflow_id,
            "status": "started",
            "message": "Workflow started successfully"
        }
    except Exception as e:
        logger.error(f"Workflow start error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """Get status of a running workflow."""
    try:
        status = await orchestrator.get_workflow_status(workflow_id)
        return status
    except Exception as e:
        logger.error(f"Workflow status error: {e}")
        raise HTTPException(status_code=404, detail="Workflow not found")


@app.post("/api/advocacy/email/{opportunity_id}")
async def generate_advocacy_email(opportunity_id: str):
    """Generate advocacy email for an opportunity."""
    try:
        opportunity = await pipeline.get_opportunity(opportunity_id)
        if not opportunity:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        email_content = await orchestrator.generate_advocacy_email(opportunity)
        return {"content": email_content}
    except Exception as e:
        logger.error(f"Generate email error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings")
async def get_settings():
    """Get current system settings."""
    return {
        "target_states": settings.target_states or [],
        "policy_topics": settings.policy_topics,
        "min_confidence": 0.7,
        "email_notifications": False,
        "notification_email": ""
    }


@app.put("/api/settings")
async def update_settings(new_settings: Dict[str, Any]):
    """Update system settings."""
    try:
        # In production, this would update configuration in Unity Catalog
        logger.info(f"Settings update requested: {new_settings}")
        return {"message": "Settings updated successfully"}
    except Exception as e:
        logger.error(f"Settings update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/status")
async def get_agents_status():
    """Get status of all agents."""
    try:
        return {
            "agents": [
                {"name": "Scraper", "status": "active", "uptime": "24h"},
                {"name": "Classifier", "status": "active", "uptime": "24h"},
                {"name": "Sentiment Analyzer", "status": "active", "uptime": "24h"},
                {"name": "Advocacy Writer", "status": "active", "uptime": "24h"}
            ]
        }
    except Exception as e:
        logger.error(f"Agent status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/nonprofits")
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
    
    Example: /api/nonprofits?location=Tuscaloosa,AL&keyword=dental&ntee_code=E
    """
    try:
        from scrapers.irs.nonprofit_discovery import NonprofitDiscovery
        
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


@app.get("/api/data/status")
async def get_data_status():
    """
    Get status of all reference data ingestions.
    
    Returns counts and last update times for:
    - Census jurisdictions
    - NCES school districts
    - Nonprofit organizations
    - Meeting datasets (MeetingBank, LocalView, etc.)
    """
    try:
        from pathlib import Path
        from datetime import datetime
        
        status = {
            "census_jurisdictions": {
                "path": "data/bronze/census_jurisdictions",
                "status": "not_ingested",
                "count": 0,
                "last_updated": None
            },
            "nces_school_districts": {
                "path": "data/bronze/nces_school_districts",
                "status": "not_ingested",
                "count": 0,
                "last_updated": None
            },
            "nonprofits": {
                "path": "data/cache/nonprofits",
                "status": "cached",
                "count": 0,
                "last_updated": None
            },
            "meeting_datasets": {
                "meetingbank": {"status": "available", "count": 1366},
                "city_scrapers": {"status": "available", "count": "100-500"},
                "open_states": {"status": "available", "count": "50+"}
            }
        }
        
        # Check each data directory
        for key in ["census_jurisdictions", "nces_school_districts", "nonprofits"]:
            data_path = Path(status[key]["path"])
            if data_path.exists():
                files = list(data_path.glob("**/*"))
                status[key]["count"] = len(files)
                status[key]["status"] = "ingested" if files else "empty"
                if files:
                    latest_file = max(files, key=lambda f: f.stat().st_mtime if f.is_file() else 0)
                    if latest_file.is_file():
                        status[key]["last_updated"] = datetime.fromtimestamp(
                            latest_file.stat().st_mtime
                        ).isoformat()
        
        return status
        
    except Exception as e:
        logger.error(f"Data status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data/ingest/census")
async def ingest_census_data(background_tasks: BackgroundTasks):
    """
    Trigger Census Bureau jurisdiction data ingestion.
    
    Downloads and processes:
    - 3,144 counties
    - 19,500+ municipalities  
    - 36,000+ townships
    - 13,000+ school districts
    
    This is a long-running operation that runs in the background.
    """
    try:
        def run_census_ingestion():
            from scripts.discovery.census_ingestion import CensusGovernmentIngestion
            import asyncio
            
            logger.info("Starting Census data ingestion...")
            ingestor = CensusGovernmentIngestion()
            
            # Run async ingestion
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(ingestor.ingest_all_jurisdictions())
            loop.close()
            
            logger.success(f"Census ingestion complete: {result}")
        
        background_tasks.add_task(run_census_ingestion)
        
        return {
            "message": "Census data ingestion started",
            "status": "processing",
            "check_status": "/api/data/status"
        }
        
    except Exception as e:
        logger.error(f"Census ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data/ingest/nces")
async def ingest_nces_data(background_tasks: BackgroundTasks):
    """
    Trigger NCES school district data ingestion.
    
    Downloads and processes 13,000+ school districts with:
    - District names and addresses
    - Contact information
    - NCES IDs
    - Enrollment data
    """
    try:
        def run_nces_ingestion():
            from scripts.discovery.nces_ingestion import NCESSchoolDistrictIngestion
            import asyncio
            
            logger.info("Starting NCES data ingestion...")
            ingestor = NCESSchoolDistrictIngestion()
            
            # Run async ingestion
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(ingestor.download_and_process())
            loop.close()
            
            logger.success(f"NCES ingestion complete: {result}")
        
        background_tasks.add_task(run_nces_ingestion)
        
        return {
            "message": "NCES data ingestion started",
            "status": "processing",
            "check_status": "/api/data/status"
        }
        
    except Exception as e:
        logger.error(f"NCES ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data/ingest/nonprofits")
async def ingest_nonprofits(
    state: str = Query(..., description="2-letter state code"),
    ntee_codes: Optional[List[str]] = Query(None, description="NTEE codes to ingest"),
    background_tasks: BackgroundTasks = None
):
    """
    Trigger nonprofit data ingestion for a specific state.
    
    Bulk downloads nonprofit data from ProPublica API and caches locally.
    
    Example: POST /api/data/ingest/nonprofits?state=AL&ntee_codes=E&ntee_codes=E20
    """
    try:
        from scrapers.irs.nonprofit_discovery import NonprofitDiscovery
        
        discovery = NonprofitDiscovery()
        ntee_list = ntee_codes or ["E"]  # Default to health
        
        total_orgs = 0
        for ntee_code in ntee_list:
            orgs = discovery.search_propublica(state=state, ntee_code=ntee_code)
            total_orgs += len(orgs)
            logger.info(f"Cached {len(orgs)} nonprofits for {state}/{ntee_code}")
        
        return {
            "message": f"Nonprofit data ingestion complete for {state}",
            "state": state,
            "ntee_codes": ntee_list,
            "organizations_cached": total_orgs,
            "cache_location": "data/cache/nonprofits"
        }
        
    except Exception as e:
        logger.error(f"Nonprofit ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jurisdictions")
async def get_jurisdictions(
    state: Optional[str] = Query(None, description="2-letter state code"),
    type: Optional[str] = Query(None, description="Type: county, municipality, township"),
    limit: int = Query(100, le=1000)
):
    """
    Query ingested Census jurisdiction data.
    
    Returns government entities with FIPS codes, coordinates, and population.
    """
    try:
        # This would query the Delta Lake census tables
        # For now, return sample data
        return {
            "message": "Query census jurisdiction data from Delta Lake",
            "filters": {"state": state, "type": type},
            "limit": limit,
            "note": "Requires Census data ingestion first (POST /api/data/ingest/census)",
            "example_data": [
                {
                    "name": "Tuscaloosa County",
                    "state": "AL",
                    "type": "county",
                    "fips": "01125",
                    "population": "209355"
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"Jurisdiction query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/school-districts")
async def get_school_districts(
    state: Optional[str] = Query(None, description="2-letter state code"),
    limit: int = Query(100, le=1000)
):
    """
    Query ingested NCES school district data.
    
    Returns school districts with contact information and enrollment.
    """
    try:
        # This would query the Delta Lake NCES tables
        return {
            "message": "Query NCES school district data from Delta Lake",
            "filters": {"state": state},
            "limit": limit,
            "note": "Requires NCES data ingestion first (POST /api/data/ingest/nces)",
            "example_data": [
                {
                    "name": "Tuscaloosa City Schools",
                    "state": "AL",
                    "nces_id": "0100123",
                    "phone": "(205) 759-3500",
                    "website": "https://www.tusc.k12.al.us/"
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"School district query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Batch job dashboard (caption/analyze pipelines)
from api.routes import batch_jobs as batch_jobs_routes

app.include_router(batch_jobs_routes.router, prefix="/api")

# Serve React frontend
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    # Mount static files (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    # Public /data tree, served the same paths as Vite dev. Covers the ACS
    # map/scorecard marts (/data/census-map), the per-state ZCTA (ZIP) tiles
    # (/data/zctas — the lowest drilldown tier), and the jurisdiction-quality
    # snapshot. Mounting only /data/census-map left the others 404ing.
    frontend_public = Path(__file__).parent.parent / "frontend" / "public"
    data_dir = frontend_public / "data"
    if data_dir.is_dir():
        app.mount("/data", StaticFiles(directory=data_dir), name="public_data")
    else:
        logger.warning(f"Public data bundle missing (expected {data_dir})")

    # Serve index.html for all non-API routes (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """Serve React app for all non-API routes."""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")


@app.on_event("startup")
async def startup_event():
    """Initialize system on startup."""
    logger.info("Starting CommunityOne Open Navigatory application...")
    
    # Initialize Delta Lake if not exists
    try:
        await pipeline.initialize_tables()
        logger.info("Delta Lake tables initialized")
    except Exception as e:
        logger.warning(f"Delta Lake initialization skipped: {e}")
    
    logger.info("Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down application...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
