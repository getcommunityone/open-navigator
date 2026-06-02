"""
Unified Search API
LinkedIn-style search across contacts, meetings, organizations, and causes
Uses hybrid approach: PostgreSQL (primary, fast) + HuggingFace Search API + DuckDB (fallback)
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pathlib import Path
import pandas as pd
import duckdb
from loguru import logger
import re
import os
import sys
import requests
from functools import lru_cache
from datetime import datetime, timedelta

from api.errors import ErrorDetail, parse_error

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.utils.calendar_year_util import calendar_year_label

# Import PostgreSQL search functions (primary)
from api.routes import search_postgres

# Import HuggingFace Search helpers
from api.routes.hf_search import (
    search_contacts_hf,
    search_organizations_hf,
    search_jurisdictions_hf,
    is_dataset_indexed
)

router = APIRouter(tags=["search"])

# Paths to gold datasets
GOLD_DIR = Path("data/gold")

# Detect deployment environment
IS_HF_SPACES = os.getenv("HF_SPACES") == "1"
HF_ORGANIZATION = os.getenv('HF_ORGANIZATION', 'CommunityOne')

# Cache for count queries (TTL: 1 hour)
_count_cache = {}
_count_cache_ttl = {}

# In-memory DataFrame cache for HuggingFace datasets (TTL: 5 minutes)
# Reduces remote HTTP requests from 2-3s to <10ms per search
_dataframe_cache: Dict[str, pd.DataFrame] = {}
_dataframe_cache_ttl: Dict[str, datetime] = {}
DATAFRAME_CACHE_TTL = timedelta(minutes=5)

# Every.org API config (fallback only)
EVERYORG_API_KEY = os.getenv('EVERYORG_API_KEY', '')
EVERYORG_API_BASE = "https://partners.every.org/v0.2"


def load_parquet_cached(url: str) -> pd.DataFrame:
    """
    Load parquet file with in-memory caching to avoid repeated HTTP requests.
    
    Cache TTL: 5 minutes (balances speed vs freshness)
    Reduces search latency from 2-3s to <10ms per query.
    
    Args:
        url: URL to parquet file (local path or HuggingFace URL)
    
    Returns:
        pandas DataFrame
    """
    now = datetime.now()
    
    # Check cache
    if url in _dataframe_cache:
        cache_time = _dataframe_cache_ttl.get(url)
        if cache_time and (now - cache_time) < DATAFRAME_CACHE_TTL:
            logger.debug(f"🚀 Cache hit for {url}")
            return _dataframe_cache[url]
    
    # Cache miss - load from source
    logger.info(f"📥 Loading parquet from {url}")
    df = pd.read_parquet(url)
    
    # Store in cache
    _dataframe_cache[url] = df
    _dataframe_cache_ttl[url] = now
    logger.debug(f"💾 Cached {len(df)} rows from {url}")
    
    return df


def get_hf_dataset_url(dataset_name: str) -> str:
    """
    Convert dataset name to HuggingFace parquet URL.
    
    HuggingFace Datasets library stores parquet files in the standard format:
    data/train-00000-of-00001.parquet
    
    Examples:
        states-ma-contacts-local-officials -> 
            https://huggingface.co/datasets/CommunityOne/states-ma-contacts-local-officials/resolve/main/data/train-00000-of-00001.parquet
    """
    return f"https://huggingface.co/datasets/{HF_ORGANIZATION}/{dataset_name}/resolve/main/data/train-00000-of-00001.parquet"


def get_data_source(file_path: Path, use_remote: bool = False) -> str:
    """
    Get data source (local path or remote URL) based on environment.
    
    Args:
        file_path: Local file path (e.g., data/gold/states/MA/contacts_local_officials.parquet)
        use_remote: Force remote URL even in local environment
    
    Returns:
        File path string (local) or HuggingFace URL (remote)
    """
    if not IS_HF_SPACES and not use_remote:
        return str(file_path)
    
    # Convert local path to HuggingFace dataset name
    # data/gold/states/MA/contacts_local_officials.parquet -> states-ma-contacts-local-officials
    parts = file_path.parts
    
    if 'states' in parts:
        state_idx = parts.index('states')
        state = parts[state_idx + 1].lower()
        filename = parts[-1].replace('.parquet', '').replace('_', '-')
        dataset_name = f"states-{state}-{filename}"
    elif 'national' in parts:
        filename = parts[-1].replace('.parquet', '').replace('_', '-')
        dataset_name = f"national-{filename}"
    elif 'reference' in parts:
        filename = parts[-1].replace('.parquet', '').replace('_', '-')
        dataset_name = f"reference-{filename}"
    else:
        # Fallback to local
        return str(file_path)
    
    return get_hf_dataset_url(dataset_name)


@lru_cache(maxsize=5000)
def fetch_form990_data(ein: str) -> Optional[Dict[str, Any]]:
    """
    Fetch enrichment data from ProPublica Nonprofit Explorer (FREE!)
    Uses their API to get website and mission from Form 990 filings
    """
    if not ein:
        return None
    
    try:
        clean_ein = str(ein).replace('-', '').zfill(9)
        url = f"https://projects.propublica.org/nonprofits/api/v2/organizations/{clean_ein}.json"
        
        response = requests.get(url, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            org = data.get('organization', {})
            filings = data.get('filings_with_data', [])
            
            # Get most recent filing data
            website = None
            mission = None
            
            if filings:
                # ProPublica provides website from most recent filing
                latest = filings[0]
                # Note: ProPublica API doesn't directly expose website field
                # but we can use their organization name and data as fallback
                pass
            
            return {
                'website': website,  # ProPublica doesn't expose this in API
                'mission': None,  # Would need to parse PDF
                'source': 'propublica',
                'last_updated': datetime.now().isoformat(),
                'tax_year': calendar_year_label(filings[0].get('tax_prd_yr')) if filings else None
            }
    except Exception as e:
        logger.debug(f"ProPublica lookup failed for EIN {ein}: {e}")
    
    return None


@lru_cache(maxsize=5000)
def fetch_everyorg_data(ein: str) -> Optional[Dict[str, Any]]:
    """Fetch enrichment data from Every.org API (cached) - FALLBACK ONLY"""
    if not EVERYORG_API_KEY or not ein:
        return None
    
    try:
        # Format EIN (remove dashes, ensure 9 digits)
        clean_ein = str(ein).replace('-', '').zfill(9)
        
        url = f"{EVERYORG_API_BASE}/nonprofit/{clean_ein}"
        headers = {
            "Authorization": f"Bearer {EVERYORG_API_KEY}",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            if data and 'data' in data and 'nonprofit' in data['data']:
                nonprofit = data['data']['nonprofit']
                tags = data['data'].get('nonprofitTags', [])
                causes = [tag.get('tagName') for tag in tags if tag.get('tagName')]
                
                return {
                    'mission': nonprofit.get('description') or nonprofit.get('descriptionLong'),
                    'website': nonprofit.get('websiteUrl'),
                    'logo_url': nonprofit.get('logoUrl'),
                    'profile_url': nonprofit.get('profileUrl'),
                    'causes': causes[:5],  # Limit to top 5 causes
                    'source': 'everyorg',
                    'last_updated': datetime.now().isoformat()
                }
    except Exception as e:
        logger.debug(f"Every.org lookup failed for EIN {ein}: {e}")
    
    return None


def get_enrichment_data(ein: str, existing_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Get enrichment data with intelligent backfill strategy
    
    Priority:
    1. Existing form_990_* data (if recent)
    2. GivingTuesday 990 XML (future: direct S3 access)
    3. ProPublica API (current fallback)
    4. Every.org API (last resort)
    
    Tracks source and update time for incremental processing
    """
    result = {
        'website': None,
        'mission': None,
        'logo_url': None,
        'profile_url': None,
        'causes': [],
        'data_sources': []
    }
    
    # Check existing data first (skip if older than 30 days)
    if existing_data:
        cutoff_date = datetime.now() - timedelta(days=30)
        
        # Check enrichment data (from any source: form_990, bigquery, etc.)
        if existing_data.get('enrichment_website'):
            last_updated = existing_data.get('enrichment_last_updated')
            if not last_updated or (isinstance(last_updated, str) and datetime.fromisoformat(last_updated) > cutoff_date):
                result['website'] = existing_data['enrichment_website']
                result['data_sources'].append('cached')
        
        if existing_data.get('enrichment_mission'):
            result['mission'] = existing_data['enrichment_mission']
            if 'cached' not in result['data_sources']:
                result['data_sources'].append('cached')
    
    # Try Every.org for missing fields (keeps logo and causes which 990 doesn't have)
    if not result['website'] or not result['mission']:
        everyorg_data = fetch_everyorg_data(ein)
        if everyorg_data:
            if not result['website'] and everyorg_data.get('website'):
                result['website'] = everyorg_data['website']
                result['data_sources'].append('everyorg')
            
            if not result['mission'] and everyorg_data.get('mission'):
                result['mission'] = everyorg_data['mission']
                result['data_sources'].append('everyorg')
            
            # Always get logo and causes from Every.org
            result['logo_url'] = everyorg_data.get('logo_url')
            result['profile_url'] = everyorg_data.get('profile_url')
            result['causes'] = everyorg_data.get('causes', [])
            if result['logo_url'] or result['causes']:
                if 'everyorg' not in result['data_sources']:
                    result['data_sources'].append('everyorg')
    
    return result

class SearchResult:
    """Unified search result"""
    
    def __init__(self, 
                 result_type: str,
                 title: str,
                 subtitle: str,
                 description: str,
                 url: str,
                 score: float,
                 metadata: Dict[str, Any]):
        self.result_type = result_type
        self.title = title
        self.subtitle = subtitle
        self.description = description
        self.url = url
        self.score = score
        self.metadata = metadata
    
    def to_dict(self):
        return {
            "type": self.result_type,
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "url": self.url,
            "score": self.score,
            "metadata": self.metadata
        }


def convert_pg_result(pg_result: search_postgres.SearchResult) -> 'SearchResult':
    """Convert PostgreSQL SearchResult dataclass to SearchResult class"""
    return SearchResult(
        result_type=pg_result.result_type,
        title=pg_result.title,
        subtitle=pg_result.subtitle,
        description=pg_result.description,
        url=pg_result.url,
        score=pg_result.score,
        metadata=pg_result.metadata
    )


def calculate_relevance_score(text: str, query: str) -> float:
    """Calculate relevance score for text matching query"""
    if not text or not query:
        return 0.0
    
    text_lower = text.lower()
    query_lower = query.lower()
    
    # Exact match gets highest score
    if query_lower in text_lower:
        score = 1.0
        # Boost if it's at the start
        if text_lower.startswith(query_lower):
            score += 0.5
        return min(score, 2.0)
    
    # Partial word matches
    query_words = query_lower.split()
    text_words = text_lower.split()
    
    matches = sum(1 for qw in query_words if any(qw in tw for tw in text_words))
    return matches / len(query_words) if query_words else 0.0


def search_contacts_duckdb(query: str, state: Optional[str] = None, limit: int = 10) -> List[SearchResult]:
    """
    Search contacts using DuckDB (supports local files or remote HTTP parquet).
    This is the fallback when HF Search API is unavailable.
    Supports browse mode when query is empty.
    """
    results = []
    
    # Determine if this is browse mode (no query) or search mode
    is_browse_mode = not query or query.strip() == ''
    
    try:
        # Initialize DuckDB connection
        conn = duckdb.connect()
        
        # Search 1: State Officials (OpenStates - state legislators, mayors, etc.)
        if state:
            officials_file_path = GOLD_DIR / "states" / state / "contact_official.parquet"
            officials_file_paths = [officials_file_path]
        else:
            officials_file_paths = list(GOLD_DIR.glob("states/*/contact_official.parquet"))[:5]
        
        logger.info(f"Searching {len(officials_file_paths)} state official contact files (OpenStates) - browse_mode={is_browse_mode}")
        
        for file_path in officials_file_paths:
            if not file_path.exists():
                continue
                
            # Get data source (local or remote URL)
            data_source = get_data_source(file_path, use_remote=IS_HF_SPACES)
            
            try:
                if is_browse_mode:
                    # Browse mode: return all officials, prioritize mayors
                    sql = """
                        SELECT 
                            full_name as name,
                            role_type as title,
                            city_jurisdiction as jurisdiction,
                            state,
                            email,
                            phone,
                            CASE 
                                WHEN LOWER(role_type) = 'mayor' THEN 2.0
                                WHEN LOWER(role_type) LIKE '%council%' THEN 1.8
                                WHEN LOWER(role_type) LIKE '%commission%' THEN 1.7
                                ELSE 1.5
                            END as score
                        FROM read_parquet(?)
                        ORDER BY score DESC, full_name ASC
                        LIMIT ?
                    """
                    
                    rows = conn.execute(sql, [data_source, limit]).fetchall()
                else:
                    # Search mode: relevance scoring
                    sql = """
                        SELECT 
                            full_name as name,
                            role_type as title,
                            city_jurisdiction as jurisdiction,
                            state,
                            email,
                            phone,
                            GREATEST(
                                CASE 
                                    WHEN LOWER(full_name) LIKE LOWER(?) THEN 1.5
                                    WHEN LOWER(full_name) LIKE LOWER(?) THEN 1.0
                                    ELSE 0.0
                                END,
                                CASE 
                                    WHEN LOWER(role_type) LIKE LOWER(?) THEN 1.5
                                    WHEN LOWER(role_type) LIKE LOWER(?) THEN 1.0
                                    ELSE 0.0
                                END,
                                CASE 
                                    WHEN LOWER(city_jurisdiction) LIKE LOWER(?) THEN 1.5
                                    WHEN LOWER(city_jurisdiction) LIKE LOWER(?) THEN 1.0
                                    ELSE 0.0
                                END,
                                CASE 
                                    WHEN LOWER(jurisdiction_name) LIKE LOWER(?) THEN 1.5
                                    WHEN LOWER(jurisdiction_name) LIKE LOWER(?) THEN 1.0
                                    ELSE 0.0
                                END
                            ) as score
                        FROM read_parquet(?)
                        WHERE LOWER(full_name) LIKE LOWER(?) 
                           OR LOWER(role_type) LIKE LOWER(?) 
                           OR LOWER(city_jurisdiction) LIKE LOWER(?)
                           OR LOWER(jurisdiction_name) LIKE LOWER(?)
                        ORDER BY score DESC
                        LIMIT ?
                    """
                    
                    query_pattern = f'%{query}%'
                    query_start = f'{query}%'
                    
                    rows = conn.execute(sql, [
                        query_start, query_pattern,  # name scoring
                        query_start, query_pattern,  # role_type scoring
                        query_start, query_pattern,  # city_jurisdiction scoring
                        query_start, query_pattern,  # jurisdiction_name scoring
                        data_source,                 # file path or URL
                        query_pattern, query_pattern, query_pattern, query_pattern,  # WHERE clause
                        limit
                    ]).fetchall()
                
                # Convert to SearchResult objects
                for row in rows:
                    name, title, jurisdiction, state_code, email, phone, score = row
                    
                    if score > 0.3:  # Relevance threshold
                        contact_info = []
                        if email:
                            contact_info.append(f"📧 {email}")
                        if phone:
                            contact_info.append(f"📞 {phone}")
                        
                        description = f"State official in {jurisdiction}" if jurisdiction else f"State official in {state_code}"
                        if contact_info:
                            description += f" • {' • '.join(contact_info)}"
                        
                        results.append(SearchResult(
                            result_type="contact",
                            title=name if name else "Unknown",
                            subtitle=f"{title.title() if title else 'Official'} - {jurisdiction or state_code}",
                            description=description,
                            url=f"/people/{name.replace(' ', '-') if name else 'unknown'}",
                            score=score,
                            metadata={
                                "title": title,
                                "jurisdiction": jurisdiction,
                                "state": state_code,
                                "name": name,
                                "email": email,
                                "phone": phone,
                                "contact_type": "state_official",
                                "data_source": "OpenStates"
                            }
                        ))
                
            except Exception as e:
                logger.debug(f"Error searching state officials {file_path}: {e}")
        
        # Search 2: Local Officials (from meeting transcripts)
        if state:
            local_file_path = GOLD_DIR / "states" / state / "contacts_local_officials.parquet"
            local_file_paths = [local_file_path]
        else:
            local_file_paths = list(GOLD_DIR.glob("states/*/contacts_local_officials.parquet"))[:5]
        
        logger.info(f"Searching {len(local_file_paths)} local official contact files (meeting transcripts)")
        
        for file_path in local_file_paths:
            # Get data source (local or remote URL)
            data_source = get_data_source(file_path, use_remote=IS_HF_SPACES)
            
            try:
                # SQL query with relevance scoring across name, title, jurisdiction
                sql = """
                    SELECT 
                        name,
                        title,
                        jurisdiction,
                        state,
                        GREATEST(
                            CASE 
                                WHEN LOWER(name) LIKE LOWER(?) THEN 1.5
                                WHEN LOWER(name) LIKE LOWER(?) THEN 1.0
                                ELSE 0.0
                            END,
                            CASE 
                                WHEN LOWER(title) LIKE LOWER(?) THEN 1.5
                                WHEN LOWER(title) LIKE LOWER(?) THEN 1.0
                                ELSE 0.0
                            END,
                            CASE 
                                WHEN LOWER(jurisdiction) LIKE LOWER(?) THEN 1.5
                                WHEN LOWER(jurisdiction) LIKE LOWER(?) THEN 1.0
                                ELSE 0.0
                            END
                        ) as score
                    FROM read_parquet(?)
                    WHERE LOWER(name) LIKE LOWER(?) 
                       OR LOWER(title) LIKE LOWER(?) 
                       OR LOWER(jurisdiction) LIKE LOWER(?)
                    ORDER BY score DESC
                    LIMIT ?
                """
                
                query_pattern = f'%{query}%'
                query_start = f'{query}%'
                
                rows = conn.execute(sql, [
                    query_start, query_pattern,  # name scoring
                    query_start, query_pattern,  # title scoring
                    query_start, query_pattern,  # jurisdiction scoring
                    data_source,                 # file path or URL
                    query_pattern, query_pattern, query_pattern,  # WHERE clause
                    limit
                ]).fetchall()
                
                # Convert to SearchResult objects
                for row in rows:
                    name, title, jurisdiction, state_code, score = row
                    
                    if score > 0.3:  # Relevance threshold
                        results.append(SearchResult(
                            result_type="contact",
                            title=name if name else "Unknown",
                            subtitle=f"{title} - {jurisdiction}, {state_code}",
                            description=f"Local official in {jurisdiction}",
                            url=f"/people/{name.replace(' ', '-') if name else 'unknown'}",
                            score=score,
                            metadata={
                                "title": title,
                                "jurisdiction": jurisdiction,
                                "state": state_code,
                                "name": name
                            }
                        ))
                
            except Exception as e:
                logger.debug(f"Error searching {file_path}: {e}")
        
        # Search 3: Nonprofit Officers from state directories
        nonprofit_files = []
        
        # If state specified, search that state's directory
        if state:
            state_nonprofit_file = GOLD_DIR / "states" / state / "contacts_nonprofit_officers.parquet"
            nonprofit_files.append(state_nonprofit_file)
        else:
            # Search all state directories
            for state_dir in (GOLD_DIR / "states").glob("*/"):
                state_file = state_dir / "contacts_nonprofit_officers.parquet"
                nonprofit_files.append(state_file)
        
        for nonprofit_file in nonprofit_files:
            # Get data source (local or remote URL)
            nonprofit_source = get_data_source(nonprofit_file, use_remote=IS_HF_SPACES)
            
            try:
                logger.info(f"Searching nonprofit officers: {nonprofit_source}")
                
                officer_sql = """
                    SELECT 
                        name,
                        title,
                        organization_name,
                        city,
                        state,
                        compensation,
                        GREATEST(
                            CASE 
                                WHEN LOWER(name) LIKE LOWER(?) THEN 1.5
                                WHEN LOWER(name) LIKE LOWER(?) THEN 1.0
                                ELSE 0.0
                            END,
                            CASE 
                                WHEN LOWER(title) LIKE LOWER(?) THEN 1.0
                                WHEN LOWER(title) LIKE LOWER(?) THEN 0.5
                                ELSE 0.0
                            END,
                            CASE 
                                WHEN LOWER(organization_name) LIKE LOWER(?) THEN 1.0
                                WHEN LOWER(organization_name) LIKE LOWER(?) THEN 0.5
                                ELSE 0.0
                            END
                        ) AS score
                    FROM read_parquet(?)
                    WHERE (LOWER(name) LIKE LOWER(?) 
                       OR LOWER(title) LIKE LOWER(?) 
                       OR LOWER(organization_name) LIKE LOWER(?))
                """
                
                query_pattern = f'%{query}%'
                query_start = f'{query}%'
                params = [
                    query_start, query_pattern,  # name scoring
                    query_start, query_pattern,  # title scoring  
                    query_start, query_pattern,  # organization scoring
                    nonprofit_source,            # file path or URL
                    query_pattern, query_pattern, query_pattern  # WHERE clause
                ]
                
                if state:
                    officer_sql += " AND LOWER(state) = LOWER(?)"
                    params.append(state)
                
                officer_sql += " ORDER BY score DESC, compensation DESC NULLS LAST LIMIT ?"
                params.append(limit)
                
                officer_rows = conn.execute(officer_sql, params).fetchall()
                
                for row in officer_rows:
                    name, title, org_name, city, state_code, compensation, score = row
                    
                    if score > 0.3:
                        comp_text = f" (${compensation:,.0f})" if compensation else ""
                        
                        results.append(SearchResult(
                            result_type="contact",
                            title=name if name else "Unknown",
                            subtitle=f"{title} - {org_name}{comp_text}",
                            description=f"Nonprofit officer in {city}, {state_code}",
                            url=f"/nonprofits?name={org_name.replace(' ', '-') if org_name else 'unknown'}",
                            score=score,
                            metadata={
                                "title": title,
                                "organization": org_name,
                                "city": city,
                                "state": state_code,
                                "compensation": compensation,
                                "contact_type": "nonprofit_officer"
                            }
                        ))
                
                logger.info(f"Found {len([r for r in results if r.metadata.get('contact_type') == 'nonprofit_officer'])} nonprofit officer results")
                
            except Exception as e:
                logger.debug(f"Error searching nonprofit officers: {e}")
        
        conn.close()
        
        # Sort all results by score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        logger.info(f"DuckDB search found {len(results)} contacts for query '{query}'")
        return results[:limit]
    
    except Exception as e:
        logger.error(f"Contact search error: {e}")
        return results


def search_contacts(query: str, state: Optional[str] = None, limit: int = 10) -> List[SearchResult]:
    """
    HYBRID SEARCH: Search local officials AND nonprofit officers.
    
    Strategy:
    1. Try HuggingFace Search API first (fast, server-side indexed) - HF Spaces only
    2. Fall back to DuckDB (local files or remote HTTP parquet)
    
    Args:
        query: Search text (name, title, organization, etc.)
        state: Optional 2-letter state code filter
        limit: Maximum results to return
    
    Returns:
        List of SearchResult objects sorted by relevance
    """
    logger.info(f"🔎 search_contacts() called - query={query!r}, state={state!r}, limit={limit}, IS_HF_SPACES={IS_HF_SPACES}")
    
    # STRATEGY 1: Try HuggingFace Search API (fast text search)
    if query and IS_HF_SPACES:
        logger.info(f"🔍 Trying HF Search API for '{query}' (state={state})")
        try:
            hf_results = search_contacts_hf(query, state, limit=limit)
            
            if hf_results:
                logger.info(f"✅ HF Search API returned {len(hf_results)} results")
                # Convert HF results to SearchResult objects
                results = []
                for row in hf_results:
                    source_type = row.get('source', 'contact')
                    name = row.get('name', 'Unknown')
                    title = row.get('title', '')
                    jurisdiction = row.get('jurisdiction', row.get('organization_name', ''))
                    state_code = row.get('state', state or '')
                    
                    results.append(SearchResult(
                        result_type="contact",
                        title=name,
                        subtitle=f"{title} - {jurisdiction}, {state_code}",
                        description=f"{'Local official' if source_type == 'local_officials' else 'Nonprofit officer'} in {jurisdiction}",
                        url=f"/people/{name.replace(' ', '-')}",
                        score=1.0,
                        metadata={
                            "title": title,
                            "jurisdiction": jurisdiction,
                            "state": state_code,
                            "name": name,
                            "source": source_type
                        }
                    ))
                return results[:limit]
        except Exception as e:
            logger.warning(f"HF Search API failed, falling back to DuckDB: {e}")
    
    # STRATEGY 2: Fall back to DuckDB (works with local or remote parquet)
    logger.info(f"🔍 Using DuckDB {'remote' if IS_HF_SPACES else 'local'} search for '{query}'")
    return search_contacts_duckdb(query, state, limit)


def search_meetings(query: str, state: Optional[str] = None, limit: int = 10) -> List[SearchResult]:
    """Search meeting transcripts and agendas"""
    results = []
    
    try:
        # Search state event/meeting files (try new naming first, fallback to old)
        if state:
            meeting_files = list(GOLD_DIR.glob(f"states/{state}/events.parquet"))
            if not meeting_files:
                meeting_files = list(GOLD_DIR.glob(f"states/{state}/events_events.parquet"))
            if not meeting_files:
                meeting_files = list(GOLD_DIR.glob(f"states/{state}/meetings.parquet"))
        else:
            meeting_files = list(GOLD_DIR.glob("states/*/events.parquet"))
            if not meeting_files:
                meeting_files = list(GOLD_DIR.glob("states/*/events_events.parquet"))
            if not meeting_files:
                meeting_files = list(GOLD_DIR.glob("states/*/meetings.parquet"))
        
        for file_path in meeting_files[:5]:  # Limit for performance
            try:
                df = pd.read_parquet(file_path)
                state_code = file_path.parent.name
                
                # Detect schema - different files have different column names
                columns = set(df.columns)
                
                # Map column names (handle LocalView vs CityScrapers vs other formats)
                title_col = 'vid_title' if 'vid_title' in columns else ('event_title' if 'event_title' in columns else 'title')
                body_col = 'caption_text_clean' if 'caption_text_clean' in columns else ('caption_text' if 'caption_text' in columns else ('full_text' if 'full_text' in columns else 'body'))
                jurisdiction_col = 'place_name' if 'place_name' in columns else ('jurisdiction_name' if 'jurisdiction_name' in columns else 'jurisdiction')
                date_col = 'meeting_date' if 'meeting_date' in columns else 'date'
                id_col = 'vid_id' if 'vid_id' in columns else ('meeting_id' if 'meeting_id' in columns else 'id')
                
                # Search in title, body, jurisdiction
                for _, row in df.iterrows():
                    title = str(row.get(title_col, ''))
                    body = str(row.get(body_col, ''))[:500]  # First 500 chars
                    jurisdiction = str(row.get(jurisdiction_col, ''))
                    meeting_date = str(row.get(date_col, ''))
                    meeting_id = str(row.get(id_col, ''))
                    
                    score = max(
                        calculate_relevance_score(title, query),
                        calculate_relevance_score(body, query) * 0.8,  # Body matches slightly lower
                        calculate_relevance_score(jurisdiction, query) * 0.6
                    )
                    
                    if score > 0.3:
                        # Extract snippet around query
                        snippet = body[:200] + "..." if len(body) > 200 else body
                        
                        results.append(SearchResult(
                            result_type="meeting",
                            title=title,
                            subtitle=f"{jurisdiction}, {state_code} - {meeting_date}",
                            description=snippet,
                            url=f"/documents?meeting_id={meeting_id}",
                            score=score,
                            metadata={
                                "jurisdiction": jurisdiction,
                                "state": state_code,
                                "date": meeting_date,
                                "meeting_id": meeting_id
                            }
                        ))
            except Exception as e:
                logger.debug(f"Error searching {file_path}: {e}")
    
    except Exception as e:
        logger.error(f"Meeting search error: {e}")
    
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]


def count_organizations(state: Optional[str] = None, ntee_code: Optional[str] = None, query: Optional[str] = None) -> int:
    """Count total organizations matching criteria (for pagination) - cached"""
    # Create cache key
    cache_key = f"count_{state}_{ntee_code}_{query}"
    
    # Check cache (1 hour TTL)
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]
    
    try:
        # Determine file path
        if state:
            file_pattern = f"{GOLD_DIR}/states/{state}/nonprofits_organizations.parquet"
        else:
            file_pattern = f"{GOLD_DIR}/national/nonprofits_organizations.parquet"
        
        file_path = Path(file_pattern)
        if not file_path.exists():
            return 0
        
        conn = duckdb.connect()
        
        # Detect schema
        columns_query = f"DESCRIBE SELECT * FROM '{file_path}' LIMIT 0"
        available_columns = set([row[0] for row in conn.execute(columns_query).fetchall()])
        name_col = 'organization_name' if 'organization_name' in available_columns else 'name'
        ntee_col = 'ntee_code' if 'ntee_code' in available_columns else 'ntee_cd'
        
        # Build WHERE clause
        where_clauses = []
        params = []
        
        if query and query.strip():
            where_clauses.append(f"LOWER({name_col}) LIKE LOWER(?)")
            params.append(f'%{query}%')
        
        if ntee_code and ntee_col in available_columns:
            where_clauses.append(f"{ntee_col} LIKE ?")
            params.append(f'{ntee_code}%')
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        
        # Count query
        count_sql = f"SELECT COUNT(*) FROM '{data_source}' WHERE {where_sql}"
        result = conn.execute(count_sql, params).fetchone()
        conn.close()
        
        count = result[0] if result else 0
        
        # Cache the result
        _count_cache[cache_key] = count
        _count_cache_ttl[cache_key] = now
        
        return count
    except Exception as e:
        logger.error(f"Count error: {e}")
        return 0


def search_organizations(query: str, state: Optional[str] = None, ntee_code: Optional[str] = None, limit: int = 10, offset: int = 0, enrich: bool = False, sort: str = 'relevance', ein: Optional[str] = None) -> List[SearchResult]:
    """Search nonprofit organizations using DuckDB for fast Parquet queries
    
    Args:
        enrich: If True, fetch additional data from Every.org API (slower)
        sort: Sort order - 'relevance', 'name-asc', 'name-desc', 'revenue-asc', 'revenue-desc', 'assets-asc', 'assets-desc'
        ein: If provided, filter to exact EIN match (for direct organization links)
    """
    results = []
    
    try:
        # Determine file path
        if state:
            file_pattern = f"{GOLD_DIR}/states/{state}/nonprofits_organizations.parquet"
        else:
            file_pattern = f"{GOLD_DIR}/national/nonprofits_organizations.parquet"
        
        # Get data source (local or remote HuggingFace URL)
        file_path = Path(file_pattern)
        data_source = get_data_source(file_path, use_remote=IS_HF_SPACES)
        
        # Load parquet with caching (speeds up from 2-3s to <10ms)
        df = load_parquet_cached(data_source)
        
        # Initialize DuckDB connection
        conn = duckdb.connect()
        
        # Query the DataFrame directly (DuckDB can query pandas DataFrames)
        available_columns = set(df.columns)
        
        # Detect column name variations (handle different schemas)
        name_col = 'organization_name' if 'organization_name' in available_columns else 'name'
        ntee_col = 'ntee_code' if 'ntee_code' in available_columns else 'ntee_cd'
        revenue_col = 'form_990_total_revenue' if 'form_990_total_revenue' in available_columns else 'revenue_amt'
        asset_col = 'form_990_total_assets' if 'form_990_total_assets' in available_columns else 'asset_amt'
        income_col = 'form_990_net_income' if 'form_990_net_income' in available_columns else 'income_amt'
        
        # Build WHERE clauses using detected column names
        where_clauses = []
        params = []
        
        # EIN filter (exact match - highest priority for direct organization links)
        if ein and ein.strip():
            where_clauses.append("ein = ?")
            params.append(ein.strip())
        
        # Search query (case-insensitive LIKE) - only if query provided and no EIN
        if query and query.strip() and not ein:
            where_clauses.append(f"LOWER({name_col}) LIKE LOWER(?)")
            params.append(f'%{query}%')
        
        # State filter (if using national file) - use state_code for 2-letter codes
        if state and not file_pattern.startswith(f"{GOLD_DIR}/states/"):
            where_clauses.append("state_code = ?")
            params.append(state)
        
        # NTEE code filter
        if ntee_code and ntee_col in available_columns:
            where_clauses.append(f"{ntee_col} LIKE ?")
            params.append(f'{ntee_code}%')
        
        # Default to TRUE if no filters (browse all)
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        
        # Build column list with proper NULL handling for missing columns
        select_columns = []
        
        # Add core columns (with aliases for consistency)
        select_columns.append(f'{name_col} as name')
        select_columns.append('city')
        select_columns.append('state')
        select_columns.append(f'{ntee_col} as ntee_cd' if ntee_col in available_columns else 'NULL as ntee_cd')
        select_columns.append('ein')
        select_columns.append(f'{revenue_col} as revenue_amt' if revenue_col in available_columns else 'NULL as revenue_amt')
        select_columns.append(f'{asset_col} as asset_amt' if asset_col in available_columns else 'NULL as asset_amt')
        select_columns.append(f'{income_col} as income_amt' if income_col in available_columns else 'NULL as income_amt')
        select_columns.append('tax_period' if 'tax_period' in available_columns else 'NULL as tax_period')
        
        # Track enrichment columns (form_990 and bigquery)
        enrichment_cols = []
        enrichment_col_map = {}
        
        # Check for website columns (multiple possible names) - ALWAYS add if exists
        website_col_added = False
        for col_name in ['bigquery_website', 'form_990_website', 'website', 'everyorg_website']:
            if col_name in available_columns:
                select_columns.append(f'{col_name} as enrichment_website')
                enrichment_cols.append('enrichment_website')
                enrichment_col_map['enrichment_website'] = col_name
                website_col_added = True
                logger.debug(f"Added website column: {col_name}")
                break
        
        # Check for mission columns
        mission_col_added = False
        for col_name in ['bigquery_mission', 'form_990_mission', 'mission', 'everyorg_mission']:
            if col_name in available_columns:
                select_columns.append(f'{col_name} as enrichment_mission')
                enrichment_cols.append('enrichment_mission')
                enrichment_col_map['enrichment_mission'] = col_name
                mission_col_added = True
                logger.debug(f"Added mission column: {col_name}")
                break
        
        # Check for logo columns
        logo_col_added = False
        for col_name in ['logodev_logo_url', 'everyorg_logo_url', 'logo_url']:
            if col_name in available_columns:
                select_columns.append(f'{col_name} as enrichment_logo')
                enrichment_cols.append('enrichment_logo')
                enrichment_col_map['enrichment_logo'] = col_name
                logo_col_added = True
                logger.debug(f"Added logo column: {col_name}")
                break
        
        # Last updated timestamp
        for col_name in ['bigquery_updated_date', 'form_990_last_updated', 'everyorg_last_updated']:
            if col_name in available_columns:
                select_columns.append(f'{col_name} as enrichment_last_updated')
                enrichment_cols.append('enrichment_last_updated')
                enrichment_col_map['enrichment_last_updated'] = col_name
                logger.debug(f"Added timestamp column: {col_name}")
                break
        
        columns_sql = ', '.join(select_columns)
        
        # Log what we're selecting
        logger.info(f"🔍 Enrichment columns to select: {enrichment_cols}")
        logger.info(f"📋 Full SQL columns: {columns_sql}")
        
        # Build ORDER BY clause based on sort parameter
        order_by_clauses = []
        
        if sort == 'name-asc':
            order_by_clauses.append(f"{name_col} ASC")
        elif sort == 'name-desc':
            order_by_clauses.append(f"{name_col} DESC")
        elif sort == 'revenue-desc':
            order_by_clauses.append(f"COALESCE(TRY_CAST({revenue_col} AS BIGINT), 0) DESC")
        elif sort == 'revenue-asc':
            # Low to high: Show positive values first (smallest to largest), then zeros, then negatives
            order_by_clauses.append(f"""
                CASE 
                    WHEN TRY_CAST({revenue_col} AS BIGINT) IS NULL THEN 3
                    WHEN TRY_CAST({revenue_col} AS BIGINT) <= 0 THEN 2
                    ELSE 1
                END ASC,
                ABS(COALESCE(TRY_CAST({revenue_col} AS BIGINT), 0)) ASC
            """)
        elif sort == 'assets-desc':
            order_by_clauses.append(f"COALESCE(TRY_CAST({asset_col} AS BIGINT), 0) DESC")
        elif sort == 'assets-asc':
            # Low to high: Show positive values first (smallest to largest), then zeros, then negatives
            order_by_clauses.append(f"""
                CASE 
                    WHEN TRY_CAST({asset_col} AS BIGINT) IS NULL THEN 3
                    WHEN TRY_CAST({asset_col} AS BIGINT) <= 0 THEN 2
                    ELSE 1
                END ASC,
                ABS(COALESCE(TRY_CAST({asset_col} AS BIGINT), 0)) ASC
            """)
        elif query and query.strip():
            # Relevance sort (only for search mode)
            order_by_clauses.append("score DESC")
            order_by_clauses.append(f"COALESCE(TRY_CAST({revenue_col} AS BIGINT), 0) DESC")
        else:
            # Default browse mode: sort by revenue/assets
            order_by_clauses.append(f"COALESCE(TRY_CAST({revenue_col} AS BIGINT), 0) DESC")
            order_by_clauses.append(f"COALESCE(TRY_CAST({asset_col} AS BIGINT), 0) DESC")
        
        # Always add name as final sort for consistency
        if 'name' not in sort:
            order_by_clauses.append(f"{name_col}")
        
        order_by_sql = ', '.join(order_by_clauses)
        
        # SQL query with relevance scoring (browse mode if no query)
        if query and query.strip():
            # Search mode: score by text match
            sql = f"""
                SELECT 
                    {columns_sql},
                    CASE 
                        WHEN LOWER({name_col}) LIKE LOWER(?) THEN 1.5
                        WHEN LOWER({name_col}) LIKE LOWER(?) THEN 1.0
                        ELSE 0.5
                    END as score
                FROM df
                WHERE {where_sql}
                ORDER BY {order_by_sql}
                LIMIT ? OFFSET ?
            """
            # Execute query with scoring parameters
            query_params = [f'{query}%', f'%{query}%'] + params + [limit, offset]
        else:
            # Browse mode: sort by size/activity
            sql = f"""
                SELECT 
                    {columns_sql},
                    1.0 as score
                FROM df
                WHERE {where_sql}
                ORDER BY {order_by_sql}
                LIMIT ? OFFSET ?
            """
            # Execute query without scoring parameters
            query_params = params + [limit, offset]
        
        rows = conn.execute(sql, query_params).fetchall()
        
        # NTEE code descriptions for better context
        ntee_descriptions = {
            'E': 'Health Services',
            'E60': 'Health Support Services',
            'E61': 'Blood Supply',
            'E62': 'Emergency Medical Services',
            'E65': 'Organ & Tissue Banks',
            'E70': 'Public Health',
            'E80': 'Health Treatment - Primary Care',
            'E90': 'Nursing Services',
            'E20': 'Hospitals & Primary Medical Care',
            'E30': 'Ambulatory & Primary Health Care',
            'E32': 'Clinics & Community Health Centers',
            'P': 'Human Services',
            'B': 'Education',
            'X': 'Religion-Related',
            'A': 'Arts, Culture & Humanities',
        }
        
        # Convert to SearchResult objects with intelligent enrichment
        for row in rows:
            # Unpack base columns (now includes tax_period)
            org_name, city, state_code, ntee, ein, revenue, assets, income, tax_period = row[:9]
            
            # Unpack optional enrichment columns if present
            existing_data = {}
            idx = 9
            
            if 'enrichment_website' in enrichment_cols:
                existing_data['enrichment_website'] = row[idx]
                # Only log non-null websites to reduce spam
                if row[idx] and str(row[idx]) != 'nan':
                    logger.debug(f"✅ Website: {row[idx]}")
                idx += 1
            if 'enrichment_mission' in enrichment_cols:
                existing_data['enrichment_mission'] = row[idx]
                idx += 1
            if 'enrichment_logo' in enrichment_cols:
                existing_data['enrichment_logo'] = row[idx]
                idx += 1
            if 'enrichment_last_updated' in enrichment_cols:
                existing_data['enrichment_last_updated'] = row[idx]
                idx += 1
            
            score = row[-1]  # Score is always last
            
            # Parse tax year label from tax_period (format: YYYYMM)
            tax_year = calendar_year_label(tax_period)
            
            # Get enriched data with intelligent backfill (only if requested)
            enrichment = get_enrichment_data(ein, existing_data) if (ein and enrich) else {}
            
            # Build a more informative description
            ntee_desc = None
            if ntee:
                # Try exact match first, then prefix match
                ntee_desc = ntee_descriptions.get(ntee)
                if not ntee_desc:
                    # Try first character (major category)
                    ntee_desc = ntee_descriptions.get(ntee[0]) if ntee else None
            
            # Use enriched mission as primary description, fallback to NTEE + financial
            description = enrichment.get('mission') if enrichment.get('mission') else None
            
            # Validate mission: if it contains a different org name, it's stale data
            if description and org_name:
                # Check if mission mentions a completely different org name
                # (e.g., "Catalyst Institute" when org name is "CAREQUEST INSTITUTE")
                mission_lower = description.lower()
                name_words = set(org_name.lower().split())
                
                # If mission starts with an org name that's not in our actual org name, skip it
                first_sentence = description.split('.')[0].lower()
                if ' is a nonprofit' in first_sentence or ' is an nonprofit' in first_sentence:
                    # Extract the subject (organization name before "is a nonprofit")
                    subject = first_sentence.split(' is a')[0].strip()
                    subject_words = set(subject.split())
                    
                    # If the subject shares NO significant words with our org name, it's stale
                    # (e.g., "catalyst institute" vs "carequest institute")
                    significant_words = subject_words - {'the', 'a', 'an', 'of', 'for', 'and', 'inc', 'llc'}
                    name_significant = name_words - {'the', 'a', 'an', 'of', 'for', 'and', 'inc', 'llc', 'institute'}
                    
                    if significant_words and not (significant_words & name_significant):
                        # Stale data - mission talks about a different org
                        logger.warning(f"Stale mission data for {org_name}: '{subject}' != '{org_name}'")
                        description = None
            
            if not description:
                description_parts = []
                if ntee_desc:
                    description_parts.append(ntee_desc)
                
                # Convert financial data to numbers (handle None and string types)
                try:
                    revenue_num = float(revenue) if revenue else 0
                    assets_num = float(assets) if assets else 0
                except (ValueError, TypeError):
                    revenue_num = 0
                    assets_num = 0
                
                if revenue_num > 0:
                    description_parts.append(f"Revenue: ${revenue_num:,.0f}")
                elif assets_num > 0:
                    description_parts.append(f"Assets: ${assets_num:,.0f}")
                
                if not description_parts:
                    description_parts.append(f"Nonprofit serving {city}")
                
                description = " • ".join(description_parts)
            
            # Build metadata with enriched fields
            metadata = {
                "ein": ein,
                "city": city,
                "state": state_code,
                "ntee_code": ntee,
                "revenue": revenue,
                "assets": assets,
                "income": income,
                "tax_year": tax_year,
                "data_sources": []
            }
            
            # ALWAYS add enrichment from parquet columns (existing_data) - no enrich flag needed
            if existing_data.get('enrichment_website'):
                metadata['website'] = existing_data['enrichment_website']
                metadata['data_sources'].append('cached')
            
            if existing_data.get('enrichment_mission'):
                metadata['mission'] = existing_data['enrichment_mission']
                if 'cached' not in metadata['data_sources']:
                    metadata['data_sources'].append('cached')
            
            if existing_data.get('enrichment_logo'):
                metadata['logo_url'] = existing_data['enrichment_logo']
                if 'cached' not in metadata['data_sources']:
                    metadata['data_sources'].append('cached')
            
            # Add API enrichment if requested (enrich=true)
            if enrichment:
                if enrichment.get('website') and not metadata.get('website'):
                    metadata['website'] = enrichment['website']
                if enrichment.get('logo_url'):
                    metadata['logo_url'] = enrichment['logo_url']
                if enrichment.get('profile_url'):
                    metadata['profile_url'] = enrichment['profile_url']
                if enrichment.get('causes'):
                    metadata['causes'] = enrichment['causes']
                # Add API data sources
                for source in enrichment.get('data_sources', []):
                    if source not in metadata['data_sources']:
                        metadata['data_sources'].append(source)
            
            results.append(SearchResult(
                result_type="organization",
                title=org_name if org_name else "Unknown",
                subtitle=f"{city}, {state_code}" + (f" - NTEE: {ntee}" if ntee else ""),
                description=description,
                url=f"/search?types=organizations&state={state_code}&ein={ein}",
                score=score,
                metadata=metadata
            ))
        
        conn.close()
        logger.info(f"DuckDB search found {len(results)} organizations for query '{query}'")
        
    except Exception as e:
        logger.error(f"Organization search error: {e}")
    
    return results


def search_causes(query: str, limit: int = 10) -> List[SearchResult]:
    """Search causes and NTEE categories - supports browse mode"""
    results = []
    
    try:
        # Get data source (local or remote HuggingFace URL)
        ntee_file = GOLD_DIR / "reference" / "causes_ntee_codes.parquet"
        data_source = get_data_source(ntee_file, use_remote=IS_HF_SPACES)
        
        # Load with caching
        df = load_parquet_cached(data_source)
        logger.debug(f"Loaded {len(df)} NTEE codes from cache")
        
        for _, row in df.iterrows():
            code = str(row.get('ntee_code', ''))
            description = str(row.get('description', ''))
            ntee_type = str(row.get('ntee_type', ''))
            
            # Browse mode: return all causes
            # Search mode: filter by relevance
            if query and query.strip():
                score = max(
                    calculate_relevance_score(description, query),
                    calculate_relevance_score(code, query)
                )
                if score <= 0.3:
                    continue  # Skip low relevance results
            else:
                score = 1.0  # Default score for browse mode
            
            results.append(SearchResult(
                result_type="cause",
                title=description,
                subtitle=f"NTEE Code: {code}",
                description=f"Category type: {ntee_type}",
                url=f"/nonprofits?ntee_code={code}",
                score=score,
                metadata={
                    "ntee_code": code,
                    "ntee_type": ntee_type
                }
            ))
        
        logger.info(f"Found {len(results)} cause results for query '{query}'")
    
    except Exception as e:
        logger.error(f"Cause search error: {e}")
    
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]


def search_jurisdictions(query: str, state: Optional[str] = None, city: Optional[str] = None, jurisdiction_levels: Optional[List[str]] = None, limit: int = 10, offset: int = 0) -> List[SearchResult]:
    """Search cities, counties, townships, and school districts using DuckDB"""
    all_results = []
    
    try:
        conn = duckdb.connect()
        
        # Map frontend level IDs to file keys
        level_mapping = {
            'city': 'city',
            'county': 'county',
            'town': 'township',
            'village': 'township',
            'school_district': 'school district',
            'special_district': 'school district',  # Use school district as proxy
            'state': None  # States handled separately if needed
        }
        
        # Define jurisdiction files with priority scores
        jurisdiction_files = {
            'county': (f"{GOLD_DIR}/reference/jurisdictions_counties.parquet", 1.3),  # Boost counties
            'city': (f"{GOLD_DIR}/reference/jurisdictions_cities.parquet", 1.0),
            'school district': (f"{GOLD_DIR}/reference/jurisdictions_school_districts.parquet", 1.1),  # Boost school districts
            'township': (f"{GOLD_DIR}/reference/jurisdictions_townships.parquet", 0.9)
        }
        
        # Filter jurisdiction files based on selected levels
        if jurisdiction_levels:
            # Map selected levels to file keys
            selected_file_keys = set()
            for level in jurisdiction_levels:
                file_key = level_mapping.get(level)
                if file_key:
                    selected_file_keys.add(file_key)
            
            # Filter to only selected types
            if selected_file_keys:
                jurisdiction_files = {
                    k: v for k, v in jurisdiction_files.items() 
                    if k in selected_file_keys
                }
        
        # Fetch enough results from each type to ensure diversity
        # Even with small limits, we want representation from each type
        per_type_limit = max(limit, 15)
        
        for jtype, (file_path, type_score) in jurisdiction_files.items():
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                continue
            
            try:
                # Build SQL query - use state_code column (2-letter codes)
                where_clauses = []
                params = []
                
                if state:
                    where_clauses.append("state_code = ?")
                    params.append(state)
                
                if city and query:
                    # If city is specified, search for jurisdictions matching the city name
                    where_clauses.append("LOWER(NAME) LIKE LOWER(?)")
                    params.append(f"%{city}%")
                elif query:
                    # General search across jurisdiction names
                    where_clauses.append("LOWER(NAME) LIKE LOWER(?)")
                    params.append(f"%{query}%")
                
                where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                # Calculate name match score if query provided
                score_expr = f"{type_score}"
                if query:
                    score_expr = f"""CASE 
                        WHEN LOWER(NAME) = LOWER('{query}') THEN {type_score} * 2.0
                        WHEN LOWER(NAME) LIKE LOWER('{query}%') THEN {type_score} * 1.5
                        ELSE {type_score}
                    END"""
                
                sql = f"""
                    SELECT 
                        NAME as name,
                        state,
                        GEOID as geoid,
                        jurisdiction_type,
                        {score_expr} as score
                    FROM read_parquet(?)
                    WHERE {where_clause}
                    ORDER BY score DESC, NAME ASC
                    LIMIT ?
                """
                
                query_params = [str(file_path_obj)] + params + [per_type_limit]
                df = conn.execute(sql, query_params).fetchdf()
                
                for _, row in df.iterrows():
                    jurisdiction_label = row['jurisdiction_type'].replace('_', ' ').title()
                    all_results.append(SearchResult(
                        result_type='jurisdiction',
                        title=f"{row['name']}",
                        subtitle=f"{jurisdiction_label}",
                        description=f"{jurisdiction_label} in {row['state']}",
                        url=f"/jurisdictions/{row['geoid']}",
                        score=float(row['score']),
                        metadata={
                            'state': row['state'],
                            'geoid': row['geoid'],
                            'type': row['jurisdiction_type']
                        }
                    ))
            
            except Exception as e:
                logger.error(f"Error searching {jtype} jurisdictions: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Jurisdiction search error: {e}")
    
    # Sort all results by score, then apply pagination
    all_results.sort(key=lambda x: (x.score, x.title), reverse=True)
    return all_results[offset:offset + limit]


@router.get("/search")
@router.get("/search/", include_in_schema=False)
async def unified_search(
    q: Optional[str] = Query(None, description="Search query (optional - browse by filters if omitted)"),
    types: Optional[str] = Query(None, description="Comma-separated result types: contacts,meetings,organizations,causes,jurisdictions,bills,topics,decisions,documents"),
    state: Optional[str] = Query(None, description="Filter by state (2-letter code)"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    jurisdiction_levels: Optional[str] = Query(None, description="Comma-separated jurisdiction levels: city,county,town,village,school_district,special_district,state"),
    ntee_code: Optional[str] = Query(None, description="Filter organizations by NTEE code"),
    ein: Optional[str] = Query(None, description="Filter organizations by exact EIN (for direct organization links)"),
    session: Optional[str] = Query(None, description="Filter bills by legislative session"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results per type"),
    offset: int = Query(0, ge=0, description="Number of results to skip (for pagination)"),
    page: int = Query(1, ge=1, description="Page number (alternative to offset)"),
    enrich: bool = Query(False, description="Enable API enrichment (slower - fetches logos, causes from Every.org)"),
    sort: str = Query('relevance', description="Sort order: relevance, name-asc, name-desc, revenue-asc, revenue-desc, assets-asc, assets-desc")
):
    """
    Unified search across all data types
    
    Search for contacts, meetings, organizations, bills, and causes in one query.
    **NEW:** Query is now optional - you can browse by state/type without searching!
    
    **Pagination:**
    - Use `offset` to skip results: `offset=20` skips first 20 results
    - Or use `page` with `limit`: `page=2&limit=20` gets results 21-40
    - `offset` takes precedence if both are provided
    
    **Examples:**
    - `/api/search?q=dental` - Search everything for "dental"
    - `/api/search?types=organizations&state=GA` - Browse all orgs in Georgia
    - `/api/search?q=budget&types=meetings` - Search only meetings
    - `/api/search?q=health&state=AL` - Search in Alabama only
    - `/api/search?q=education&types=organizations,causes` - Search orgs and causes
    - `/api/search?q=health&state=MA&page=2&limit=20` - Page 2 of MA health results
    - `/api/search?q=healthcare&types=bills&state=MA` - Search bills in Massachusetts
    """
    # 🔍 DEBUG LOGGING - Log all incoming request parameters
    logger.info(f"🔍 SEARCH REQUEST: q={q!r}, types={types!r}, state={state!r}, city={city!r}, jurisdiction_levels={jurisdiction_levels!r}, ntee_code={ntee_code!r}, ein={ein!r}, session={session!r}, limit={limit}, offset={offset}, page={page}, enrich={enrich}, sort={sort!r}")
    
    try:
        # Calculate offset from page if offset not explicitly provided
        if offset == 0 and page > 1:
            offset = (page - 1) * limit
        
        # Parse requested types
        if types:
            requested_types = [t.strip() for t in types.split(',')]
        else:
            requested_types = ['contacts', 'meetings', 'organizations', 'causes', 'jurisdictions', 'bills', 'topics', 'decisions', 'documents']
        
        # Parse jurisdiction levels if provided
        jurisdiction_levels_list = None
        if jurisdiction_levels:
            jurisdiction_levels_list = [level.strip() for level in jurisdiction_levels.split(',')]
        
        logger.info(f"📋 Requested types: {requested_types}, calculated offset: {offset}")
        
        all_results = []
        
        # Optimize for single-type browse mode (no query)
        # Let database handle pagination for efficiency
        use_db_pagination = not q and len(requested_types) == 1
        
        if use_db_pagination:
            # Single-type browse: pass offset to DB for efficient pagination
            search_limit = limit
            search_offset = offset
        else:
            # Multi-type or search mode: fetch extra for mixing/sorting
            search_limit = offset + limit + 100
            search_offset = 0
        
        if 'contacts' in requested_types:
            # Use PostgreSQL for fast indexed search
            contact_results_pg = await search_postgres.search_contacts_pg(q, state, limit=search_limit)
            contact_results = [convert_pg_result(r) for r in contact_results_pg]
            logger.info(f"👤 Contacts search returned {len(contact_results)} results")
            all_results.extend(contact_results)
        
        if 'meetings' in requested_types:
            # Use PostgreSQL for fast indexed search
            meeting_results_pg = await search_postgres.search_events_pg(q, state, limit=search_limit)
            meeting_results = [convert_pg_result(r) for r in meeting_results_pg]
            logger.info(f"📅 Meetings search returned {len(meeting_results)} results")
            all_results.extend(meeting_results)
        
        if 'organizations' in requested_types:
            # Use PostgreSQL for fast indexed search
            org_results_pg = await search_postgres.search_organizations_pg(q, state, city, ntee_code, ein, limit=search_limit, offset=search_offset, sort=sort)
            org_results = [convert_pg_result(r) for r in org_results_pg]
            logger.info(f"🏢 Organizations search returned {len(org_results)} results")
            all_results.extend(org_results)
        
        if 'bills' in requested_types:
            # Use PostgreSQL for fast indexed search
            bill_results_pg = await search_postgres.search_bills_pg(q, state, session, limit=search_limit)
            bill_results = [convert_pg_result(r) for r in bill_results_pg]
            logger.info(f"📜 Bills search returned {len(bill_results)} results")
            all_results.extend(bill_results)
        
        if 'topics' in requested_types:
            # Use PostgreSQL for fast indexed search of AI-extracted meeting topics
            topic_results_pg = await search_postgres.search_topics_pg(q, state, ntee_code, limit=search_limit)
            topic_results = [convert_pg_result(r) for r in topic_results_pg]
            logger.info(f"📋 Topics search returned {len(topic_results)} results")
            all_results.extend(topic_results)
        
        if 'decisions' in requested_types:
            # Use PostgreSQL for fast indexed search of governance decisions
            decision_results_pg = await search_postgres.search_decisions_pg(q, state, limit=search_limit)
            decision_results = [convert_pg_result(r) for r in decision_results_pg]
            logger.info(f"⚖️ Decisions search returned {len(decision_results)} results")
            all_results.extend(decision_results)
        
        if 'documents' in requested_types:
            # Full-text search over meeting transcripts (public.event_documents)
            document_results_pg = await search_postgres.search_documents_pg(q, state, limit=search_limit)
            document_results = [convert_pg_result(r) for r in document_results_pg]
            logger.info(f"📄 Documents search returned {len(document_results)} results")
            all_results.extend(document_results)

        if 'causes' in requested_types:
            cause_results = search_causes(q or "", limit=search_limit)
            logger.info(f"🎯 Causes search returned {len(cause_results)} results")
            all_results.extend(cause_results)
        
        if 'jurisdictions' in requested_types:
            # Use PostgreSQL for fast indexed search
            jurisdiction_results_pg = await search_postgres.search_jurisdictions_pg(q, state, city, jurisdiction_levels_list, limit=search_limit, offset=search_offset)
            jurisdiction_results = [convert_pg_result(r) for r in jurisdiction_results_pg]
            logger.info(f"🏛️ Jurisdictions search returned {len(jurisdiction_results)} results")
            all_results.extend(jurisdiction_results)
        
        # Sort all results by score
        all_results.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(f"📊 Total combined results: {len(all_results)}, applying pagination (offset={offset}, limit={limit})")
        
        # Apply pagination
        if use_db_pagination:
            # DB already paginated - use all results
            paginated_results = all_results
        else:
            # Paginate in-memory from combined results
            paginated_results = all_results[offset:offset + limit]
        
        logger.info(f"✂️ Paginated results: {len(paginated_results)} items")
        
        # Group by type for response
        grouped_results = {
            'contacts': [r.to_dict() for r in paginated_results if r.result_type == 'contact'],
            'meetings': [r.to_dict() for r in paginated_results if r.result_type == 'meeting'],
            'organizations': [r.to_dict() for r in paginated_results if r.result_type == 'organization'],
            'bills': [r.to_dict() for r in paginated_results if r.result_type == 'bill'],
            'topics': [r.to_dict() for r in paginated_results if r.result_type == 'topic'],
            'decisions': [r.to_dict() for r in paginated_results if r.result_type == 'decision'],
            'causes': [r.to_dict() for r in paginated_results if r.result_type == 'cause'],
            'jurisdictions': [r.to_dict() for r in paginated_results if r.result_type == 'jurisdiction'],
            'documents': [r.to_dict() for r in paginated_results if r.result_type == 'document'],
        }
        
        logger.info(f"📦 Grouped results - contacts:{len(grouped_results['contacts'])}, meetings:{len(grouped_results['meetings'])}, organizations:{len(grouped_results['organizations'])}, bills:{len(grouped_results['bills'])}, topics:{len(grouped_results['topics'])}, decisions:{len(grouped_results['decisions'])}, causes:{len(grouped_results['causes'])}, jurisdictions:{len(grouped_results['jurisdictions'])}")
        
        # Calculate total results per type (from all_results before pagination)
        type_totals = {
            'contacts': len([r for r in all_results if r.result_type == 'contact']),
            'meetings': len([r for r in all_results if r.result_type == 'meeting']),
            'organizations': len([r for r in all_results if r.result_type == 'organization']),
            'bills': len([r for r in all_results if r.result_type == 'bill']),
            'topics': len([r for r in all_results if r.result_type == 'topic']),
            'decisions': len([r for r in all_results if r.result_type == 'decision']),
            'causes': len([r for r in all_results if r.result_type == 'cause']),
            'jurisdictions': len([r for r in all_results if r.result_type == 'jurisdiction']),
            'documents': len([r for r in all_results if r.result_type == 'document']),
        }
        
        # Calculate total results
        # For single-type browse mode, get accurate count from database
        if not q and len(requested_types) == 1:
            # Browse mode: count total matching records in DB
            if 'organizations' in requested_types:
                total_results = count_organizations(state=state, ntee_code=ntee_code, query=q)
                type_totals['organizations'] = total_results  # Use accurate DB count
            else:
                # Fallback to fetched results for other types
                total_results = len(all_results)
        else:
            # Search/multi-type mode: use fetched results
            total_results = len(all_results)
        
        total_pages = (total_results + limit - 1) // limit  # Ceiling division
        
        response_data = {
            "query": q or "",
            "total_results": total_results,
            "type_totals": type_totals,  # Add per-type totals
            "results": grouped_results,
            "pagination": {
                "page": page if offset == 0 or offset == (page - 1) * limit else (offset // limit) + 1,
                "limit": limit,
                "offset": offset,
                "total_pages": total_pages,
                "has_next": offset + limit < total_results,
                "has_prev": offset > 0
            },
            "filters": {
                "state": state,
                "ntee_code": ntee_code,
                "types": requested_types,
                "sort": sort
            }
        }
        
        logger.info(f"✅ Search complete - returning {total_results} total results, {len(paginated_results)} on this page")
        return response_data
    
    except Exception as e:
        logger.error(f"❌ Search error: {type(e).__name__}: {e}")
        logger.exception("Full traceback:")
        
        # Parse error into structured response
        error_detail = parse_error(e, context={
            "query": q,
            "state": state,
            "types": types,
            "data_type": "search"
        })
        
        return JSONResponse(
            status_code=500,
            content=error_detail.model_dump()
        )


@router.get("/search/suggest")
async def search_suggestions(
    q: str = Query(..., min_length=1, description="Partial search query"),
    limit: int = Query(5, ge=1, le=20, description="Maximum suggestions")
):
    """
    Get search suggestions/autocomplete
    
    Returns quick suggestions as user types
    """
    try:
        suggestions = []
        
        # Common search terms
        common_terms = [
            "dental health", "oral health", "affordable housing", "public transit",
            "school funding", "budget", "water quality", "parks", "zoning",
            "police", "fire department", "mental health", "food assistance",
            "senior services", "youth programs", "employment", "job training"
        ]
        
        # Filter suggestions
        q_lower = q.lower()
        suggestions = [term for term in common_terms if q_lower in term.lower()]
        
        return {
            "query": q,
            "suggestions": suggestions[:limit]
        }
    
    except Exception as e:
        logger.error(f"Suggestion error: {e}")
        
        # Parse error into structured response
        error_detail = parse_error(e, context={
            "query": q,
            "data_type": "suggestions"
        })
        
        return JSONResponse(
            status_code=500,
            content=error_detail.model_dump()
        )
