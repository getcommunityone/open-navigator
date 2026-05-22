"""
Statistics endpoint using Neon Postgres (fast!)
Replaces parquet file scanning with indexed database queries
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from loguru import logger
import os
import asyncpg
from datetime import datetime, timedelta

router = APIRouter()

# Cache for stats (TTL: 5 minutes - data in Neon changes infrequently)
STATS_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION = timedelta(minutes=5)

# Get database URL from environment
# Priority: OPEN_NAVIGATOR_DATABASE_URL > NEON_DATABASE_URL_DEV > NEON_DATABASE_URL > DATABASE_URL
NEON_DATABASE_URL_DEV = os.getenv('NEON_DATABASE_URL_DEV')
NEON_DATABASE_URL = os.getenv('NEON_DATABASE_URL')
OPEN_NAVIGATOR_DATABASE_URL = os.getenv('OPEN_NAVIGATOR_DATABASE_URL')
GENERIC_DATABASE_URL = os.getenv('DATABASE_URL')

DATABASE_URL = (
    (OPEN_NAVIGATOR_DATABASE_URL or '').strip()
    or (NEON_DATABASE_URL_DEV or '').strip()
    or (NEON_DATABASE_URL or '').strip()
    or (GENERIC_DATABASE_URL or '').strip()
    or None
)

# Connection pool (created on first request)
_db_pool = None

# Cached per-table column sets (public schema) — invalid when pool resets
_table_columns: Dict[str, frozenset] = {}


def _reset_schema_cache() -> None:
    global _table_columns
    _table_columns = {}


async def _get_table_columns(conn, table: str) -> frozenset:
    """Columns for `table` in public schema (lowercase names)."""
    if table not in _table_columns:
        rows = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            """,
            table,
        )
        _table_columns[table] = frozenset(r["column_name"] for r in rows)
    return _table_columns[table]


def _state_usps_match_sql(columns: frozenset, param: str = "$1") -> str:
    """
    SQL boolean expression: row matches USPS state from API (2-letter in param).

    Supports:
    - dbt / schema.sql: state_code set, state often NULL
    - legacy migrate / calculate_stats_only: only `state` with 2-letter value
    - both columns present: match either code or 2-char state field
    """
    has_sc = "state_code" in columns
    has_st = "state" in columns
    if has_sc and has_st:
        return (
            f"(UPPER(TRIM(COALESCE(state_code::text, ''))) = UPPER(TRIM({param}::text)) "
            f"OR (state IS NOT NULL AND LENGTH(TRIM(state::text)) = 2 "
            f"AND UPPER(TRIM(state::text)) = UPPER(TRIM({param}::text)))"
            f")"
        )
    if has_sc:
        return f"UPPER(TRIM(COALESCE(state_code::text, ''))) = UPPER(TRIM({param}::text))"
    if has_st:
        return f"UPPER(TRIM(COALESCE(state::text, ''))) = UPPER(TRIM({param}::text))"
    raise ValueError(f"Table has neither state_code nor state among columns: {columns}")


async def get_db_pool():
    """Get or create database connection pool"""
    global _db_pool
    if _db_pool is None:
        if not DATABASE_URL:
            raise ValueError(
                "DATABASE_URL not configured (set OPEN_NAVIGATOR_DATABASE_URL, NEON_DATABASE_URL_DEV, "
                "NEON_DATABASE_URL, or DATABASE_URL)"
            )

        if OPEN_NAVIGATOR_DATABASE_URL and DATABASE_URL == OPEN_NAVIGATOR_DATABASE_URL.strip():
            db_type = "OPEN_NAVIGATOR_DATABASE_URL"
        elif NEON_DATABASE_URL_DEV and DATABASE_URL == NEON_DATABASE_URL_DEV.strip():
            db_type = "Development (NEON_DATABASE_URL_DEV)"
        else:
            db_type = "Production/Neon (NEON_DATABASE_URL or DATABASE_URL)"
        logger.info(f"🗄️  [Stats] Connecting to {db_type}: {DATABASE_URL[:50]}...")
        
        _reset_schema_cache()
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _db_pool


@router.get("/stats")
async def get_stats(
    state: Optional[str] = Query(None, description="Two-letter state code (e.g., MA)"),
    county: Optional[str] = Query(None, description="County name (e.g., Suffolk County)"),
    city: Optional[str] = Query(None, description="City name (e.g., Boston)")
):
    """
    Get statistics from Neon Postgres database
    
    **Performance**: ~10-50ms (vs 3-10 seconds with parquet files)
    
    - **National**: GET /api/stats
    - **State**: GET /api/stats?state=MA
    - **County**: GET /api/stats?state=MA&county=Suffolk%20County
    - **City**: GET /api/stats?state=MA&city=Boston
    
    Returns comprehensive statistics including:
    - Jurisdiction counts (cities, counties, school districts)
    - Nonprofit counts and financials
    - Event/meeting counts
    - Contact/officer counts
    """
    
    try:
        # Determine cache key and query parameters
        if city and state:
            cache_key = f"city:{state}:{city}"
            level = 'city'
            location_display = f"{city}, {state}"
        elif county and state:
            cache_key = f"county:{state}:{county}"
            level = 'county'
            location_display = f"{county}, {state}"
        elif state:
            cache_key = f"state:{state}"
            level = 'state'
            location_display = state
        else:
            cache_key = "national"
            level = 'national'
            location_display = 'United States'
        
        # Check cache
        if cache_key in STATS_CACHE:
            cached = STATS_CACHE[cache_key]
            if datetime.now() - cached['timestamp'] < CACHE_DURATION:
                logger.debug(f"🚀 Cache hit for {cache_key}")
                return cached['stats']
        
        # Query Neon database
        logger.info(f"📊 Fetching stats from Neon: {cache_key}")
        stats = await fetch_stats_from_neon(level, state, county, city)
        
        if not stats:
            # No data found - return empty stats
            stats = {
                'location': location_display,
                'level': level,
                'state': state,
                'county': county,
                'city': city,
                'jurisdictions': 0,
                'school_districts': 0,
                'nonprofits': 0,
                'events': 0,
                'bills': 0,
                'contacts': 0,
                'decisions': 0,
                'total_revenue': 0,
                'total_assets': 0,
                'last_updated': None,
                'source': 'neon',
                'note': 'No data available for this location'
            }
        else:
            # Format response
            stats = {
                'location': location_display,
                'level': level,
                'state': state,
                'county': county,
                'city': city,
                'jurisdictions': stats.get('jurisdictions_count', 0),
                'school_districts': stats.get('school_districts_count', 0),
                'nonprofits': stats.get('nonprofits_count', 0),
                'events': stats.get('events_count', 0),
                'bills': stats.get('bills_count', 0),
                'contacts': stats.get('contacts_count', 0),
                'decisions': stats.get('decisions_count', 0),
                'total_revenue': stats.get('total_revenue', 0),
                'total_assets': stats.get('total_assets', 0),
                'trending_causes': stats.get('trending_causes'),  # Include trending causes from dbt
                'last_updated': stats.get('last_updated'),
                'source': 'neon'
            }
        
        # Cache result
        STATS_CACHE[cache_key] = {
            'stats': stats,
            'timestamp': datetime.now()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


async def fetch_stats_from_neon(
    level: str,
    state: Optional[str] = None,
    county: Optional[str] = None,
    city: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch statistics from Neon database
    
    Args:
        level: 'national', 'state', 'county', or 'city'
        state: State code (if applicable)
        county: County name (if applicable)
        city: City name (if applicable)
    
    Returns:
        Dictionary with stats or None if not found
    """
    try:
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            stats_cols = await _get_table_columns(conn, "jurisdiction_state_aggregate")
            state_pred_stats = _state_usps_match_sql(stats_cols, "$1")
            state_val = state.upper() if state and len(state) == 2 else state

            # Build query based on level
            if level == 'national':
                query = """
                    SELECT * FROM jurisdiction_state_aggregate 
                    WHERE level = 'national'
                    LIMIT 1
                """
                result = await conn.fetchrow(query)
                
            elif level == 'state':
                query = f"""
                    SELECT * FROM jurisdiction_state_aggregate 
                    WHERE level = 'state' AND ({state_pred_stats})
                    LIMIT 1
                """
                result = await conn.fetchrow(query, state_val)
                
            elif level == 'county':
                # Try county-level stats first
                # Normalize county name (remove 'County' suffix)
                county_name = county.replace(' County', '').strip() if county else county
                query = f"""
                    SELECT * FROM jurisdiction_state_aggregate 
                    WHERE level = 'county' 
                      AND ({state_pred_stats})
                      AND county ILIKE $2
                    LIMIT 1
                """
                result = await conn.fetchrow(query, state_val, f"%{county_name}%")
                
                # Fall back to state-level if county not found
                if not result and state:
                    logger.info(f"County '{county}' not found in stats, falling back to state '{state}'")
                    query = f"""
                        SELECT * FROM jurisdiction_state_aggregate 
                        WHERE level = 'state' AND ({state_pred_stats})
                        LIMIT 1
                    """
                    result = await conn.fetchrow(query, state_val)
                
            elif level == 'city':
                # Try city-level stats first from jurisdiction_state_aggregate
                query = f"""
                    SELECT * FROM jurisdiction_state_aggregate 
                    WHERE level = 'city' 
                      AND ({state_pred_stats})
                      AND city ILIKE $2
                    LIMIT 1
                """
                result = await conn.fetchrow(query, state_val, f"%{city}%")
                
                # If not in jurisdiction_state_aggregate, query jurisdiction directly
                if not result:
                    logger.info(f"City '{city}' not in jurisdiction_state_aggregate, querying jurisdiction directly")
                    
                    jur_cols = await _get_table_columns(conn, "jurisdiction")
                    jur_state_pred = _state_usps_match_sql(jur_cols, "$1")
                    
                    # Count jurisdictions for this city
                    jurisdiction_query = f"""
                        SELECT COUNT(DISTINCT id) as count
                        FROM jurisdiction
                        WHERE ({jur_state_pred})
                          AND name ILIKE $2
                    """
                    jur_result = await conn.fetchrow(
                        jurisdiction_query,
                        state_val,
                        f"%{city}%",
                    )
                    jurisdictions = jur_result['count'] if jur_result else 0
                    
                    # Count school districts
                    school_query = f"""
                        SELECT COUNT(*) as count
                        FROM jurisdiction
                        WHERE type = 'school_district'
                          AND ({jur_state_pred})
                          AND name ILIKE $2
                    """
                    school_result = await conn.fetchrow(
                        school_query,
                        state_val,
                        f"%{city}%",
                    )
                    school_districts = school_result['count'] if school_result else 0
                    
                    # Count contacts
                    contact_cols = await _get_table_columns(conn, "contact")
                    contact_state_pred = _state_usps_match_sql(contact_cols, "$1")
                    contact_query = f"""
                        SELECT COUNT(*) as count
                        FROM contact
                        WHERE ({contact_state_pred})
                    """
                    contact_result = await conn.fetchrow(contact_query, state_val)
                    contacts = contact_result['count'] if contact_result else 0
                    
                    # Return constructed stats
                    if jurisdictions > 0 or contacts > 0:
                        return {
                            'level': 'city',
                            'state': state,
                            'county': None,
                            'city': city,
                            'jurisdictions_count': jurisdictions,
                            'school_districts_count': school_districts,
                            'nonprofits_count': 0,
                            'events_count': 0,
                            'bills_count': 0,
                            'contacts_count': contacts,
                            'total_revenue': 0,
                            'total_assets': 0,
                            'last_updated': datetime.now(),
                            'source': 'database'  # Queried from database tables
                        }
                
                # Still no data? Fall back to state-level
                if not result and state:
                    logger.info(f"City '{city}' not found in database, falling back to state '{state}'")
                    query = f"""
                        SELECT * FROM jurisdiction_state_aggregate 
                        WHERE level = 'state' AND ({state_pred_stats})
                        LIMIT 1
                    """
                    result = await conn.fetchrow(query, state_val)
            
            else:
                return None
            
            if result:
                # Parse JSONB fields if they exist
                result_dict = dict(result)
                if result_dict.get('trending_causes') and isinstance(result_dict['trending_causes'], str):
                    import json
                    result_dict['trending_causes'] = json.loads(result_dict['trending_causes'])
                return result_dict
            return None
            
    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise


@router.get("/stats/search")
async def search_stats(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Max results")
):
    """
    Search for locations (cities, counties, states) with statistics
    
    Example: GET /api/stats/search?query=boston&limit=5
    
    Returns matching locations with their statistics
    """
    try:
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            # Search across all geographic levels
            results = await conn.fetch("""
                SELECT 
                    level,
                    state,
                    county,
                    city,
                    jurisdictions_count,
                    nonprofits_count,
                    events_count,
                    total_revenue
                FROM jurisdiction_state_aggregate
                WHERE 
                    (city ILIKE $1 OR county ILIKE $1 OR state ILIKE $1)
                    AND level != 'national'
                ORDER BY 
                    CASE level
                        WHEN 'city' THEN 1
                        WHEN 'county' THEN 2
                        WHEN 'state' THEN 3
                    END,
                    nonprofits_count DESC
                LIMIT $2
            """, f"%{query}%", limit)
            
            return [{
                'level': row['level'],
                'location': format_location(row),
                'state': row['state'],
                'county': row['county'],
                'city': row['city'],
                'jurisdictions': row['jurisdictions_count'],
                'nonprofits': row['nonprofits_count'],
                'events': row['events_count'],
                'total_revenue': row['total_revenue']
            } for row in results]
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def format_location(row) -> str:
    """Format location string from database row"""
    if row['city']:
        if row['county']:
            return f"{row['city']}, {row['county']}, {row['state']}"
        return f"{row['city']}, {row['state']}"
    elif row['county']:
        return f"{row['county']}, {row['state']}"
    elif row['state']:
        return row['state']
    return 'Unknown'


@router.on_event("shutdown")
async def shutdown_db_pool():
    """Close database connection pool on shutdown"""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
    _reset_schema_cache()
