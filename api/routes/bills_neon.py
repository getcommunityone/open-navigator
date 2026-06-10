"""
Bills API Routes - Hybrid approach using Neon + Parquet
- Map aggregates: Neon PostgreSQL (fast, lightweight)
- Detailed bills & sessions: Parquet files (saves Neon space)
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import asyncpg
import duckdb
import pandas as pd
from pathlib import Path
from loguru import logger
import os
from datetime import datetime, timedelta

from api.errors import ErrorDetail, parse_error
from api.database import DATA_SEARCH_PATH

router = APIRouter(prefix="/bills", tags=["bills"])

# Database configuration (for map aggregates only)
NEON_DATABASE_URL_DEV = os.getenv("NEON_DATABASE_URL_DEV")
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")
DATABASE_URL = NEON_DATABASE_URL_DEV or NEON_DATABASE_URL

# Parquet configuration (for detailed bills)
GOLD_DIR = Path("data/gold")
IS_HF_SPACES = os.getenv("HF_SPACES") == "1"
HF_ORGANIZATION = os.getenv('HF_ORGANIZATION', 'CommunityOne')

if DATABASE_URL:
    logger.info(f"🗄️  Bills map using: {'DEV' if NEON_DATABASE_URL_DEV else 'PROD'} database")
    logger.info(f"📁 Bills details using: {'HuggingFace' if IS_HF_SPACES else 'local'} parquet")
else:
    logger.warning("⚠️  No database URL configured. Map endpoint will not work.")

# Connection pool
_pool = None

# Cache for map data (TTL: 5 minutes)
_map_cache = {}
_map_cache_time = None
MAP_CACHE_DURATION = timedelta(minutes=5)


def get_hf_dataset_url(dataset_name: str) -> str:
    """Convert dataset name to HuggingFace parquet URL."""
    return f"https://huggingface.co/datasets/{HF_ORGANIZATION}/{dataset_name}/resolve/main/data/train-00000-of-00001.parquet"

def get_data_source(file_path: Path, use_remote: bool = False) -> str:
    """Get data source (local path or remote URL) based on environment."""
    if not IS_HF_SPACES and not use_remote:
        return str(file_path)
    
    # Convert local path to HuggingFace dataset name
    parts = file_path.parts
    filename = parts[-1].replace('.parquet', '').replace('_', '-')
    
    # Handle nested state-specific files (if they exist)
    if 'states' in parts:
        state_idx = parts.index('states')
        state = parts[state_idx + 1].lower()
        dataset_name = f"states-{state}-{filename}"
        return get_hf_dataset_url(dataset_name)
    
    # Handle flat files in gold directory
    # Map: bills_bills.parquet -> one-bills
    dataset_mapping = {
        'bills-bills': 'one-bills',
        'bills-bill-actions': 'one-bill-actions',
        'bills-bill-sponsorships': 'one-bill-sponsorships',
        'bills-map-aggregates': 'one-bills-map-aggregates',
    }
    
    dataset_name = dataset_mapping.get(filename, filename)
    return get_hf_dataset_url(dataset_name)


async def get_pool():
    """Get or create asyncpg connection pool."""
    global _pool
    if _pool is None and DATABASE_URL:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
            server_settings={"search_path": DATA_SEARCH_PATH},
        )
    return _pool


async def fetch_bills_from_parquet(
    state: str,
    q: Optional[str] = None,
    sessions: Optional[List[str]] = None,
    topic: Optional[str] = None,
    chambers: Optional[List[str]] = None,
    bill_types: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """Fetch bills from parquet files using DuckDB (detailed drill-down). Supports multi-select filters."""
    try:
        # Use flat file structure (all states in one file)
        bills_file = GOLD_DIR / "bills_bills.parquet"
        
        # Get data source (local or remote HuggingFace URL)
        data_source = get_data_source(bills_file, use_remote=IS_HF_SPACES)
        
        # Connect to DuckDB
        conn = duckdb.connect()
        
        # Build SQL query - ALWAYS filter by state_code (2-letter codes)
        where_clauses = ["state_code = ?"]
        params = [state]
        
        # Topic filter (keyword search in title)
        if topic:
            topic_keywords = {
                'fluoride': 'fluorid',
                'dental': 'dental',
                'medicaid': 'medicaid',
                'oral health': 'oral|dental|teeth',
                'health': 'health',
                'education': 'education|school',
            }
            keyword = topic_keywords.get(topic.lower(), topic)
            
            # Handle multiple keywords with OR
            if '|' in keyword:
                keyword_parts = keyword.split('|')
                keyword_clauses = ["LOWER(title) LIKE LOWER(?)"] * len(keyword_parts)
                where_clauses.append(f"({' OR '.join(keyword_clauses)})")
                params.extend([f'%{kw}%' for kw in keyword_parts])
            else:
                where_clauses.append("LOWER(title) LIKE LOWER(?)")
                params.append(f'%{keyword}%')
        
        if q:
            where_clauses.append("(LOWER(title) LIKE LOWER(?) OR LOWER(bill_number) LIKE LOWER(?))")
            pattern = f'%{q}%'
            params.extend([pattern, pattern])
        
        # Sessions filter (multi-select)
        if sessions and len(sessions) > 0:
            session_placeholders = ','.join(['?'] * len(sessions))
            where_clauses.append(f"session IN ({session_placeholders})")
            params.extend(sessions)
        
        # Chamber filter (multi-select - based on bill number prefix)
        if chambers and len(chambers) > 0:
            chamber_conditions = []
            for chamber in chambers:
                if chamber.lower() == 'house':
                    chamber_conditions.append("(bill_number LIKE 'HB%' OR bill_number LIKE 'HR%' OR bill_number LIKE 'HJR%' OR bill_number LIKE 'HCR%' OR bill_number LIKE 'HJM%' OR bill_number LIKE 'H %')")
                elif chamber.lower() == 'senate':
                    chamber_conditions.append("(bill_number LIKE 'SB%' OR bill_number LIKE 'SR%' OR bill_number LIKE 'SJR%' OR bill_number LIKE 'SCR%' OR bill_number LIKE 'SJM%' OR bill_number LIKE 'S %')")
                elif chamber.lower() == 'joint':
                    chamber_conditions.append("(bill_number LIKE '%JR%' OR bill_number LIKE '%JM%')")
            if chamber_conditions:
                where_clauses.append(f"({' OR '.join(chamber_conditions)})")
        
        # Bill type filter (multi-select - based on bill number pattern)
        if bill_types and len(bill_types) > 0:
            logger.info(f"🔍 Applying bill_types filter: {bill_types}")
            type_conditions = []
            for bill_type in bill_types:
                if bill_type == 'bill':
                    type_conditions.append("(bill_number LIKE 'HB%' OR bill_number LIKE 'SB%' OR bill_number LIKE 'AB%')")
                elif bill_type == 'resolution':
                    type_conditions.append("(bill_number LIKE 'HR%' OR bill_number LIKE 'SR%' OR bill_number LIKE 'AR%')")
                elif bill_type == 'joint_resolution':
                    type_conditions.append("(bill_number LIKE 'HJR%' OR bill_number LIKE 'SJR%' OR bill_number LIKE 'AJR%')")
                elif bill_type == 'concurrent_resolution':
                    type_conditions.append("(bill_number LIKE 'HCR%' OR bill_number LIKE 'SCR%')")
                elif bill_type == 'memorial':
                    type_conditions.append("(bill_number LIKE 'HJM%' OR bill_number LIKE 'SJM%')")
            if type_conditions:
                logger.info(f"✅ Adding type_conditions: {type_conditions}")
                where_clauses.append(f"({' OR '.join(type_conditions)})")
        
        # Status filter (multi-select - based on latest_action)
        if statuses and len(statuses) > 0:
            status_keywords = {
                'enacted': 'Enacted',
                'passed': 'passed|Passed',
                'adopted': 'Adopted|adopted',
                'failed': 'Failed|failed',
                'introduced': 'Introduced|introduced',
                'referred': 'referred|Referred',
                'reported': 'reported|Reported'
            }
            
            status_conditions = []
            for status in statuses:
                keyword = status_keywords.get(status.lower(), status)
                
                if '|' in keyword:
                    keyword_parts = keyword.split('|')
                    keyword_clauses = ["LOWER(latest_action) LIKE LOWER(?)"] * len(keyword_parts)
                    status_conditions.append(f"({' OR '.join(keyword_clauses)})")
                    params.extend([f'%{kw}%' for kw in keyword_parts])
                else:
                    status_conditions.append("LOWER(latest_action) LIKE LOWER(?)")
                    params.append(f'%{keyword}%')
            
            if status_conditions:
                where_clauses.append(f"({' OR '.join(status_conditions)})")
        
        where_clause = " AND ".join(where_clauses)
        
        # Count total
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM read_parquet(?)
            WHERE {where_clause}
        """
        count_params = [data_source] + params
        total = conn.execute(count_sql, count_params).fetchone()[0]
        
        # Fetch bills
        sql = f"""
            SELECT 
                bill_id,
                bill_number,
                title,
                classification,
                session,
                session_name,
                first_action_date,
                latest_action_date,
                latest_action,
                jurisdiction_name,
                abstract,
                source_url
            FROM read_parquet(?)
            WHERE {where_clause}
            ORDER BY latest_action_date DESC NULLS LAST, bill_number DESC
            LIMIT ? OFFSET ?
        """
        
        query_params = [data_source] + params + [limit, offset]
        rows = conn.execute(sql, query_params).fetchall()
        
        bills = []
        for row in rows:
            bills.append({
                "bill_id": row[0],
                "bill_number": row[1],
                "title": row[2],
                "classification": list(row[3]) if row[3] else [],
                "session": row[4],
                "session_name": row[5],
                "first_action_date": str(row[6]) if row[6] else None,
                "latest_action_date": str(row[7]) if row[7] else None,
                "latest_action": row[8],
                "jurisdiction_name": row[9],
                "abstract": row[10],
                "source_url": row[11],
            })
        
        conn.close()
        
        return {
            "state": state,
            "query": q,
            "topic": topic,
            "chambers": chambers,
            "bill_types": bill_types,
            "statuses": statuses,
            "sessions": sessions,
            "bills": bills,
            "total": total,
            "limit": limit,
            "offset": offset,
            "source": "parquet"
        }
        
    except Exception as e:
        logger.error(f"Error fetching bills from parquet: {e}")
        raise


async def fetch_sessions_from_parquet(
    state: str,
    topic: Optional[str] = None,
    chambers: Optional[List[str]] = None,
    bill_types: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    q: Optional[str] = None
) -> Dict[str, Any]:
    """Fetch sessions from parquet files using DuckDB, filtered by active filters. Supports multi-select."""
    try:
        # Use flat file structure (all states in one file)
        bills_file = GOLD_DIR / "bills_bills.parquet"
        
        # Get data source
        data_source = get_data_source(bills_file, use_remote=IS_HF_SPACES)
        
        # Connect to DuckDB
        conn = duckdb.connect()
        
        # Build WHERE clause with all filters - use state_code for 2-letter codes
        where_conditions = ["state_code = ?"]
        params = [data_source, state]
        
        # Topic filter
        if topic:
            topic_keywords = {
                'fluoride': 'fluorid',
                'dental': 'dental',
                'medicaid': 'medicaid',
                'oral health': 'oral|dental|teeth',
                'health': 'health',
                'education': 'education|school'
            }
            keyword = topic_keywords.get(topic.lower(), topic)
            where_conditions.append(f"REGEXP_MATCHES(LOWER(title), LOWER(?))")
            params.append(keyword)
        
        # Chamber filter (multi-select)
        if chambers and len(chambers) > 0:
            chamber_conditions = []
            for chamber in chambers:
                if chamber.lower() == 'house':
                    chamber_conditions.append("(bill_number LIKE 'HB%' OR bill_number LIKE 'HR%' OR bill_number LIKE 'HJR%' OR bill_number LIKE 'HCR%' OR bill_number LIKE 'HJM%')")
                elif chamber.lower() == 'senate':
                    chamber_conditions.append("(bill_number LIKE 'SB%' OR bill_number LIKE 'SR%' OR bill_number LIKE 'SJR%' OR bill_number LIKE 'SCR%' OR bill_number LIKE 'SJM%')")
                elif chamber.lower() == 'joint':
                    chamber_conditions.append("(bill_number LIKE '%JR%' OR bill_number LIKE '%JM%')")
            if chamber_conditions:
                where_conditions.append(f"({' OR '.join(chamber_conditions)})")
        
        # Bill type filter (multi-select)
        if bill_types and len(bill_types) > 0:
            type_patterns = {
                'bill': "(bill_number LIKE 'HB%' OR bill_number LIKE 'SB%' OR bill_number LIKE 'AB%')",
                'resolution': "(bill_number LIKE 'HR%' OR bill_number LIKE 'SR%' OR bill_number LIKE 'AR%')",
                'joint_resolution': "(bill_number LIKE 'HJR%' OR bill_number LIKE 'SJR%' OR bill_number LIKE 'AJR%')",
                'concurrent_resolution': "(bill_number LIKE 'HCR%' OR bill_number LIKE 'SCR%')",
                'memorial': "(bill_number LIKE 'HJM%' OR bill_number LIKE 'SJM%')"
            }
            type_conditions = []
            for bill_type in bill_types:
                if bill_type.lower() in type_patterns:
                    type_conditions.append(type_patterns[bill_type.lower()])
            if type_conditions:
                where_conditions.append(f"({' OR '.join(type_conditions)})")
        
        # Status filter (multi-select)
        if statuses and len(statuses) > 0:
            status_keywords = {
                'enacted': 'Enacted',
                'passed': 'passed|Passed',
                'adopted': 'Adopted|adopted',
                'failed': 'Failed|failed',
                'introduced': 'Introduced|introduced',
                'referred': 'referred|Referred',
                'reported': 'reported|Reported'
            }
            status_conditions = []
            for status in statuses:
                keyword = status_keywords.get(status.lower(), status)
                status_conditions.append(f"REGEXP_MATCHES(COALESCE(latest_action, ''), ?)")
                params.append(keyword)
            if status_conditions:
                where_conditions.append(f"({' OR '.join(status_conditions)})")
        
        # Search query
        if q:
            where_conditions.append("(LOWER(title) LIKE ? OR LOWER(bill_number) LIKE ?)")
            search_pattern = f"%{q.lower()}%"
            params.append(search_pattern)
            params.append(search_pattern)
        
        where_clause = " AND ".join(where_conditions)
        
        # Aggregate sessions - filter by state and other filters
        sql = f"""
            SELECT 
                session,
                MAX(session_name) as session_name,
                MIN(first_action_date) as start_date,
                MAX(latest_action_date) as end_date,
                COUNT(*) as bill_count
            FROM read_parquet(?)
            WHERE {where_clause}
            GROUP BY session
            ORDER BY MAX(latest_action_date) DESC NULLS LAST, session DESC
        """
        
        rows = conn.execute(sql, params).fetchall()
        
        sessions = []
        for row in rows:
            sessions.append({
                "session": row[0],
                "session_name": row[1],
                "start_date": str(row[2]) if row[2] else None,
                "end_date": str(row[3]) if row[3] else None,
                "bill_count": row[4]
            })
        
        conn.close()
        
        return {
            "state": state,
            "sessions": sessions,
            "total_sessions": len(sessions),
            "source": "parquet"
        }
        
    except Exception as e:
        logger.error(f"Error fetching sessions from parquet: {e}")
        raise


async def fetch_map_data_from_neon(
    topic: Optional[str] = None,
    session: Optional[str] = None
) -> Dict[str, Any]:
    """Fetch map aggregates from Neon PostgreSQL."""
    pool = await get_pool()
    
    # Use cache if available
    global _map_cache, _map_cache_time
    cache_key = f"{topic or 'all'}_{session or 'all'}"
    
    now = datetime.now()
    if _map_cache_time and (now - _map_cache_time) < MAP_CACHE_DURATION:
        if cache_key in _map_cache:
            logger.debug(f"🚀 Map cache hit for {cache_key}")
            return _map_cache[cache_key]
    
    async with pool.acquire() as conn:
        requested_topic = topic.lower() if topic else 'all'

        # The serving table `rpt_bill_map_aggregate` was repurposed by the
        # trending-topics dbt mart — its grain is now (jurisdiction_id, subject) and
        # it no longer carries the legacy policy-map columns
        # (topic / type_* / status_* / primary_*). When that schema is live, the old
        # choropleth query below 500s with `column "topic" does not exist`. Detect the
        # legacy schema first and, when it's gone, return a clean empty map instead of
        # erroring. We deliberately do NOT fabricate type/status counts to fill the
        # gap — restoring policy-map shading needs a dedicated aggregate table.
        has_legacy_schema = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'rpt_bill_map_aggregate'
                  AND column_name = 'topic'
            )
            """
        )
        if not has_legacy_schema:
            logger.warning(
                "📊 rpt_bill_map_aggregate has no legacy policy-map schema "
                "(topic/type/status columns); returning empty map. The table is now "
                "the trending-topics mart — policy-map shading needs its own aggregate."
            )
            return {
                "topic": requested_topic,
                "session": session,
                "states": {},
                "total_states": 0,
                "legend": {
                    "types": {},
                    "statuses": {
                        "enacted": "Enacted",
                        "failed": "Failed",
                        "pending": "Pending",
                    },
                },
                "message": "Policy-map aggregates are not available on this database.",
                "source": "neon",
            }

        # For now, we only support topic='all' (no topic filtering yet)
        # Session filtering would require aggregating bills on-the-fly

        sql = """
            SELECT
                state_code,
                topic,
                total_bills,
                type_bill,
                type_resolution,
                type_concurrent_resolution,
                type_joint_resolution,
                type_constitutional_amendment,
                status_enacted,
                status_failed,
                status_pending,
                primary_type,
                primary_status,
                map_category,
                sample_bills,
                last_updated
            FROM rpt_bill_map_aggregate
            WHERE topic = $1
        """

        rows = await conn.fetch(sql, requested_topic)
        
        # If topic-specific data not found, return empty (don't fallback)
        if not rows:
            logger.warning(f"📊 No pre-computed data for topic '{requested_topic}'")
            return {
                "topic": requested_topic,
                "session": session,
                "states": {},
                "total_states": 0,
                "message": f"No data available for topic '{requested_topic}'. Try 'all' or pre-compute aggregates for this topic.",
                "source": "neon"
            }
        
        state_data = {}
        for row in rows:
            state_code = row['state_code']
            
            # Parse sample bills JSON
            sample_bills = row['sample_bills'] or []
            if isinstance(sample_bills, str):
                import json
                sample_bills = json.loads(sample_bills)
            
            state_data[state_code] = {
                "state": state_code,
                "total_bills": row['total_bills'],
                "type_counts": {
                    "bill": row['type_bill'],
                    "resolution": row['type_resolution'],
                    "concurrent_resolution": row['type_concurrent_resolution'],
                    "joint_resolution": row['type_joint_resolution'],
                    "constitutional_amendment": row['type_constitutional_amendment']
                },
                "status_counts": {
                    "enacted": row['status_enacted'] or 0,
                    "failed": row['status_failed'] or 0,
                    "pending": row['status_pending'] or 0
                },
                "primary_type": row['primary_type'],
                "primary_status": row['primary_status'],
                "map_category": row['map_category'],
                "sample_bills": sample_bills,
                "last_updated": row['last_updated'].isoformat() if row['last_updated'] else None
            }
        
        # Build dynamic legend based on actual data
        unique_types = set()
        for state in state_data.values():
            if state['primary_type']:
                unique_types.add(state['primary_type'])
        
        # Map types to user-friendly names
        type_labels = {
            'mandate': 'Mandate',
            'removal': 'Removal',
            'study': 'Study',
            'funding': 'Funding',
            'coverage_expansion': 'Coverage Expansion',
            'screening': 'Screening',
            'provider_access': 'Provider Access',
            'expansion': 'Expansion',
            'coverage': 'Coverage',
            'reimbursement': 'Reimbursement',
            'eligibility': 'Eligibility',
            'requirement': 'Requirement',
            'curriculum': 'Curriculum',
            'reform': 'Reform',
            'protection': 'Protection',
            'restriction': 'Restriction',
            'other': 'Other'
        }
        
        legend_types = {t: type_labels.get(t, t.replace('_', ' ').title()) for t in unique_types}
        
        result = {
            "topic": requested_topic,
            "session": session,
            "states": state_data,
            "total_states": len(state_data),
            "legend": {
                "types": legend_types,
                "statuses": {
                    "enacted": "Enacted",
                    "failed": "Failed",
                    "pending": "Pending"
                }
            },
            "cached": True,
            "source": "neon"
        }
        
        # Update cache
        _map_cache[cache_key] = result
        _map_cache_time = now
        
        return result


@router.get("")
async def get_bills(
    state: str = Query(..., description="State abbreviation (e.g., MA, AL)"),
    q: Optional[str] = Query(None, description="Search query (bill number or title)"),
    sessions: Optional[str] = Query(None, description="Comma-separated session IDs"),
    topic: Optional[str] = Query(None, description="Policy topic (e.g., fluoride, dental, medicaid)"),
    chambers: Optional[str] = Query(None, description="Comma-separated chambers (house, senate, joint)"),
    bill_types: Optional[str] = Query(None, description="Comma-separated bill types"),
    statuses: Optional[str] = Query(None, description="Comma-separated bill statuses"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Search legislative bills using parquet files (detailed drill-down).
    Supports multiple values for sessions, chambers, bill_types, and statuses via comma separation.
    
    **Examples:**
    - `/api/bills?state=AL&q=dental` - Search Alabama bills for "dental"
    - `/api/bills?state=AL&sessions=2024rs,2023rs` - Get bills from multiple sessions
    - `/api/bills?state=AL&chambers=house,senate` - Get House and Senate bills
    - `/api/bills?state=AL&bill_types=bill,resolution` - Get bills and resolutions
    - `/api/bills?state=AL&statuses=enacted,passed` - Get enacted and passed bills
    """
    try:
        # Parse comma-separated values
        session_list = sessions.split(',') if sessions else None
        chamber_list = chambers.split(',') if chambers else None
        bill_type_list = bill_types.split(',') if bill_types else None
        status_list = statuses.split(',') if statuses else None
        
        # Debug logging
        logger.info(f"📊 Bills request: state={state}, q={q}, sessions={session_list}, topic={topic}, chambers={chamber_list}, bill_types={bill_type_list}, statuses={status_list}")
        
        result = await fetch_bills_from_parquet(
            state=state.upper(),
            q=q,
            sessions=session_list,
            topic=topic,
            chambers=chamber_list,
            bill_types=bill_type_list,
            statuses=status_list,
            limit=limit,
            offset=offset
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bills query error for state={state}: {e}")
        
        error_detail = parse_error(e, context={
            "state": state,
            "query": q,
            "session": session
        })
        
        return JSONResponse(
            status_code=500,
            content=error_detail.model_dump()
        )


@router.get("/sessions")
async def get_sessions(
    state: str = Query(..., description="State abbreviation (e.g., MA, AL)"),
    topic: Optional[str] = Query(None, description="Topic filter (e.g., fluoride, dental)"),
    chambers: Optional[str] = Query(None, description="Comma-separated chambers (house, senate, joint)"),
    bill_types: Optional[str] = Query(None, description="Comma-separated bill types"),
    statuses: Optional[str] = Query(None, description="Comma-separated statuses"),
    q: Optional[str] = Query(None, description="Search query")
):
    """
    Get legislative sessions for a state using parquet files, filtered by active search criteria.
    Supports multiple values for chambers, bill_types, and statuses via comma separation.
    
    **Examples:**
    - `/api/bills/sessions?state=MA` - Get all Massachusetts sessions
    - `/api/bills/sessions?state=MA&topic=dental` - Get sessions with dental bills
    - `/api/bills/sessions?state=MA&chambers=house,senate` - Filter by House and Senate
    """
    try:
        # Parse comma-separated values
        chamber_list = chambers.split(',') if chambers else None
        bill_type_list = bill_types.split(',') if bill_types else None
        status_list = statuses.split(',') if statuses else None
        
        # Debug logging
        logger.info(f"📊 Sessions request: state={state}, topic={topic}, chambers={chamber_list}, bill_types={bill_type_list}, statuses={status_list}, q={q}")
        
        result = await fetch_sessions_from_parquet(
            state=state.upper(),
            topic=topic,
            chambers=chamber_list,
            bill_types=bill_type_list,
            statuses=status_list,
            q=q
        )
        
        logger.info(f"✅ Returning {len(result.get('sessions', []))} sessions for {state}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sessions query error for state={state}: {e}")
        
        error_detail = parse_error(e, context={
            "state": state
        })
        
        return JSONResponse(
            status_code=500,
            content=error_detail.model_dump()
        )


@router.get("/map")
async def get_bill_map_data(
    topic: Optional[str] = Query(None, description="Topic to filter (e.g., dental, health, education)"),
    session: Optional[str] = Query(None, description="Legislative session")
):
    """
    Get aggregated bill data for choropleth map using Neon PostgreSQL.
    
    Returns pre-computed state-level aggregates for instant visualization.
    
    **Examples:**
    - `/api/bills/map` - Get national bill map data
    - `/api/bills/map?topic=dental` - Map dental legislation (not yet implemented)
    """
    try:
        if not DATABASE_URL:
            raise HTTPException(status_code=503, detail="Database not configured")
        
        result = await fetch_map_data_from_neon(topic=topic, session=session)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Map data query error: {e}")
        
        error_detail = parse_error(e, context={
            "topic": topic,
            "session": session
        })
        
        return JSONResponse(
            status_code=500,
            content=error_detail.model_dump()
        )


@router.get("/filter-options")
async def get_filter_options(
    state: str = Query(..., description="State abbreviation (e.g., AL, GA)"),
    topic: Optional[str] = Query(None, description="Topic filter"),
    q: Optional[str] = Query(None, description="Search query")
):
    """
    Get available filter options for a state based on actual data.
    Returns only bill types, chambers, and statuses that exist for the selected state/topic.
    """
    try:
        bills_file = GOLD_DIR / "bills_bills.parquet"
        data_source = get_data_source(bills_file, use_remote=IS_HF_SPACES)
        
        conn = duckdb.connect()
        
        # Build WHERE clause - use state_code for 2-letter codes
        where_conditions = ["state_code = ?"]
        params = [data_source, state]
        
        # Topic filter
        if topic:
            topic_keywords = {
                'fluoride': 'fluorid',
                'dental': 'dental',
                'medicaid': 'medicaid',
                'oral health': 'oral|dental|teeth',
                'health': 'health',
                'education': 'education|school'
            }
            keyword = topic_keywords.get(topic.lower(), topic)
            where_conditions.append(f"REGEXP_MATCHES(LOWER(title), LOWER(?))")
            params.append(keyword)
        
        # Search query
        if q:
            where_conditions.append("(LOWER(title) LIKE ? OR LOWER(bill_number) LIKE ?)")
            search_pattern = f"%{q.lower()}%"
            params.append(search_pattern)
            params.append(search_pattern)
        
        where_clause = " AND ".join(where_conditions)
        
        # Get bill types
        sql_types = f"""
            SELECT 
                CASE 
                    WHEN bill_number LIKE 'HB%' OR bill_number LIKE 'SB%' OR bill_number LIKE 'AB%' THEN 'bill'
                    WHEN bill_number LIKE 'HR%' OR bill_number LIKE 'SR%' OR bill_number LIKE 'AR%' THEN 'resolution'
                    WHEN bill_number LIKE 'HJR%' OR bill_number LIKE 'SJR%' OR bill_number LIKE 'AJR%' THEN 'joint_resolution'
                    WHEN bill_number LIKE 'HCR%' OR bill_number LIKE 'SCR%' THEN 'concurrent_resolution'
                    WHEN bill_number LIKE 'HJM%' OR bill_number LIKE 'SJM%' THEN 'memorial'
                END as bill_type,
                COUNT(*) as count
            FROM read_parquet(?)
            WHERE {where_clause}
            GROUP BY bill_type
            HAVING bill_type IS NOT NULL
            ORDER BY count DESC
        """
        
        type_rows = conn.execute(sql_types, params).fetchall()
        
        # Get chambers
        sql_chambers = f"""
            SELECT 
                CASE 
                    WHEN bill_number LIKE 'HB%' OR bill_number LIKE 'HR%' OR bill_number LIKE 'HJR%' OR 
                         bill_number LIKE 'HCR%' OR bill_number LIKE 'HJM%' OR bill_number LIKE 'H %' THEN 'house'
                    WHEN bill_number LIKE 'SB%' OR bill_number LIKE 'SR%' OR bill_number LIKE 'SJR%' OR 
                         bill_number LIKE 'SCR%' OR bill_number LIKE 'SJM%' OR bill_number LIKE 'S %' THEN 'senate'
                    WHEN bill_number LIKE '%JR%' OR bill_number LIKE '%JM%' THEN 'joint'
                END as chamber,
                COUNT(*) as count
            FROM read_parquet(?)
            WHERE {where_clause}
            GROUP BY chamber
            HAVING chamber IS NOT NULL
            ORDER BY count DESC
        """
        
        chamber_rows = conn.execute(sql_chambers, params).fetchall()
        
        # Get statuses
        sql_statuses = f"""
            SELECT 
                CASE 
                    WHEN LOWER(latest_action) LIKE '%enact%' THEN 'enacted'
                    WHEN LOWER(latest_action) LIKE '%pass%' THEN 'passed'
                    WHEN LOWER(latest_action) LIKE '%adopt%' THEN 'adopted'
                    WHEN LOWER(latest_action) LIKE '%fail%' THEN 'failed'
                    WHEN LOWER(latest_action) LIKE '%introduc%' THEN 'introduced'
                    WHEN LOWER(latest_action) LIKE '%refer%' THEN 'referred'
                    WHEN LOWER(latest_action) LIKE '%report%' THEN 'reported'
                END as status,
                COUNT(*) as count
            FROM read_parquet(?)
            WHERE {where_clause} AND latest_action IS NOT NULL
            GROUP BY status
            HAVING status IS NOT NULL
            ORDER BY count DESC
        """
        
        status_rows = conn.execute(sql_statuses, params).fetchall()
        
        conn.close()
        
        # Map to labels
        type_labels = {
            'bill': 'Bill (HB/SB)',
            'resolution': 'Resolution (HR/SR)',
            'joint_resolution': 'Joint Resolution (HJR/SJR)',
            'concurrent_resolution': 'Concurrent Resolution (HCR/SCR)',
            'memorial': 'Memorial (HJM/SJM)'
        }
        
        chamber_labels = {
            'house': 'House',
            'senate': 'Senate',
            'joint': 'Joint'
        }
        
        status_labels = {
            'enacted': 'Enacted',
            'passed': 'Passed',
            'adopted': 'Adopted',
            'failed': 'Failed',
            'introduced': 'Introduced',
            'referred': 'Referred to Committee',
            'reported': 'Reported from Committee'
        }
        
        return {
            "state": state,
            "topic": topic,
            "bill_types": [
                {"value": row[0], "label": type_labels.get(row[0], row[0]), "count": row[1]}
                for row in type_rows
            ],
            "chambers": [
                {"value": row[0], "label": chamber_labels.get(row[0], row[0]), "count": row[1]}
                for row in chamber_rows
            ],
            "statuses": [
                {"value": row[0], "label": status_labels.get(row[0], row[0]), "count": row[1]}
                for row in status_rows
            ]
        }
        
    except Exception as e:
        logger.error(f"Filter options query error for state={state}: {e}")
        
        error_detail = parse_error(e, context={
            "state": state,
            "topic": topic,
            "q": q
        })
        
        return JSONResponse(
            status_code=500,
            content=error_detail.model_dump()
        )


@router.get("/versions")
async def get_bill_versions(
    bill_id: str = Query(..., description="Bill ID (e.g., ocd-bill/...)")
):
    """
    Get all versions (text versions) for a specific bill.
    Returns different versions like "Introduced", "Engrossed", "Enacted" with document links.
    """
    try:
        versions_file = GOLD_DIR / "bills_versions.parquet"
        
        if not versions_file.exists():
            return {
                "bill_id": bill_id,
                "versions": [],
                "message": "Bill versions data not available"
            }
        
        data_source = get_data_source(versions_file, use_remote=IS_HF_SPACES)
        
        conn = duckdb.connect()
        
        # Fetch versions for this bill
        sql = """
            SELECT 
                version_id,
                bill_id,
                bill_number,
                version_note,
                version_date,
                classification,
                document_url,
                media_type,
                jurisdiction_name,
                session,
                state
            FROM read_parquet(?)
            WHERE bill_id = ?
            ORDER BY version_date DESC NULLS LAST
        """
        
        rows = conn.execute(sql, [data_source, bill_id]).fetchall()
        
        versions = []
        for row in rows:
            versions.append({
                "version_id": row[0],
                "bill_id": row[1],
                "bill_number": row[2],
                "version_note": row[3],
                "version_date": row[4],
                "classification": row[5],
                "document_url": row[6],
                "media_type": row[7],
                "jurisdiction_name": row[8],
                "session": row[9],
                "state": row[10],
            })
        
        conn.close()
        
        return {
            "bill_id": bill_id,
            "total": len(versions),
            "versions": versions
        }
        
    except Exception as e:
        logger.error(f"Bill versions query error for bill_id={bill_id}: {e}")
        
        error_detail = parse_error(e, context={
            "bill_id": bill_id
        })
        
        return JSONResponse(
            status_code=500,
            content=error_detail.model_dump()
        )


@router.get("/{bill_id}")
async def get_bill_details(bill_id: str):
    """
    Get detailed information about a specific bill from gold parquet files.
    
    Args:
        bill_id: Bill identifier in format {state}-{bill_number} (e.g., "mo-SB 1548")
    
    Returns:
        Detailed bill information including actions, sponsors, sources
    
    Examples:
        - `/api/bills/ga-HB 123` - Georgia House Bill 123
        - `/api/bills/mo-SB 1548` - Missouri Senate Bill 1548
    """
    try:
        # Parse bill_id to extract state and bill number
        if '-' not in bill_id:
            raise HTTPException(status_code=400, detail="Invalid bill ID format. Expected: STATE-BILLNUMBER")
        
        parts = bill_id.split('-', 1)
        state = parts[0].upper()
        bill_number = parts[1]
        
        # Use consolidated parquet files in gold directory
        bills_file = GOLD_DIR / "bills_bills.parquet"
        actions_file = GOLD_DIR / "bills_bill_actions.parquet"
        sponsors_file = GOLD_DIR / "bills_bill_sponsorships.parquet"

        # Get data sources (local or remote HuggingFace URL)
        bills_source = get_data_source(bills_file, use_remote=IS_HF_SPACES)
        actions_source = get_data_source(actions_file, use_remote=IS_HF_SPACES)
        sponsors_source = get_data_source(sponsors_file, use_remote=IS_HF_SPACES)
        
        # Connect to DuckDB for querying parquet files
        conn = duckdb.connect()
        
        try:
            # Query for the specific bill in consolidated bills file
            bill_query = """
                SELECT 
                    bill_id,
                    bill_number,
                    title,
                    classification,
                    latest_action,
                    latest_action_date,
                    first_action_date,
                    session,
                    session_name,
                    jurisdiction_name
                FROM read_parquet(?)
                WHERE UPPER(state) = ? AND bill_number = ?
                LIMIT 1
            """
            
            result = conn.execute(bill_query, [bills_source, state, bill_number]).fetchone()
            
            if not result:
                # Try to get sample bill data from map aggregates as fallback
                logger.info(f"Bill {bill_number} not found in detailed data, checking map aggregates...")

                pool = await get_pool()
                async with pool.acquire() as agg_conn:
                    agg_row = await agg_conn.fetchrow(
                        """
                        SELECT sample_bills
                        FROM rpt_bill_map_aggregate
                        WHERE state_code = $1 AND topic = 'all'
                        LIMIT 1
                        """,
                        state,
                    )

                if agg_row and agg_row['sample_bills']:
                    # Search for the bill in sample_bills array
                    sample_bills = agg_row['sample_bills']
                    if isinstance(sample_bills, str):
                        import json
                        sample_bills = json.loads(sample_bills)
                    matching_bill = None
                    for bill in sample_bills:
                        if bill.get('bill_number') == bill_number:
                            matching_bill = bill
                            break
                    
                    if matching_bill:
                        conn.close()
                        # Return limited data from map aggregate
                        return {
                            "bill_id": f"{state.lower()}-{bill_number}",
                            "bill_number": bill_number,
                            "title": matching_bill.get('title', ''),
                            "classification": [matching_bill.get('type', 'bill')],
                            "latest_action": matching_bill.get('action', ''),
                            "latest_action_date": matching_bill.get('date', ''),
                            "first_action_date": matching_bill.get('date', ''),
                            "session": '',
                            "session_name": '',
                            "jurisdiction": state,
                            "state": state,
                            "sponsors": [],
                            "actions": [{
                                "description": matching_bill.get('action', ''),
                                "date": matching_bill.get('date', ''),
                                "classification": []
                            }] if matching_bill.get('action') else [],
                            "sources": [],
                            "limited_data": True,
                            "note": "This bill's full details are not available yet. Only summary information is shown."
                        }
                
                conn.close()
                raise HTTPException(
                    status_code=404, 
                    detail=f"Bill {bill_number} not found in {state}. Full bill data is currently available for: AL, GA, MA, WA, WI."
                )
            
            # Parse bill data
            bill_data = {
                "bill_id": result[0] if result[0] else bill_id,
                "bill_number": result[1],
                "title": result[2],
                "classification": result[3] if result[3] else [],
                "latest_action": result[4],
                "latest_action_date": result[5],
                "first_action_date": result[6],
                "session": result[7],
                "session_name": result[8],
                "jurisdiction": result[9],
                "state": state,
            }
            
            # Get sponsors if available
            try:
                sponsor_query = """
                    SELECT name, primary_sponsor, classification
                    FROM read_parquet(?)
                    WHERE bill_id = ?
                    ORDER BY primary_sponsor DESC
                """
                sponsor_rows = conn.execute(sponsor_query, [sponsors_source, bill_data["bill_id"]]).fetchall()
                
                bill_data["sponsors"] = [
                    {"name": s[0], "primary": bool(s[1]), "classification": s[2]}
                    for s in sponsor_rows
                ]
            except Exception as e:
                logger.warning(f"Could not load sponsors for {bill_id}: {e}")
                bill_data["sponsors"] = []
            
            # Get actions if available
            try:
                actions_query = """
                    SELECT description, date, classification
                    FROM read_parquet(?)
                    WHERE bill_id = ?
                    ORDER BY date DESC
                    LIMIT 10
                """
                action_rows = conn.execute(actions_query, [actions_source, bill_data["bill_id"]]).fetchall()
                
                bill_data["actions"] = [
                    {"description": a[0], "date": a[1], "classification": a[2]}
                    for a in action_rows
                ]
            except Exception as e:
                logger.warning(f"Could not load actions for {bill_id}: {e}")
                bill_data["actions"] = []
            
            conn.close()
            return bill_data
            
        except Exception as e:
            conn.close()
            raise
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bill details error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
