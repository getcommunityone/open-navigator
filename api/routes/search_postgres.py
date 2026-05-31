"""
PostgreSQL-based search functions
Uses indexed search tables for fast queries (10-100x faster than parquet)
"""
from typing import Optional, List
from loguru import logger
import asyncpg
import os
from datetime import datetime
from dataclasses import dataclass
from api.utils.formatters import format_organization_id, format_role_type, format_title

# Database configuration
# Priority: NEON_DATABASE_URL_DEV (local) > NEON_DATABASE_URL (production)
NEON_DATABASE_URL_DEV = os.getenv('NEON_DATABASE_URL_DEV')
NEON_DATABASE_URL = os.getenv('NEON_DATABASE_URL')

# Use dev database for local development, production database for deployed environments
DATABASE_URL = NEON_DATABASE_URL_DEV or NEON_DATABASE_URL

# Bronze schema for AI-extracted meeting data (topics, decisions, etc.)
# NOTE: Bronze data is now in bronze schema of main database
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
BRONZE_DATABASE_URL = os.getenv('LOCAL_BRONZE_DATABASE_URL', 
                                 f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator')

# Connection pools (created on first request)
_db_pool = None  # Production database pool (Neon)
_bronze_db_pool = None  # Bronze database pool (local PostgreSQL)

# State name to code mapping for input normalization
STATE_NAME_TO_CODE = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
    'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
    'District of Columbia': 'DC', 'Puerto Rico': 'PR', 'Guam': 'GU', 'Virgin Islands': 'VI'
}


def normalize_state_input(state: Optional[str]) -> Optional[str]:
    """
    Normalize state input to 2-letter code.
    
    Accepts:
    - 2-letter codes: 'MA', 'ma' -> 'MA'
    - Full names: 'Massachusetts', 'massachusetts' -> 'MA'
    - Already uppercase codes: 'MA' -> 'MA'
    
    Returns:
        2-letter uppercase state code or None
    """
    if not state:
        return None
    
    state_stripped = state.strip()
    
    # If already a 2-letter code, return uppercase
    if len(state_stripped) == 2:
        return state_stripped.upper()
    
    # Check if it's a full state name (case-insensitive)
    for name, code in STATE_NAME_TO_CODE.items():
        if name.lower() == state_stripped.lower():
            return code
    
    # If not found, return uppercase version of input (might be invalid but let DB handle it)
    return state_stripped.upper()


@dataclass
class SearchResult:
    """Search result data class"""
    result_type: str
    title: str
    subtitle: str
    description: str
    url: str
    score: float
    metadata: dict


async def get_db_pool():
    """Get or create database connection pool"""
    global _db_pool
    if _db_pool is None:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")
        
        db_type = "Development (Local PostgreSQL)" if NEON_DATABASE_URL_DEV else "Production (Neon)"
        logger.info(f"🗄️  Creating connection pool to {db_type}")
        
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=20)
    return _db_pool


async def search_jurisdictions_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    jurisdiction_levels: Optional[List[str]] = None,
    limit: int = 10,
    offset: int = 0
) -> List[SearchResult]:
    """
    Search jurisdictions using PostgreSQL full-text search
    
    Args:
        query: Search text (jurisdiction name)
        state: Filter by state code (e.g., 'MA') or full name (e.g., 'Massachusetts')
        city: Filter by city name  
        jurisdiction_levels: Filter by types (city, county, town, school_district, etc.)
        limit: Max results
        offset: Pagination offset
    
    Returns:
        List of SearchResult objects
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)
    
    try:
        pool = await get_db_pool()
        
        # Map frontend level IDs to database types
        level_mapping = {
            'city': 'city',
            'county': 'county',
            'town': 'town',
            'village': 'village',
            'school_district': 'school_district',
            'special_district': 'special_district',
            'state': 'state'
        }
        
        # Build SQL query
        where_clauses = []
        params = []
        param_idx = 1
        has_query = query and query.strip()
        
        # Text search filter first (if present) - must be $1 for score calculation
        score_param_idx = None
        if has_query:
            # Use search_text field which includes name + state + type for better matching
            where_clauses.append(f"to_tsvector('english', COALESCE(search_text, display_name)) @@ plainto_tsquery('english', ${param_idx})")
            params.append(query)
            score_param_idx = param_idx
            param_idx += 1
        
        # State filter
        if state:
            where_clauses.append(f"state_code = ${param_idx}")
            params.append(state.upper())
            param_idx += 1
        
        # City filter
        if city:
            where_clauses.append(f"LOWER(display_name) LIKE LOWER(${param_idx})")
            params.append(f"%{city}%")
            param_idx += 1
        
        # Jurisdiction level filter
        if jurisdiction_levels:
            db_types = [level_mapping.get(level) for level in jurisdiction_levels if level_mapping.get(level)]
            if db_types:
                placeholders = ','.join([f"${param_idx + i}" for i in range(len(db_types))])
                where_clauses.append(f"type IN ({placeholders})")
                params.extend(db_types)
                param_idx += len(db_types)
        
        # Build final WHERE clause
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        
        # Select clause and order by
        if has_query:
            select_score = f"ts_rank(to_tsvector('english', COALESCE(search_text, display_name)), plainto_tsquery('english', ${score_param_idx})) as score"
            order_by = f"score DESC, display_name ASC"
        else:
            select_score = "1.0 as score"
            order_by = "display_name ASC"
        
        # Build complete query
        sql = f"""
            SELECT 
                display_name as name,
                jurisdiction_type as type,
                state_code,
                state_name as state,
                county_name as county,
                geoid,
                population,
                latitude,
                longitude,
                website_url,
                {select_score}
            FROM jurisdictions
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${param_idx}
            OFFSET ${param_idx + 1}
        """
        
        # Add limit and offset
        params.append(limit)
        params.append(offset)
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            
            results = []
            for row in rows:
                jurisdiction_label = row['type'].replace('_', ' ').title()
                
                results.append(SearchResult(
                    result_type='jurisdiction',
                    title=row['name'],
                    subtitle=f"{jurisdiction_label}",
                    description=f"{jurisdiction_label} in {row['state']}" + (f" • Pop: {row['population']:,}" if row['population'] else ""),
                    url=f"/jurisdictions/{row['geoid']}" if row['geoid'] else f"/jurisdictions/{row['name']}",
                    score=float(row.get('score', 1.0)) if query else 1.0,
                    metadata={
                        'state': row['state'],
                        'state_code': row['state_code'],
                        'geoid': row['geoid'],
                        'type': row['type'],
                        'county': row['county'],
                        'population': row['population']
                    }
                ))
            
            logger.info(f"🏛️  PostgreSQL jurisdictions search: {len(results)} results")
            return results
            
    except Exception as e:
        logger.error(f"PostgreSQL jurisdictions search error: {e}")
        return []


async def search_contacts_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 10
) -> List[SearchResult]:
    """
    Search contacts (nonprofit officers, local officials) using PostgreSQL
    
    Args:
        query: Search text (name, title, organization)
        state: Filter by state code (e.g., 'MA') or full name (e.g., 'Massachusetts')
        limit: Max results
    
    Returns:
        List of SearchResult objects
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)
    
    try:
        pool = await get_db_pool()
        
        # Build WHERE clauses
        where_clauses = []
        params = []
        param_idx = 1
        
        if state:
            where_clauses.append(f"state_code = ${param_idx}")
            params.append(state.upper())
            param_idx += 1
        
        # Text search across name, title, and organization
        if query and query.strip():
            where_clauses.append(f"""(
                to_tsvector('english', name) @@ plainto_tsquery('english', ${param_idx})
                OR to_tsvector('english', COALESCE(organization_name, '')) @@ plainto_tsquery('english', ${param_idx})
                OR LOWER(title) LIKE LOWER(${param_idx + 1})
                OR LOWER(organization_name) LIKE LOWER(${param_idx + 1})
                OR LOWER(name) LIKE LOWER(${param_idx + 1})
            )""")
            params.append(query)
            params.append(f"%{query}%")
            param_idx += 2
            
            # Rank by relevance
            order_by = f"""
                GREATEST(
                    ts_rank(to_tsvector('english', name), plainto_tsquery('english', ${param_idx - 2})),
                    ts_rank(to_tsvector('english', COALESCE(organization_name, '')), plainto_tsquery('english', ${param_idx - 2}))
                ) DESC, name ASC
            """
        else:
            order_by = "name ASC"
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        
        sql = f"""
            SELECT 
                name,
                title,
                organization_name,
                organization_ein,
                email,
                phone,
                city,
                state_code,
                state,
                role_type,
                compensation,
                source
            FROM contact
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${param_idx}
        """
        params.append(limit)
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            
            results = []
            for row in rows:
                org_display = format_organization_id(row['organization_name']) if row['organization_name'] else 'Unknown Organization'
                location = f"{row['city']}, {row['state']}" if row['city'] and row['state'] else (row['state'] or '')
                
                results.append(SearchResult(
                    result_type='contact',
                    title=row['name'],
                    subtitle=f"{format_title(row['title']) if row['title'] else 'Officer'} - {org_display}",
                    description=f"{format_role_type(row['role_type']) if row['role_type'] else 'Contact'} in {location}",
                    url=f"/people/{row['name'].replace(' ', '-')}",
                    score=1.0,
                    metadata={
                        'name': row['name'],
                        'title': row['title'],
                        'organization': org_display,
                        'organization_ein': row['organization_ein'],
                        'state': row['state'],
                        'state_code': row['state_code'],
                        'city': row['city'],
                        'role_type': row['role_type'],
                        'compensation': row['compensation'],
                        'email': row.get('email'),
                        'phone': row.get('phone'),
                        'source': row['source']
                    }
                ))
            
            logger.info(f"👤 PostgreSQL contacts search: {len(results)} results")
            return results
            
    except Exception as e:
        logger.error(f"PostgreSQL contacts search error: {e}")
        return []


async def search_organizations_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    ntee_code: Optional[str] = None,
    ein: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    sort: str = 'relevance'
) -> List[SearchResult]:
    """
    Search nonprofit organizations using PostgreSQL
    
    Args:
        query: Search text (organization name)
        state: Filter by state code (e.g., 'MA') or full name (e.g., 'Massachusetts')
        city: Filter by city name (case-insensitive)
        ntee_code: Filter by NTEE code prefix
        ein: Exact EIN match
        limit: Max results
        offset: Pagination offset
        sort: Sort order (relevance, name-asc, name-desc, revenue-asc, revenue-desc, assets-asc, assets-desc)
    
    Returns:
        List of SearchResult objects
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)
    
    try:
        pool = await get_db_pool()
        
        # Build WHERE clauses
        where_clauses = []
        params = []
        param_idx = 1
        
        # EIN exact match (highest priority)
        if ein:
            where_clauses.append(f"ein = ${param_idx}")
            params.append(ein.strip())
            param_idx += 1
        
        # State filter
        if state:
            where_clauses.append(f"state_code = ${param_idx}")
            params.append(state.upper())
            param_idx += 1
        
        # City filter (case-insensitive)
        if city:
            where_clauses.append(f"LOWER(city) = LOWER(${param_idx})")
            params.append(city.strip())
            param_idx += 1
        
        # NTEE code filter
        if ntee_code:
            where_clauses.append(f"ntee_code LIKE ${param_idx}")
            params.append(f"{ntee_code}%")
            param_idx += 1
        
        # Text search (if no EIN specified)
        if query and query.strip() and not ein:
            where_clauses.append(f"to_tsvector('english', name) @@ plainto_tsquery('english', ${param_idx})")
            params.append(query)
            param_idx += 1
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        
        # Debug logging
        logger.info(f"🔍 Organizations search - WHERE: {where_sql} | PARAMS: {params} | city={city}")
        
        # Determine sort order
        if sort == 'name-asc':
            order_by = "name ASC"
        elif sort == 'name-desc':
            order_by = "name DESC"
        elif sort == 'revenue-asc':
            order_by = "revenue ASC NULLS LAST"
        elif sort == 'revenue-desc':
            order_by = "revenue DESC NULLS LAST"
        elif sort == 'assets-asc':
            order_by = "assets ASC NULLS LAST"
        elif sort == 'assets-desc':
            order_by = "assets DESC NULLS LAST"
        elif query and query.strip() and not ein:
            # Relevance ranking for text search
            order_by = f"ts_rank(to_tsvector('english', name), plainto_tsquery('english', ${param_idx - 1})) DESC, name ASC"
        else:
            order_by = "name ASC"
        
        sql = f"""
            SELECT 
                ein,
                name,
                city,
                state_code,
                state,
                county,
                ntee_code,
                ntee_description,
                revenue,
                assets,
                income,
                tax_period,
                gt990_tax_year,
                gt990_total_revenue,
                gt990_total_expenses,
                gt990_total_assets,
                gt990_mission,
                has_gt990_data
            FROM organization_nonprofit
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${param_idx}
            OFFSET ${param_idx + 1}
        """
        params.append(limit)
        params.append(offset)
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            
            results = []
            for row in rows:
                location = f"{row['city']}, {row['state']}" if row['city'] and row['state'] else (row['state'] or '')

                # Prefer real e-filed 990 figures (GivingTuesday datamart) over the
                # IRS BMF proxy; fall back to the BMF amounts when no 990 was matched.
                revenue = row['gt990_total_revenue'] if row['gt990_total_revenue'] is not None else row['revenue']
                assets = row['gt990_total_assets'] if row['gt990_total_assets'] is not None else row['assets']
                expenses = row['gt990_total_expenses']
                mission = row['gt990_mission']

                # Format financials
                financials = []
                if revenue:
                    financials.append(f"Revenue: ${revenue:,}")
                if expenses:
                    financials.append(f"Expenses: ${expenses:,}")
                if assets:
                    financials.append(f"Assets: ${assets:,}")

                # The 990 mission statement is a far better description than the NTEE
                # label; truncate for the card and keep the full text in metadata.
                if mission:
                    description = mission if len(mission) <= 280 else mission[:277] + "..."
                else:
                    description = row['ntee_description'] or 'Nonprofit organization'
                if financials:
                    description += " • " + " • ".join(financials)

                results.append(SearchResult(
                    result_type='organization',
                    title=row['name'],
                    subtitle=location,
                    description=description,
                    url=f"/search?types=organizations&state={row['state_code']}&ein={row['ein']}",
                    score=1.0,
                    metadata={
                        'ein': row['ein'],
                        'state': row['state'],
                        'state_code': row['state_code'],
                        'city': row['city'],
                        'county': row['county'],
                        'ntee_code': row['ntee_code'],
                        'ntee_description': row['ntee_description'],
                        'revenue': row['revenue'],
                        'assets': row['assets'],
                        'income': row['income'],
                        'tax_period': row['tax_period'],
                        # GivingTuesday 990 datamart enrichment (real e-filed figures)
                        'mission': mission,
                        'gt990_tax_year': row['gt990_tax_year'],
                        'gt990_total_revenue': row['gt990_total_revenue'],
                        'gt990_total_expenses': row['gt990_total_expenses'],
                        'gt990_total_assets': row['gt990_total_assets'],
                        'has_gt990_data': row['has_gt990_data'],
                    }
                ))
            
            logger.info(f"🏢 PostgreSQL organizations search: {len(results)} results")
            return results
            
    except Exception as e:
        logger.error(f"PostgreSQL organizations search error: {e}")
        return []


async def search_events_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 10
) -> List[SearchResult]:
    """
    Search meetings/events using PostgreSQL
    
    Args:
        query: Search text (title, jurisdiction, description)
        state: Filter by state code (e.g., 'MA') or full name (e.g., 'Massachusetts')
        limit: Max results
    
    Returns:
        List of SearchResult objects
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)
    
    try:
        pool = await get_db_pool()
        
        # Build WHERE clauses
        where_clauses = []
        params = []
        param_idx = 1
        
        if state:
            where_clauses.append(f"state_code = ${param_idx}")
            params.append(state.upper())
            param_idx += 1
        
        # Text search
        if query and query.strip():
            where_clauses.append(f"""(
                to_tsvector('english', event_title) @@ plainto_tsquery('english', ${param_idx})
                OR LOWER(jurisdiction_name) LIKE LOWER(${param_idx + 1})
            )""")
            params.append(query)
            params.append(f"%{query}%")
            param_idx += 2
            
            order_by = f"ts_rank(to_tsvector('english', event_title), plainto_tsquery('english', ${param_idx - 2})) DESC, event_date DESC"
        else:
            order_by = "event_date DESC"
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        
        sql = f"""
            SELECT 
                event_id,
                event_title,
                event_description,
                event_date,
                jurisdiction_name,
                jurisdiction_type,
                state_code,
                state,
                city,
                video_url,
                agenda_url
            FROM event
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${param_idx}
        """
        params.append(limit)
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            
            results = []
            for row in rows:
                location = f"{row['jurisdiction_name']}, {row['state']}" if row['jurisdiction_name'] and row['state'] else ''
                date_str = row['event_date'].strftime('%Y-%m-%d') if row['event_date'] else ''
                
                description = (row['event_description'] or '')[:200]
                if len(description) == 200:
                    description += "..."
                
                results.append(SearchResult(
                    result_type='meeting',
                    title=row['event_title'],
                    subtitle=f"{location} - {date_str}",
                    description=description,
                    url=f"/documents?meeting_id={row['event_id']}",
                    score=1.0,
                    metadata={
                        'jurisdiction': row['jurisdiction_name'],
                        'jurisdiction_type': row['jurisdiction_type'],
                        'state': row['state'],
                        'state_code': row['state_code'],
                        'city': row['city'],
                        'date': date_str,
                        'meeting_id': row['event_id'],
                        'video_url': row['video_url'],
                        'agenda_url': row['agenda_url']
                    }
                ))
            
            logger.info(f"📅 PostgreSQL events search: {len(results)} results")
            return results
            
    except Exception as e:
        logger.error(f"PostgreSQL events search error: {e}")
        return []


async def search_bills_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    session: Optional[str] = None,
    limit: int = 10
) -> List[SearchResult]:
    """
    Search bills using PostgreSQL full-text search
    
    Args:
        query: Search text (title, bill number, abstract)
        state: Filter by state code (e.g., 'MA') or full name (e.g., 'Massachusetts')
        session: Filter by legislative session
        limit: Max results
    
    Returns:
        List of SearchResult objects
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)
    
    try:
        pool = await get_db_pool()
        
        # Build WHERE clauses
        where_clauses = []
        params = []
        param_idx = 1
        
        if state:
            where_clauses.append(f"state_code = ${param_idx}")
            params.append(state.upper())
            param_idx += 1
        
        if session:
            where_clauses.append(f"session = ${param_idx}")
            params.append(session)
            param_idx += 1
        
        # Text search across title and abstract
        if query and query.strip():
            where_clauses.append(f"""(
                to_tsvector('english', title) @@ plainto_tsquery('english', ${param_idx})
                OR to_tsvector('english', COALESCE(abstract, '')) @@ plainto_tsquery('english', ${param_idx})
                OR LOWER(bill_number) LIKE LOWER(${param_idx + 1})
            )""")
            params.append(query)
            params.append(f"%{query}%")
            param_idx += 2
            
            order_by = f"""
                GREATEST(
                    ts_rank(to_tsvector('english', title), plainto_tsquery('english', ${param_idx - 2})),
                    ts_rank(to_tsvector('english', COALESCE(abstract, '')), plainto_tsquery('english', ${param_idx - 2}))
                ) DESC, latest_action_date DESC NULLS LAST
            """
        else:
            order_by = "latest_action_date DESC NULLS LAST"
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        
        sql = f"""
            SELECT 
                bill_id,
                bill_number,
                title,
                classification,
                session,
                session_name,
                jurisdiction_name,
                state_code,
                state,
                latest_action_date,
                latest_action_description,
                abstract,
                source_url
            FROM bills_search
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${param_idx}
        """
        params.append(limit)
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            
            results = []
            for row in rows:
                # Format title  
                title = f"{row['bill_number']}: {row['title'][:100]}"
                if len(row['title']) > 100:
                    title += "..."
                
                # Format subtitle with session and date
                subtitle_parts = []
                if row['session_name']:
                    subtitle_parts.append(row['session_name'])
                if row['latest_action_date']:
                    subtitle_parts.append(f"Last action: {row['latest_action_date'].strftime('%Y-%m-%d')}")
                subtitle = " • ".join(subtitle_parts) if subtitle_parts else row.get('jurisdiction_name', '')
                
                # Description is either abstract or latest action
                description = row['abstract'] if row['abstract'] else (row['latest_action_description'] or '')
                if description and len(description) > 200:
                    description = description[:200] + "..."
                
                results.append(SearchResult(
                    result_type='bill',
                    title=title,
                    subtitle=subtitle,
                    description=description,
                    url=row['source_url'] or f"/bills/{row['state_code']}/{row['bill_number']}",
                    score=1.0,
                    metadata={
                        'bill_id': row['bill_id'],
                        'bill_number': row['bill_number'],
                        'state': row['state'],
                        'state_code': row['state_code'],
                        'session': row['session'],
                        'classification': row['classification'],
                        'latest_action_date': row['latest_action_date'].isoformat() if row['latest_action_date'] else None
                    }
                ))
            
            logger.info(f"📜 PostgreSQL bills search: {len(results)} results")
            return results
            
    except Exception as e:
        logger.error(f"PostgreSQL bills search error: {e}")
        return []


async def search_topics_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    ntee_code: Optional[str] = None,
    limit: int = 10
) -> List[SearchResult]:
    """
    Search meeting topics from bronze_topics table.
    Topics are AI-extracted decision topics from meeting transcripts.
    
    Args:
        query: Search query (searches topic, headline, themes)
        state: State code filter (not applicable for bronze, but kept for compatibility)
        ntee_code: NTEE code filter (e.g., 'E' for Health)
        limit: Max results to return
    
    Returns:
        List of SearchResult objects
    """
    global _bronze_db_pool
    
    try:
        # Create connection pool for bronze database if needed
        if _bronze_db_pool is None:
            _bronze_db_pool = await asyncpg.create_pool(
                BRONZE_DATABASE_URL,
                min_size=1,
                max_size=10,
                command_timeout=30
            )
        
        pool = _bronze_db_pool
        
        # Build WHERE clause
        where_conditions = []
        params = []
        param_idx = 1
        
        if query:
            # Full-text search across topic, headline, and themes
            where_conditions.append(f"""
                (topic ILIKE ${param_idx} 
                 OR headline ILIKE ${param_idx}
                 OR primary_theme ILIKE ${param_idx}
                 OR secondary_theme ILIKE ${param_idx})
            """)
            params.append(f"%{query}%")
            param_idx += 1
        
        if ntee_code:
            where_conditions.append(f"(ntee_major_group = ${param_idx} OR secondary_ntee_major_group = ${param_idx})")
            params.append(ntee_code)
            param_idx += 1
        
        where_sql = " AND ".join(where_conditions) if where_conditions else "TRUE"
        
        sql = f"""
            SELECT 
                id,
                source_event_id,
                decision_id,
                topic,
                headline,
                primary_theme,
                primary_theme_cofog,
                secondary_theme,
                ntee_code,
                ntee_major_group,
                ntee_category_label,
                secondary_ntee_code,
                secondary_ntee_major_group,
                extracted_at
            FROM bronze.bronze_topics
            WHERE {where_sql}
            ORDER BY extracted_at DESC
            LIMIT ${param_idx}
        """
        params.append(limit)
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            
            results = []
            for row in rows:
                # Format title
                title = row['topic'] or 'Untitled Topic'
                if len(title) > 100:
                    title = title[:100] + "..."
                
                # Format subtitle with theme
                subtitle_parts = []
                if row['primary_theme']:
                    subtitle_parts.append(row['primary_theme'])
                if row['ntee_category_label']:
                    subtitle_parts.append(f"Cause: {row['ntee_category_label']}")
                subtitle = " • ".join(subtitle_parts)
                
                # Description is the headline
                description = row['headline'] or ''
                if description and len(description) > 200:
                    description = description[:200] + "..."
                
                results.append(SearchResult(
                    result_type='topic',
                    title=title,
                    subtitle=subtitle,
                    description=description,
                    url=f"/topics/{row['id']}",
                    score=1.0,
                    metadata={
                        'id': row['id'],
                        'decision_id': row['decision_id'],
                        'source_event_id': row['source_event_id'],
                        'primary_theme': row['primary_theme'],
                        'ntee_code': row['ntee_code'],
                        'ntee_major_group': row['ntee_major_group'],
                        'cofog_code': row['primary_theme_cofog'],
                        'extracted_at': row['extracted_at'].isoformat() if row['extracted_at'] else None
                    }
                ))
            
            logger.info(f"📋 PostgreSQL topics search: {len(results)} results")
            return results
            
    except Exception as e:
        logger.error(f"PostgreSQL topics search error: {e}")
        return []


async def search_decisions_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 10
) -> List[SearchResult]:
    """
    Search governance decisions from bronze_decisions table.
    Decisions are AI-extracted policy decisions from meeting transcripts.
    
    Args:
        query: Search query (searches topic, headline, decision_statement)
        state: State code filter (not applicable for bronze, but kept for compatibility)
        outcome: Filter by outcome (APPROVED, DENIED, DEFERRED, etc.)
        limit: Max results to return
    
    Returns:
        List of SearchResult objects
    """
    global _bronze_db_pool
    
    try:
        # Create connection pool for bronze database if needed
        if _bronze_db_pool is None:
            _bronze_db_pool = await asyncpg.create_pool(
                BRONZE_DATABASE_URL,
                min_size=1,
                max_size=10,
                command_timeout=30
            )
        
        pool = _bronze_db_pool
        
        # Build WHERE clause
        where_conditions = []
        params = []
        param_idx = 1
        
        if query:
            # Full-text search across topic, headline, and decision_statement
            where_conditions.append(f"""
                (topic ILIKE ${param_idx} 
                 OR headline ILIKE ${param_idx}
                 OR decision_statement ILIKE ${param_idx})
            """)
            params.append(f"%{query}%")
            param_idx += 1
        
        if outcome:
            where_conditions.append(f"outcome = ${param_idx}")
            params.append(outcome.upper())
            param_idx += 1
        
        where_sql = " AND ".join(where_conditions) if where_conditions else "TRUE"
        
        sql = f"""
            SELECT 
                id,
                source_event_id,
                decision_id,
                subject_id,
                topic,
                headline,
                decision_statement,
                decision_method,
                outcome,
                decision_date,
                primary_theme,
                primary_theme_cofog,
                vote_tally,
                extracted_at
            FROM bronze.bronze_decisions
            WHERE {where_sql}
            ORDER BY decision_date DESC NULLS LAST, extracted_at DESC
            LIMIT ${param_idx}
        """
        params.append(limit)
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            
            results = []
            for row in rows:
                # Title is the headline (the actual decision)
                title = row['headline'] or row['decision_statement'] or 'Untitled Decision'
                if len(title) > 150:
                    title = title[:150] + "..."
                
                # Subtitle includes topic and metadata
                subtitle_parts = []
                if row['topic']:
                    subtitle_parts.append(row['topic'])
                if row['outcome']:
                    subtitle_parts.append(row['outcome'])
                if row['decision_date']:
                    subtitle_parts.append(row['decision_date'].strftime('%Y-%m-%d'))
                subtitle = " • ".join(subtitle_parts)
                
                # Description is the decision_statement for additional context
                description = row['decision_statement'] or row['headline'] or ''
                if description and len(description) > 200:
                    description = description[:200] + "..."
                
                results.append(SearchResult(
                    result_type='decision',
                    title=title,
                    subtitle=subtitle,
                    description=description,
                    url=f"/decisions/{row['id']}",
                    score=1.0,
                    metadata={
                        'id': row['id'],
                        'decision_id': row['decision_id'],
                        'subject_id': row['subject_id'],
                        'source_event_id': row['source_event_id'],
                        'outcome': row['outcome'],
                        'decision_method': row['decision_method'],
                        'decision_date': row['decision_date'].isoformat() if row['decision_date'] else None,
                        'primary_theme': row['primary_theme'],
                        'cofog_code': row['primary_theme_cofog'],
                        'vote_tally': row['vote_tally'],
                        'extracted_at': row['extracted_at'].isoformat() if row['extracted_at'] else None
                    }
                ))
            
            logger.info(f"⚖️ PostgreSQL decisions search: {len(results)} results")
            return results
            
    except Exception as e:
        logger.error(f"PostgreSQL decisions search error: {e}")
        return []

