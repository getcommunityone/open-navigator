"""
Bills API Routes - Legislative bill data from OpenStates
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict
import duckdb
import pandas as pd
from pathlib import Path
from loguru import logger
import re
import os
import sys
import traceback

from api.errors import ErrorDetail, parse_error
from api.routes.search import load_parquet_cached

router = APIRouter(prefix="/bills", tags=["bills"])

GOLD_DIR = Path("data/gold")
IS_HF_SPACES = os.getenv("HF_SPACES") == "1"
HF_ORGANIZATION = "CommunityOne"

def get_hf_dataset_url(dataset_name: str) -> str:
    """
    Convert dataset name to HuggingFace parquet URL.
    
    HuggingFace Datasets library stores parquet files in the standard format:
    data/train-00000-of-00001.parquet
    
    Args:
        dataset_name: Dataset name (e.g., 'states-ma-bills-bills')
    
    Returns:
        Full URL to the parquet file
    """
    return f"https://huggingface.co/datasets/{HF_ORGANIZATION}/{dataset_name}/resolve/main/data/train-00000-of-00001.parquet"

def get_data_source(file_path: Path, use_remote: bool = False) -> str:
    """Get data source (local path or remote URL) based on environment."""
    if not IS_HF_SPACES and not use_remote:
        return str(file_path)
    
    # Convert local path to HuggingFace dataset name
    parts = file_path.parts
    
    if 'states' in parts:
        state_idx = parts.index('states')
        state = parts[state_idx + 1].lower()
        filename = parts[-1].replace('.parquet', '').replace('_', '-')
        dataset_name = f"states-{state}-{filename}"
        return get_hf_dataset_url(dataset_name)
    
    # Fallback to local
    return str(file_path)


def classify_bill_type(title: str, classification: list, topic: Optional[str] = None) -> str:
    """
    Classify bill based on topic-specific categories.
    
    Different topics use different classification schemes:
    - Fluoridation: mandate, removal, funding, study
    - Dental/Oral Health: coverage_expansion, screening, provider_access, funding
    - Medicaid: expansion, coverage, reimbursement, eligibility
    - Health (general): protection, restriction, funding, reform
    - Education: requirement, funding, curriculum, reform
    - Default: support, oppose, regulate, other
    """
    title_lower = title.lower()
    topic_lower = topic.lower() if topic else ""
    
    # EXCEPTION: Fluoride varnish/dental coverage bills (not water fluoridation)
    # Check this BEFORE water fluoridation classification
    if any(word in title_lower for word in ['varnish', 'sealant', 'dental', 'medicaid', 'medical assistance']) and 'fluoride' in title_lower:
        if any(word in title_lower for word in ['coverage', 'expand', 'expansion', 'benefit']):
            return 'coverage_expansion'
        elif any(word in title_lower for word in ['screening', 'examination', 'check']):
            return 'screening'
        # If it mentions dental/varnish but unclear type, it's dental "other" not fluoridation
        return 'other'
    
    # Fluoridation-specific classifications (WATER fluoridation only)
    if 'fluoride' in topic_lower or 'fluoride' in title_lower:
        # FIRST: Check for REMOVAL/BAN/PROHIBITION (negative sentiment)
        # CRITICAL: Must check these BEFORE "mandate"/"require" to avoid misclassification
        # e.g., "prohibit fluoride" should be "removal", not "mandate"
        if any(word in title_lower for word in [
            'prohibit', 'prohibition', 'prohibited', 'prohibiting',
            'ban', 'banning', 'banned',
            'discontinue', 'discontinuation',
            'cease', 'ceasing',
            'eliminate', 'elimination',
            'removal', 'remove', 'removing',
            'prevent', 'preventing',
            'repeal', 'repealing', 'repealed',
            'optional', 'opt-out', 'opt out',
            'fluoride-free', 'fluoride free'
        ]):
            # But check if it's "prohibit removal" (double negative = pro-fluoride)
            if any(phrase in title_lower for phrase in ['prohibit removal', 'prevent removal', 'ban removal']):
                return 'mandate'  # Prohibiting removal = mandate to keep
            return 'removal'
        
        # SECOND: Check for notification/monitoring (before "require" check)
        # Bills like "notification required" are about monitoring, not mandating fluoridation
        elif any(phrase in title_lower for phrase in [
            'notification', 'notify', 'notifying',
            'report to', 'reporting', 'report when',
            'monitor', 'monitoring'
        ]):
            return 'study'
        
        # THIRD: Check for MANDATE/REQUIRE (positive sentiment)
        # Be specific - just "require" alone isn't enough, need context
        elif any(phrase in title_lower for phrase in [
            'mandate', 'mandating', 'shall fluoridate', 'shall add fluoride',
            'must fluoridate', 'must add fluoride',
            'require fluoridation', 'require water system to fluoridate',
            'require addition of fluoride'
        ]):
            return 'mandate'
        
        # FOURTH: Check for funding
        elif any(word in title_lower for word in ['fund', 'funding', 'appropriation', 'grant', 'reimburse', 'subsidy']):
            return 'funding'
        elif any(word in title_lower for word in ['study', 'research', 'analysis', 'assess', 'evaluate']):
            return 'study'
        else:
            return 'other'
    
    # Dental/Oral Health-specific classifications
    elif 'dental' in topic_lower or 'oral health' in topic_lower or 'dental' in title_lower:
        if any(word in title_lower for word in ['expand', 'increase coverage', 'extend coverage', 'add coverage']):
            return 'coverage_expansion'
        elif any(word in title_lower for word in ['screen', 'examination', 'checkup', 'assessment']):
            return 'screening'
        elif any(word in title_lower for word in ['provider', 'dentist', 'hygienist', 'workforce', 'professional']):
            return 'provider_access'
        elif any(word in title_lower for word in ['fund', 'appropriation', 'grant', 'budget', 'reimburse']):
            return 'funding'
        else:
            return 'other'
    
    # Medicaid-specific classifications
    elif 'medicaid' in topic_lower or 'medicaid' in title_lower:
        if any(word in title_lower for word in ['expand', 'expansion', 'extend', 'broaden']):
            return 'expansion'
        elif any(word in title_lower for word in ['coverage', 'benefit', 'service']):
            return 'coverage'
        elif any(word in title_lower for word in ['reimburse', 'payment', 'rate', 'compensation']):
            return 'reimbursement'
        elif any(word in title_lower for word in ['eligib', 'qualify', 'enroll']):
            return 'eligibility'
        else:
            return 'other'
    
    # Education-specific classifications
    elif 'education' in topic_lower or 'school' in topic_lower:
        if any(word in title_lower for word in ['require', 'mandate', 'shall provide', 'must offer']):
            return 'requirement'
        elif any(word in title_lower for word in ['fund', 'appropriation', 'grant', 'budget']):
            return 'funding'
        elif any(word in title_lower for word in ['curriculum', 'course', 'instruction', 'program']):
            return 'curriculum'
        elif any(word in title_lower for word in ['reform', 'restructure', 'modernize', 'improve']):
            return 'reform'
        else:
            return 'other'
    
    # General health classifications
    elif 'health' in topic_lower or 'health' in title_lower:
        if any(word in title_lower for word in ['protect', 'preserve', 'safeguard', 'ensure', 'guarantee', 'expand', 'increase', 'enhance', 'support']):
            return 'protection'
        elif any(word in title_lower for word in ['restrict', 'limit', 'regulate', 'control', 'impose', 'prohibit', 'ban']):
            return 'restriction'
        elif any(word in title_lower for word in ['fund', 'appropriation', 'grant', 'budget']):
            return 'funding'
        elif any(word in title_lower for word in ['reform', 'restructure', 'modernize', 'improve']):
            return 'reform'
        else:
            return 'other'
    
    # Default general classifications
    else:
        if any(word in title_lower for word in ['support', 'promote', 'encourage', 'expand', 'increase', 'enhance', 'fund']):
            return 'support'
        elif any(word in title_lower for word in ['oppose', 'prohibit', 'ban', 'restrict', 'limit', 'prevent']):
            return 'oppose'
        elif any(word in title_lower for word in ['regulate', 'oversee', 'control', 'require', 'mandate']):
            return 'regulate'
        else:
            return 'other'


def get_legend_for_topic(topic: Optional[str]) -> dict:
    """
    Get appropriate legend labels based on topic.
    """
    topic_lower = topic.lower() if topic else ""
    
    if 'fluoride' in topic_lower:
        return {
            "mandate": "Mandate Fluoridation",
            "removal": "Remove Fluoridation",
            "funding": "Funding/Grants",
            "study": "Study/Research",
            "other": "Other"
        }
    elif 'dental' in topic_lower or 'oral health' in topic_lower:
        return {
            "coverage_expansion": "Coverage Expansion",
            "screening": "Screening Programs",
            "provider_access": "Provider Access",
            "funding": "Funding/Grants",
            "other": "Other"
        }
    elif 'medicaid' in topic_lower:
        return {
            "expansion": "Program Expansion",
            "coverage": "Coverage/Benefits",
            "reimbursement": "Reimbursement",
            "eligibility": "Eligibility",
            "other": "Other"
        }
    elif 'education' in topic_lower or 'school' in topic_lower:
        return {
            "requirement": "Requirements",
            "funding": "Funding",
            "curriculum": "Curriculum",
            "reform": "Reform",
            "other": "Other"
        }
    elif 'health' in topic_lower:
        return {
            "protection": "Protection/Expansion",
            "restriction": "Restriction",
            "funding": "Funding",
            "reform": "Reform",
            "other": "Other"
        }
    else:
        return {
            "support": "Support/Promote",
            "oppose": "Oppose/Restrict",
            "regulate": "Regulate",
            "other": "Other"
        }


def determine_bill_status(latest_action: str, latest_date: str) -> str:
    """
    Determine if bill was enacted, failed, or is pending.
    """
    if not latest_action:
        return 'pending'
    
    action_lower = latest_action.lower()
    
    # Enacted/Passed
    if any(word in action_lower for word in ['signed', 'enacted', 'approved', 'passed both', 'became law']):
        return 'enacted'
    
    # Failed
    if any(word in action_lower for word in ['failed', 'defeated', 'rejected', 'died', 'withdrawn', 'vetoed']):
        return 'failed'
    
    # Pending (default)
    return 'pending'


@router.get("")
async def search_bills(
    q: Optional[str] = Query(None, description="Search query for bill title or number"),
    state: Optional[str] = Query("AL", description="State code (e.g., AL, GA, MA)"),
    session: Optional[str] = Query(None, description="Legislative session (e.g., 2024rs)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """
    Search legislative bills from OpenStates data.
    
    **Examples:**
    - `/api/bills?state=AL&q=dental` - Search Alabama bills for "dental"
    - `/api/bills?state=AL&session=2024rs` - Get all 2024 regular session bills
    - `/api/bills?state=AL&limit=50` - Browse recent Alabama bills
    """
    try:
        # Build file path
        bills_file = GOLD_DIR / "states" / state / "bills_bills.parquet"
        
        # Get data source (local or remote HuggingFace URL)
        data_source = get_data_source(bills_file, use_remote=IS_HF_SPACES)
        
        # Connect to DuckDB
        conn = duckdb.connect()
        
        # Build SQL query
        where_clauses = []
        params = []
        
        if q:
            where_clauses.append("(LOWER(title) LIKE LOWER(?) OR LOWER(bill_number) LIKE LOWER(?))")
            pattern = f'%{q}%'
            params.extend([pattern, pattern])
        
        if session:
            where_clauses.append("session = ?")
            params.append(session)
        
        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
        
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
                jurisdiction_name
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
                "classification": row[3],
                "session": row[4],
                "session_name": row[5],
                "first_action_date": row[6],
                "latest_action_date": row[7],
                "latest_action": row[8],
                "jurisdiction": row[9]
            })
        
        conn.close()
        
        return {
            "total": total,
            "bills": bills,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(bills) < total
            },
            "filters": {
                "state": state,
                "query": q,
                "session": session
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bills search error for state={state}: {e}")
        
        # Parse error into structured response
        error_detail = parse_error(e, context={
            "state": state,
            "data_type": "bills",
            "query": q,
            "session": session
        })
        
        # Return structured error response
        return JSONResponse(
            status_code=500,
            content=error_detail.model_dump()
        )


@router.get("/sessions")
async def get_sessions(
    state: str = Query("AL", description="State code")
):
    """Get available legislative sessions for a state."""
    try:
        bills_file = GOLD_DIR / "states" / state / "bills_bills.parquet"
        
        if not bills_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No bills data found for state: {state}"
            )
        
        conn = duckdb.connect()
        
        sql = """
            SELECT DISTINCT 
                session,
                session_name,
                MIN(first_action_date) as start_date,
                MAX(latest_action_date) as end_date,
                COUNT(*) as bill_count
            FROM read_parquet(?)
            GROUP BY session, session_name
            ORDER BY session DESC
        """
        
        rows = conn.execute(sql, [str(bills_file)]).fetchall()
        
        sessions = []
        for row in rows:
            sessions.append({
                "session": row[0],
                "session_name": row[1],
                "start_date": row[2],
                "end_date": row[3],
                "bill_count": row[4]
            })
        
        conn.close()
        
        return {
            "state": state,
            "sessions": sessions,
            "total_sessions": len(sessions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sessions query error for state={state}: {e}")
        
        # Parse error into structured response
        error_detail = parse_error(e, context={
            "state": state,
            "data_type": "sessions"
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
    Get aggregated bill data for choropleth map visualization.
    
    Uses pre-computed national aggregates for instant loading.
    Returns counts of bills by type and status for each state.
    
    **Examples:**
    - `/api/bills/map?topic=fluorid` - Map fluoridation legislation
    - `/api/bills/map?topic=dental` - Map dental legislation  
    """
    try:
        # Use pre-aggregated national dataset
        agg_file = GOLD_DIR / "national" / "bill_map_aggregate.parquet"
        
        # Fallback to on-demand aggregation if pre-computed file doesn't exist
        if not agg_file.exists():
            logger.warning("Pre-aggregated bill data not found, using on-demand aggregation (slower)")
            return await get_bill_map_data_on_demand(topic, session)
        
        # Load from cached aggregates (fast!)
        df = load_parquet_cached(str(agg_file))
        
        # Filter by topic
        if topic:
            df = df[df['topic'] == topic.lower()]
        
        # Convert to state_data dict
        state_data = {}
        
        for _, row in df.iterrows():
            state_code = row['state']
            
            # Reconstruct nested dicts (exclude type_status_counts which is already a dict)
            type_cols = [c for c in df.columns if c.startswith('type_') and c != 'type_status_counts']
            status_cols = [c for c in df.columns if c.startswith('status_')]
            
            # Handle NaN values - convert to 0
            type_counts = {c.replace('type_', ''): int(row[c]) if not pd.isna(row[c]) else 0 for c in type_cols}
            status_counts = {c.replace('status_', ''): int(row[c]) if not pd.isna(row[c]) else 0 for c in status_cols}
            
            # Extract sample_bills (stored as numpy array in parquet)
            sample_bills = []
            if 'sample_bills' in row.index:
                bills_data = row['sample_bills']
                # Pandas stores list columns as numpy arrays
                if hasattr(bills_data, '__iter__') and not isinstance(bills_data, str):
                    try:
                        # Convert numpy array or list to Python list
                        sample_bills = [dict(bill) for bill in bills_data if bill]
                    except:
                        sample_bills = []
                elif isinstance(bills_data, str):
                    import json
                    try:
                        sample_bills = json.loads(bills_data)
                    except:
                        sample_bills = []
            
            state_data[state_code] = {
                "state": state_code,
                "total_bills": int(row['total_bills']),
                "type_counts": type_counts,
                "status_counts": status_counts,
                "primary_type": row['primary_type'],
                "primary_status": row['primary_status'],
                "map_category": row['map_category'],
                "sample_bills": sample_bills,
                "last_updated": str(row['last_updated']) if 'last_updated' in row.index else ''
            }
        
        return {
            "topic": topic,
            "session": session,
            "states": state_data,
            "total_states": len(state_data),
            "legend": {
                "types": get_legend_for_topic(topic),
                "statuses": {
                    "enacted": "Enacted",
                    "failed": "Failed",
                    "pending": "Pending"
                }
            },
            "cached": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Map data error: {e}")
        
        error_detail = parse_error(e, context={
            "data_type": "bill map",
            "topic": topic,
            "session": session
        })
        
        return JSONResponse(
            status_code=500,
            content=error_detail.model_dump()
        )


async def get_bill_map_data_on_demand(
    topic: Optional[str] = None,
    session: Optional[str] = None
):
    """
    LEGACY: On-demand aggregation (slow - loads 50 state files).
    Only used as fallback if pre-aggregated data doesn't exist.
    """
    try:
        # List of all US state codes to check
        ALL_STATES = [
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
        ]
        
        # In local environment, check available directories
        # In HF Spaces, try all states (will skip missing datasets)
        states_to_check = ALL_STATES
        if not IS_HF_SPACES:
            states_dir = GOLD_DIR / "states"
            if states_dir.exists():
                states_to_check = [d.name for d in states_dir.iterdir() if d.is_dir()]
        
        state_data = {}
        
        # Iterate through states
        for state_code in states_to_check:
            try:
                bills_file = GOLD_DIR / "states" / state_code / "bills_bills.parquet"
                
                # Get data source (local or remote HuggingFace URL)
                data_source = get_data_source(bills_file, use_remote=IS_HF_SPACES)
                
                # Connect to DuckDB
                conn = duckdb.connect()
                
                # Build query
                where_clauses = ["1=1"]
                params = [data_source]
                
                if topic:
                    where_clauses.append("LOWER(title) LIKE LOWER(?)")
                    params.append(f'%{topic}%')
                
                if session:
                    where_clauses.append("session = ?")
                    params.append(session)
                
                where_clause = " AND ".join(where_clauses)
                
                sql = f"""
                    SELECT 
                        title,
                        classification,
                        latest_action
                    FROM read_parquet(?)
                    WHERE {where_clause}
                """
                
                rows = conn.execute(sql, params).fetchall()
                conn.close()
                
                if not rows:
                    continue
                
                # Get topic-aware categories
                legend_categories = get_legend_for_topic(topic)
                
                # Initialize type_counts with all possible categories for this topic
                type_counts = {cat: 0 for cat in legend_categories.keys()}
                status_counts = {'enacted': 0, 'failed': 0, 'pending': 0}
                type_status_counts = {}
                
                for row in rows:
                    title = row[0]
                    classification = row[1] if row[1] else []
                    latest_action = row[2] if row[2] else ''
                    
                    bill_type = classify_bill_type(title, classification, topic)
                    bill_status = determine_bill_status(latest_action, '')
                    
                    # Ensure bill_type exists in type_counts (fallback to 'other')
                    if bill_type not in type_counts:
                        bill_type = 'other'
                    
                    type_counts[bill_type] += 1
                    status_counts[bill_status] += 1
                    
                    # Track type+status combinations
                    key = f"{bill_type}_{bill_status}"
                    type_status_counts[key] = type_status_counts.get(key, 0) + 1
                
                # Determine primary legislation type and status for map visualization
                primary_type = max(type_counts, key=type_counts.get)
                primary_status = max(status_counts, key=status_counts.get)
                
                state_data[state_code] = {
                    "state": state_code,
                    "total_bills": len(rows),
                    "type_counts": type_counts,
                    "status_counts": status_counts,
                    "type_status_counts": type_status_counts,
                    "primary_type": primary_type,
                    "primary_status": primary_status,
                    # For map visualization
                    "map_category": f"{primary_type}_{primary_status}" if type_counts[primary_type] > 0 else "none"
                }
                
            except Exception as e:
                # Skip states with missing or inaccessible data
                logger.debug(f"Skipping state {state_code}: {str(e)}")
                continue
        
        return {
            "topic": topic,
            "session": session,
            "states": state_data,
            "total_states": len(state_data),
            "legend": {
                "types": get_legend_for_topic(topic),
                "statuses": {
                    "enacted": "Enacted",
                    "failed": "Failed",
                    "pending": "Pending"
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Map data error: {e}")
        
        # Parse error into structured response
        error_detail = parse_error(e, context={
            "data_type": "bill map",
            "topic": topic,
            "session": session
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
        bill_id: Bill identifier in format {state}-{bill_number} (e.g., "LA-SB 4")
    
    Returns:
        Detailed bill information including actions, sponsors, sources
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
        map_file = GOLD_DIR / "bill_map_aggregate.parquet"
        
        # Get data sources (local or remote HuggingFace URL)
        bills_source = get_data_source(bills_file, use_remote=IS_HF_SPACES)
        actions_source = get_data_source(actions_file, use_remote=IS_HF_SPACES)
        sponsors_source = get_data_source(sponsors_file, use_remote=IS_HF_SPACES)
        map_source = get_data_source(map_file, use_remote=IS_HF_SPACES)
        
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
                WHERE UPPER(state_code) = ? AND bill_number = ?
                LIMIT 1
            """
            
            result = conn.execute(bill_query, [bills_source, state, bill_number]).fetchone()
            
            if not result:
                # Try to get sample bill data from map aggregates as fallback
                logger.info(f"Bill {bill_number} not found in detailed data, checking map aggregates...")
                
                map_query = """
                    SELECT sample_bills
                    FROM read_parquet(?)
                    WHERE UPPER(state_code) = ?
                    LIMIT 1
                """
                
                map_result = conn.execute(map_query, [map_source, state]).fetchone()
                
                if map_result and map_result[0]:
                    # Search for the bill in sample_bills array
                    sample_bills = map_result[0]
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
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
