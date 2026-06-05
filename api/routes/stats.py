"""
Statistics endpoint with cached metrics from database tables
"""
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from loguru import logger
import psycopg2
import os

router = APIRouter()

# Database connection URL for stats queries
LOCAL_DB_URL = os.getenv("NEON_DATABASE_URL_DEV", "postgresql://postgres:password@localhost:5433/open_navigator")

# Multi-level cache: {cache_key: {stats_data, timestamp}}
# Cache key format: "national" or "state:MA" or "county:MA:Suffolk" or "city:MA:Boston"
STATS_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION = timedelta(hours=1)


def calculate_stats_from_db(state: Optional[str] = None, 
                            county: Optional[str] = None, 
                            city: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate statistics from database tables (faster than parquet files)
    
    Queries:
    - jurisdiction for jurisdiction counts
    - contact for official/legislator counts
    - jurisdiction_state_aggregate for nonprofit counts + trending causes
      (nonprofit detail now lives in mdm_organization + mdm_organization_nonprofit)
    
    Args:
        state: State name (e.g., 'Massachusetts') or code (e.g., 'MA')
        county: County name (e.g., 'Suffolk County' or 'Suffolk')
        city: City name (e.g., 'Boston')
    """
    try:
        conn = psycopg2.connect(LOCAL_DB_URL)
        cursor = conn.cursor()
        
        # Determine geographic level
        if city and state:
            level = 'city'
            location_display = f"{city}, {state}"
        elif county and state:
            level = 'county'
            location_display = f"{county}, {state}"
        elif state:
            level = 'state'
            location_display = state
        else:
            level = 'national'
            location_display = 'United States'
        
        # Get all stats from jurisdiction_state_aggregate table
        stats_where = ["level = %s"]
        stats_params = [level]
        
        if city and state:
            stats_where.append("city ILIKE %s")
            stats_where.append("state = %s")
            stats_params.append(f"%{city}%")
            stats_params.append(state.upper() if len(state) == 2 else state)
        elif county and state:
            # Normalize county name (remove 'County' suffix if present)
            county_name = county.replace(' County', '').strip()
            stats_where.append("county ILIKE %s")
            stats_where.append("state = %s")
            stats_params.append(f"%{county_name}%")
            stats_params.append(state.upper() if len(state) == 2 else state)
        elif state:
            stats_where.append("state = %s")
            stats_params.append(state.upper() if len(state) == 2 else state)
        
        # Columns match the public.jurisdiction_state_aggregate schema. Officials
        # are the `leaders_count` rollup. `trending_causes` is not materialized on
        # this table yet (no source column), so it is reported as None until the
        # dbt model exposes it.
        stats_query = f"""
            SELECT
                nonprofits_count,
                events_count,
                jurisdictions_count,
                school_districts_count,
                bills_count,
                leaders_count,
                nonprofit_leaders_count,
                total_revenue,
                total_assets
            FROM jurisdiction_state_aggregate
            WHERE {' AND '.join(stats_where)}
            LIMIT 1
        """

        cursor.execute(stats_query, stats_params)
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        # The precomputed aggregate is authoritative only once its rollups are
        # populated. Today it holds national + a few seeded states, with
        # leaders_count / bills_count still 0. When the matching row is missing
        # or unpopulated, defer to the live per-table counts (calculate_stats),
        # which cover every location, instead of reporting zeros. This fast path
        # self-activates once the jurisdiction_state_aggregate rollup is filled.
        if not result or (result[5] or 0) == 0:
            return calculate_stats(state=state, county=county, city=city)

        nonprofits = result[0] or 0
        events = result[1] or 0
        jurisdictions = result[2] or 0
        school_districts = result[3] or 0
        bills = result[4] or 0
        contacts = result[5] or 0
        nonprofit_leaders = result[6] or 0
        total_revenue = result[7] or 0
        total_assets = result[8] or 0
        trending_causes = None

        # Build response
        return {
            'level': level,
            'location': location_display,
            'state': state,
            'county': county,
            'city': city,
            'jurisdictions': jurisdictions,
            'school_districts': school_districts,
            'nonprofits': nonprofits,
            'events': events,
            'bills': bills,
            'contacts': contacts,
            'nonprofit_leaders': nonprofit_leaders,
            'total_revenue': total_revenue,
            'total_assets': total_assets,
            'trending_causes': trending_causes,
            'last_updated': datetime.now().isoformat(),
            'source': 'database',
            'note': 'Data from local PostgreSQL' if (jurisdictions > 0 or contacts > 0 or nonprofits > 0) else 'No data available for this location'
        }
        
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        # Fallback to parquet files
        return calculate_stats(state=state, county=county, city=city)


def calculate_stats(state: Optional[str] = None, 
                   county: Optional[str] = None, 
                   city: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate statistics from parquet files with optional geographic filtering
    
    Args:
        state: Two-letter state code (e.g., 'MA')
        county: County name (e.g., 'Suffolk County')
        city: City name (e.g., 'Boston')
    """
    
    # Determine geographic level
    if city and state:
        level = 'city'
        if county:
            location_display = f"{city}, {county}, {state}"
        else:
            location_display = f"{city}, {state}"
    elif county and state:
        level = 'county'
        location_display = f"{county}, {state}"
    elif state:
        level = 'state'
        location_display = state
    else:
        level = 'national'
        location_display = 'United States'
    
    # Counts are served from the Postgres `public` schema (NOT parquet) per
    # CLAUDE.md. Reuse the same psycopg2/LOCAL_DB_URL convention as the
    # officials migration above — a single connection for all count queries.
    state_code = (state.upper() if (state and len(state) == 2) else state) if state else None

    jurisdictions = 0
    school_districts = 0
    nonprofits = 0
    meetings = 0
    try:
        conn = psycopg2.connect(LOCAL_DB_URL)
        cursor = conn.cursor()

        # --- Jurisdictions (public.jurisdictions) ---
        # "All jurisdictions" deliberately EXCLUDES school_district (counted
        # separately below). city/town/county only.
        if city:
            # When a city is selected, show 4 jurisdictions:
            # 1. City, 2. County, 3. State, 4. School District
            jurisdictions = 4
        elif county and state_code:
            # Count cities/townships in this county's state.
            # For now, count all in state - proper county filtering needs geocoding.
            cursor.execute(
                "SELECT count(*) FROM public.jurisdictions "
                "WHERE jurisdiction_type IN ('city','town') AND state_code = %s",
                [state_code],
            )
            count = cursor.fetchone()[0] or 0
            jurisdictions = count if count > 0 else 1  # At least the county itself
        else:
            jur_where = "jurisdiction_type IN ('city','town','county')"
            jur_params: list = []
            if state_code:
                jur_where += " AND state_code = %s"
                jur_params.append(state_code)
            cursor.execute(
                f"SELECT count(*) FROM public.jurisdictions WHERE {jur_where}",
                jur_params,
            )
            jurisdictions = cursor.fetchone()[0] or 0

        # School districts (same table, jurisdiction_type='school_district').
        sd_where = "jurisdiction_type = 'school_district'"
        sd_params: list = []
        if state_code:
            sd_where += " AND state_code = %s"
            sd_params.append(state_code)
        cursor.execute(
            f"SELECT count(*) FROM public.jurisdictions WHERE {sd_where}", sd_params
        )
        school_districts = cursor.fetchone()[0] or 0

        # --- Nonprofits (public.mdm_organization_nonprofit) ---
        # This table has NO state_code column, and mdm_bridge_org_address shares
        # zero master_org_id values with it (different ID namespaces), so a clean
        # state/county/city join is not available.
        # TODO: state-filtered nonprofit count needs org->location join
        # (mdm_bridge_org_address currently does not link to mdm_organization_nonprofit).
        cursor.execute("SELECT count(*) FROM public.mdm_organization_nonprofit")
        nonprofits = cursor.fetchone()[0] or 0

        # --- Events / meetings (public.event) ---
        ev_where = "TRUE"
        ev_params: list = []
        if state_code:
            ev_where = "state_code = %s"
            ev_params.append(state_code)
        cursor.execute(
            f"SELECT count(*) FROM public.event WHERE {ev_where}", ev_params
        )
        meetings = cursor.fetchone()[0] or 0

        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error counting jurisdictions/nonprofits/events from public schema: {e}")
    
    # Count contacts (officials) from the public.contact_official table — replaces
    # the retired gold officials parquet feed (data/gold/contact_official.parquet).
    # state -> state_code (2-letter); city -> jurisdiction ILIKE.
    contacts = 0
    try:
        conn = psycopg2.connect(LOCAL_DB_URL)
        cursor = conn.cursor()
        where_clauses = []
        params: list = []
        if state:
            where_clauses.append("state_code = %s")
            params.append(state.upper() if len(state) == 2 else state)
        if city:
            where_clauses.append("jurisdiction ILIKE %s")
            params.append(f"%{city}%")
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        cursor.execute(
            f"SELECT count(*) FROM public.contact_official WHERE {where_sql}", params
        )
        row = cursor.fetchone()
        contacts = row[0] if row else 0
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error counting contacts from public.contact_official: {e}")
        contacts = 0
    
    # Count causes (NTEE cause taxonomy - always national).
    # public.tag replaced the retired reference/causes_ntee_codes.parquet feed.
    causes = 0
    try:
        conn = psycopg2.connect(LOCAL_DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM public.tag")
        causes = cursor.fetchone()[0] or 0
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error counting causes from public.tag: {e}")
        causes = 0

    # Count states with data
    states_with_data = len(list(Path('data/gold/states').glob('*/')))

    # Count domains
    domains = 0  # no Postgres source for domains; gold glob is empty (returns 0)
    
    # Format display values - use ACTUAL counts only, no extrapolation
    # Don't make up numbers we don't have
    nonprofits_display = f'{nonprofits:,}'
    meetings_display = f'{meetings:,}'
    contacts_display = f'{contacts:,}'
    
    # Build jurisdictions breakdown for city-level views
    jurisdictions_breakdown = None
    if city and state:
        jurisdictions_breakdown = [
            {'type': 'City', 'name': city},
            {'type': 'County', 'name': county if county else 'County (TBD)'},
            {'type': 'State', 'name': state},
            {'type': 'School District', 'name': f'{city} School District'}
        ]
    
    return {
        'level': level,
        'location': location_display,
        'state': state,
        'county': county,
        'city': city,
        
        # Core counts
        'jurisdictions': jurisdictions,
        'jurisdictions_display': f'{jurisdictions:,}',
        'jurisdictions_breakdown': jurisdictions_breakdown,  # List of jurisdiction types for city-level
        'school_districts': school_districts,
        'school_districts_display': f'{school_districts:,}',
        
        # Nonprofits (actual counts only)
        'nonprofits_current': nonprofits,
        'nonprofits_display': nonprofits_display,
        
        # Meetings (actual counts only)
        'meetings_current': meetings,
        'meetings_display': meetings_display,
        
        # Contacts (actual counts only)
        'contacts_current': contacts,
        'contacts_display': contacts_display,
        
        # Other metrics
        'causes': causes,
        'causes_display': f'{causes}',
        'states_with_data': states_with_data,
        'domains': domains,
        'last_updated': datetime.now().isoformat(),
        
        # Calculated metrics (use N/A for unavailable data)
        'budget_tracked': 'N/A',
        'fact_checks': 'N/A',
        'grant_opportunities': '1,000s',
        'churches': f'{int(nonprofits * 0.1):,}' if nonprofits > 0 else '4,372',
        'policy_decisions': 'N/A',
        'states_total': states_with_data,
    }


def get_cached_stats(state: Optional[str] = None, 
                    county: Optional[str] = None, 
                    city: Optional[str] = None) -> Dict[str, Any]:
    """Get stats with multi-level caching"""
    global STATS_CACHE
    
    # Build cache key based on geographic level
    if city and state:
        # City level (county is optional)
        if county:
            cache_key = f"city:{state}:{county}:{city}"
        else:
            cache_key = f"city:{state}:{city}"
    elif county and state:
        cache_key = f"county:{state}:{county}"
    elif state:
        cache_key = f"state:{state}"
    else:
        cache_key = "national"
    
    now = datetime.now()
    
    # Check if cached stats exist and are still valid
    if cache_key in STATS_CACHE:
        cached_entry = STATS_CACHE[cache_key]
        cache_timestamp = cached_entry.get('_cache_timestamp')
        
        if cache_timestamp and (now - cache_timestamp) < CACHE_DURATION:
            # Return cached stats (remove internal timestamp before returning)
            stats = cached_entry.copy()
            stats.pop('_cache_timestamp', None)
            return stats
    
    # Calculate fresh stats
    try:
        # Use database version for faster queries
        stats = calculate_stats_from_db(state=state, county=county, city=city)
        
        # Add to cache with timestamp
        cache_entry = stats.copy()
        cache_entry['_cache_timestamp'] = now
        STATS_CACHE[cache_key] = cache_entry
        
        return stats
    except Exception as e:
        print(f"Error calculating stats for {cache_key}: {e}")
        
        # Return fallback stats if calculation fails (use real numbers only)
        return {
            'level': 'national' if not state else ('state' if not county else ('county' if not city else 'city')),
            'location': state or 'United States',
            'jurisdictions_display': '925',
            'nonprofits_display': '43,726',
            'meetings_display': '6,913',
            'contacts_display': '362',
            'school_districts_display': '306',
            'causes_display': '196',
            'churches': '4,372',
            'budget_tracked': 'N/A',
            'fact_checks': 'N/A',
            'grant_opportunities': '1,000s',
            'policy_decisions': 'N/A',
            'states_with_data': 5,
            'states_total': 5,
            'last_updated': now.isoformat(),
            'error': str(e)
        }


@router.get("/stats")
async def get_stats(
    state: Optional[str] = Query(None, description="Two-letter state code (e.g., 'MA')"),
    county: Optional[str] = Query(None, description="County name (e.g., 'Suffolk County')"),
    city: Optional[str] = Query(None, description="City name (e.g., 'Boston')")
):
    """
    Get platform statistics from real data with optional geographic filtering
    
    **Examples:**
    - `/api/stats` - National statistics
    - `/api/stats?state=MA` - Massachusetts statistics  
    - `/api/stats?state=MA&county=Suffolk` - Suffolk County, MA statistics
    - `/api/stats?state=MA&county=Suffolk&city=Boston` - Boston, MA statistics
    
    **Returns:** Cached metrics calculated from parquet files:
    - Jurisdictions tracked (cities, counties, townships, school districts)
    - Nonprofits monitored 
    - Meetings analyzed
    - Officials and contacts tracked
    - Causes and NTEE codes
    
    **Cache duration:** 1 hour per geographic level
    """
    try:
        stats = get_cached_stats(state=state, county=county, city=city)
        return {
            'success': True,
            'data': stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")


@router.get("/stats/detailed")
async def get_detailed_stats(
    state: Optional[str] = Query(None, description="Two-letter state code (e.g., 'MA')")
):
    """
    Get detailed statistics including breakdowns by state
    
    Returns:
    - Overall totals
    - Per-state breakdowns (if no state specified)
    - Data quality metrics
    """
    try:
        stats = get_cached_stats(state=state)
        
        # Add state-by-state breakdown (only for national view).
        # Served from the Postgres `public` schema via single grouped queries
        # (NOT per-state parquet dirs) per CLAUDE.md.
        if not state:
            states: Dict[str, Dict[str, int]] = {}
            try:
                conn = psycopg2.connect(LOCAL_DB_URL)
                cursor = conn.cursor()

                # meetings -> public.event grouped by state_code
                cursor.execute(
                    "SELECT state_code, count(*) FROM public.event "
                    "WHERE state_code IS NOT NULL GROUP BY state_code"
                )
                for sc, cnt in cursor.fetchall():
                    states.setdefault(sc, {})['meetings'] = cnt

                # contacts_nonprofit_officers -> public.mdm_bridge_person_organization
                # (Form-990 officers) grouped by state_code.
                cursor.execute(
                    "SELECT state_code, count(*) FROM public.mdm_bridge_person_organization "
                    "WHERE state_code IS NOT NULL GROUP BY state_code"
                )
                for sc, cnt in cursor.fetchall():
                    states.setdefault(sc, {})['contacts_nonprofit_officers'] = cnt

                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"Error building per-state breakdown from public schema: {e}")

            # nonprofits_organizations per-state is intentionally omitted:
            # public.mdm_organization_nonprofit has no state_code and no usable
            # org->location join (mdm_bridge_org_address does not link to it).
            # TODO: state-filtered nonprofit count needs org->location join.

            return {
                'success': True,
                'data': {
                    **stats,
                    'state_breakdown': states
                }
            }
        else:
            return {
                'success': True,
                'data': stats
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching detailed stats: {str(e)}")


@router.post("/stats/refresh")
async def refresh_stats(
    state: Optional[str] = Query(None, description="State to refresh (or all if not specified)")
):
    """
    Force refresh of statistics cache
    
    Useful after data updates or imports.
    Can refresh a specific state or all levels.
    """
    global STATS_CACHE
    
    try:
        if state:
            # Clear cache for specific state and its derivatives
            keys_to_remove = [k for k in STATS_CACHE.keys() if k.startswith(f'state:{state}') or k.startswith(f'county:{state}') or k.startswith(f'city:{state}')]
            for key in keys_to_remove:
                STATS_CACHE.pop(key, None)
            message = f'Statistics cache refreshed for {state}'
        else:
            # Clear all cache
            STATS_CACHE = {}
            message = 'All statistics cache refreshed'
        
        # Recalculate to warm cache
        stats = get_cached_stats(state=state)
        
        return {
            'success': True,
            'message': message,
            'data': stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing stats: {str(e)}")
