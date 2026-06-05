"""
Unified Search API
LinkedIn-style search across leaders, persons, meetings, organizations, and causes
Uses hybrid approach: PostgreSQL (primary, fast) + HuggingFace Search API + DuckDB (fallback)
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pathlib import Path
import asyncio
from loguru import logger
import re
import os
import sys
import requests
from functools import lru_cache
from datetime import datetime, timedelta

from api.errors import ErrorDetail, parse_error
from api.telemetry import tracer
from opentelemetry.trace import SpanKind

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.utils.calendar_year_util import calendar_year_label

# Import PostgreSQL search functions (primary)
from api.routes import search_postgres

# Import HuggingFace Search helpers
# (search_contacts_hf removed: officials now come from public.contact_official via
# search_postgres.search_officials_pg, not the HF/parquet officials feed.)
from api.routes.hf_search import (
    search_organizations_hf,
    search_jurisdictions_hf,
    is_dataset_indexed
)

router = APIRouter(tags=["search"])

# Detect deployment environment
IS_HF_SPACES = os.getenv("HF_SPACES") == "1"
HF_ORGANIZATION = os.getenv('HF_ORGANIZATION', 'CommunityOne')

# Cache for count queries (TTL: 1 hour)
_count_cache = {}
_count_cache_ttl = {}

# Upper bound for the persons pager total. count_persons over mdm_person (~13.8M)
# with a city filter that fans out to tens of thousands of bridge rows is too
# expensive to count exactly for an honest total nobody pages through. We stop
# counting at the cap; a returned value == PERSON_COUNT_CAP means "this many or
# more" (the UI can render it as "1000+"). 1000 / 20-per-page = 50 pages, far
# past any real browse depth.
PERSON_COUNT_CAP = 1000

# Every.org API config (fallback only)
EVERYORG_API_KEY = os.getenv('EVERYORG_API_KEY', '')
EVERYORG_API_BASE = "https://partners.every.org/v0.2"


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


# NOTE: officials search moved to search_postgres.search_officials_pg
# (public.contact_official, title-aware). The old parquet/DuckDB-backed
# search_contacts_duckdb() and its search_contacts() HF/DuckDB wrapper were
# removed when the gold officials parquet feed
# (data/gold/states/<ST>/contact_official.parquet, consolidated
# data/gold/contact_official.parquet) was retired from the API serving layer.
# The unified /search endpoint now dispatches officials via
# search_postgres.search_officials_pg (result_type='leader') under the dedicated
# "leaders" response category, separate from the "persons" category (mdm_person).


async def count_organizations(
    state: Optional[str] = None,
    ntee_code: Optional[str] = None,
    query: Optional[str] = None,
) -> int:
    """Count total nonprofit organizations matching browse/search criteria.

    Postgres-backed (replaces the retired nonprofits_organizations.parquet read).
    Mirrors the table + WHERE filters of
    search_postgres.search_organizations_pg so the browse-mode total agrees with
    the paginated org results: the same
    `mdm_organization m JOIN mdm_organization_nonprofit s USING (master_org_id)`
    join, with the same state_code / ntee_code / name-FTS predicates. The call
    site (unified_search browse mode) only passes state + ntee_code + an empty q,
    but query is still mirrored for parity. Result cached for 1 hour.

    Signature kept as (state, ntee_code, query) so the call site is unchanged.
    """
    # Create cache key
    cache_key = f"count_{state}_{ntee_code}_{query}"

    # Check cache (1 hour TTL)
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_organizations") as span:
        span.set_attribute("search.has_state", bool(state))
        span.set_attribute("search.has_ntee", bool(ntee_code))
        span.set_attribute("search.has_query", bool(query and query.strip()))
        try:
            # Mirror search_organizations_pg: normalize state to 2-letter code.
            norm_state = search_postgres.normalize_state_input(state)

            where_clauses: List[str] = []
            params: List[Any] = []
            param_idx = 1

            if norm_state:
                where_clauses.append(f"m.state_code = ${param_idx}")
                params.append(norm_state.upper())
                param_idx += 1

            if ntee_code:
                where_clauses.append(f"s.ntee_code LIKE ${param_idx}")
                params.append(f"{ntee_code}%")
                param_idx += 1

            if query and query.strip():
                where_clauses.append(
                    "to_tsvector('english', m.org_name) @@ "
                    f"plainto_tsquery('english', ${param_idx})"
                )
                params.append(query)
                param_idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

            sql = f"""
                SELECT count(*)
                FROM mdm_organization m
                JOIN mdm_organization_nonprofit s USING (master_org_id)
                WHERE {where_sql}
            """

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)

            # Cache the result
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now

            return count
        except Exception as e:
            logger.error(f"Count error: {e}")
            span.record_exception(e)
            return 0


async def count_leaders(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
) -> int:
    """Count government officials matching the leaders search filters.

    Mirrors the WHERE predicates of search_postgres.search_officials_pg
    (public.contact_official): the same state_code filter, the same additive
    `jurisdiction ILIKE %city%` city scope, and the same name/title/jurisdiction
    ILIKE for a query. Used to report an HONEST type_total for the "leaders"
    category so pagination (total_pages / has_next) reflects the real match
    count, not the fetched-list length.

    NOTE: search_officials_pg caps its candidate scan at OFFICIAL_CANDIDATE_CAP
    before ranking; this COUNT is uncapped, so for a very broad term it can
    legitimately exceed the number of rows the search returns. That is the
    intended behavior for an honest pager. Result cached for 1 hour.
    """
    norm_state = search_postgres.normalize_state_input(state)
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    # Mirror the search's short-query early-return: a 1-char query with no
    # state/city scope is all noise -> 0 (the search returns []).
    if has_query and len(q) < 2 and not norm_state and not (city and city.strip()):
        return 0

    cache_key = f"count_leaders_{norm_state}_{city}_{query}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_leaders") as span:
        span.set_attribute("search.has_state", bool(norm_state))
        span.set_attribute("search.has_city", bool(city and city.strip()))
        span.set_attribute("search.has_query", has_query)
        try:
            where_clauses: List[str] = []
            params: List[Any] = []
            idx = 1

            if norm_state:
                where_clauses.append(f"state_code = ${idx}")
                params.append(norm_state.upper())
                idx += 1

            if city and city.strip():
                where_clauses.append(f"jurisdiction ILIKE ${idx}")
                params.append(f"%{city.strip()}%")
                idx += 1

            if has_query:
                where_clauses.append(
                    f"(full_name ILIKE ${idx} "
                    f"OR title ILIKE ${idx} "
                    f"OR jurisdiction ILIKE ${idx})"
                )
                params.append(f"%{q}%")
                idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            sql = f"SELECT count(*) FROM contact_official WHERE {where_sql}"

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Leaders count error: {e}")
            span.record_exception(e)
            return 0


async def count_persons(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
) -> int:
    """Count resolved people matching the persons search filters.

    Mirrors the WHERE predicates of search_postgres.search_persons_pg
    (public.mdm_person): the direct state_code filter, the jurisdiction_id /
    city scope through mdm_bridge_person_jurisdiction, the name ILIKE, and the
    org-name anti-join (NOT EXISTS on mdm_organization.org_name_norm). Counts
    DISTINCT resolved people (master_person_id) to match the search's
    DISTINCT ON (master_person_id) dedup.

    NOTE: search_persons_pg caps its candidate scan at PERSON_CANDIDATE_CAP
    before dedup/rank; this COUNT is uncapped, so for a broad term it can exceed
    the returned rows — intended for an honest pager. Result cached for 1 hour.
    """
    norm_state = search_postgres.normalize_state_input(state)
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    # Mirror the search's short-query early-return.
    if has_query and len(q) < 2 and not norm_state:
        return 0

    cache_key = f"count_persons_{norm_state}_{city}_{jurisdiction_id}_{query}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_persons") as span:
        span.set_attribute("search.has_state", bool(norm_state))
        span.set_attribute("search.has_city", bool(city and city.strip()))
        span.set_attribute("search.has_jurisdiction", bool(jurisdiction_id))
        span.set_attribute("search.has_query", has_query)
        try:
            where_clauses: List[str] = []
            params: List[Any] = []
            idx = 1

            if norm_state:
                where_clauses.append(f"p.state_code = ${idx}")
                params.append(norm_state.upper())
                idx += 1

            if jurisdiction_id:
                where_clauses.append(
                    f"EXISTS (SELECT 1 FROM mdm_bridge_person_jurisdiction bj "
                    f"WHERE bj.person_uid = p.person_uid "
                    f"AND bj.jurisdiction_id = ${idx})"
                )
                params.append(jurisdiction_id)
                idx += 1
            elif city and city.strip():
                city_pred = (
                    f"p.person_uid IN ("
                    f"SELECT bj.person_uid FROM mdm_bridge_person_jurisdiction bj "
                    f"JOIN jurisdictions j ON j.jurisdiction_id = bj.jurisdiction_id "
                    f"WHERE lower(j.name) = lower(${idx}) "
                    f"AND j.jurisdiction_type IN ('city','town')"
                )
                params.append(city.strip())
                idx += 1
                if norm_state:
                    city_pred += f" AND j.state_code = ${idx}"
                    params.append(norm_state.upper())
                    idx += 1
                city_pred += ")"
                where_clauses.append(city_pred)

            if has_query:
                where_clauses.append(f"p.full_name ILIKE ${idx}")
                params.append(f"%{q}%")
                idx += 1

            # Same org-name anti-join the search applies.
            where_clauses.append(
                "NOT EXISTS (SELECT 1 FROM mdm_organization o "
                "WHERE o.org_name_norm = p.name_norm)"
            )

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            # Accurate-but-capped distinct count. We must count DISTINCT
            # master_person_id (mdm_person has ~6 source rows per resolved person, so
            # a raw row count over-reports ~6x and would falsely trip the cap for
            # small towns). DISTINCT can't short-circuit on a LIMIT — Postgres dedups
            # the whole matched set first — but this count is cached for 1h and runs
            # off the per-keystroke path, so accuracy beats latency here. The outer
            # LIMIT caps the returned total at PERSON_COUNT_CAP: a result == the cap
            # means "1000+" (the city has at least that many people); anything below
            # is the exact distinct count. The browse query (search_persons_pg) is the
            # per-request hot path and is optimized separately via PERSON_CANDIDATE_CAP.
            sql = f"""
                SELECT count(*) FROM (
                    SELECT DISTINCT p.master_person_id
                    FROM mdm_person p
                    WHERE {where_sql}
                    LIMIT {PERSON_COUNT_CAP}
                ) t
            """

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Persons count error: {e}")
            span.record_exception(e)
            return 0


# NOTE: organizations search moved to search_postgres.search_organizations_pg
# (mdm_organization JOIN mdm_organization_nonprofit). The old DuckDB/parquet
# search_organizations() reading nonprofits_organizations.parquet was removed
# from the API serving layer; unified_search dispatches orgs via the Postgres
# function. count_organizations() above provides the browse-mode total.


# NOTE: causes search moved to search_postgres.search_causes_pg (public.tag,
# vocabulary='ntee'). The old parquet-backed search_causes() was removed when
# data/gold/reference/causes_ntee_codes.parquet was retired.




async def _traced_subsearch(
    label: str,
    coro,
    *,
    q: Optional[str],
    state: Optional[str],
):
    """Await a single per-type sub-search inside its own child span.

    Each coroutine opens its OWN span so the fan-out works correctly under
    asyncio.gather (the span is entered and exited within the same awaited
    task, not shared across the concurrent tasks). Attributes are deliberately
    low-cardinality: we record q.length / has_query / state presence and the
    resulting count — never the raw user query string.
    """
    with tracer.start_as_current_span(f"search.{label}") as span:
        span.set_attribute("search.type", label)
        span.set_attribute("search.q.length", len(q.strip()) if q else 0)
        span.set_attribute("search.has_query", bool(q and q.strip()))
        span.set_attribute("search.has_state", bool(state))
        outcome = await coro
        # gather(return_exceptions=True) would swallow this, but here we await
        # directly so a failure is recorded on the span then re-raised for the
        # dispatcher's per-type error handling.
        try:
            span.set_attribute("search.result.count", len(outcome))
        except TypeError:
            span.set_attribute("search.result.count", 0)
        return outcome


@router.get("/search")
@router.get("/search/", include_in_schema=False)
async def unified_search(
    q: Optional[str] = Query(None, description="Search query (optional - browse by filters if omitted)"),
    types: Optional[str] = Query(None, description="Comma-separated result types: leaders,persons,meetings,organizations,causes,jurisdictions,bills,topics,decisions,documents,grants. Legacy aliases accepted: 'contacts'/'officials' -> 'leaders', 'people'/'person' -> 'persons'"),
    state: Optional[str] = Query(None, description="Filter by state (2-letter code)"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    jurisdiction_id: Optional[str] = Query(None, description="Filter by exact jurisdiction_id (city, county, or state) — scopes orgs/persons/grants through the MDM jurisdiction bridges"),
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

    Search for leaders (officials), persons, meetings, organizations, bills, and
    causes in one query.
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
    logger.info(f"🔍 SEARCH REQUEST: q={q!r}, types={types!r}, state={state!r}, city={city!r}, jurisdiction_id={jurisdiction_id!r}, jurisdiction_levels={jurisdiction_levels!r}, ntee_code={ntee_code!r}, ein={ein!r}, session={session!r}, limit={limit}, offset={offset}, page={page}, enrich={enrich}, sort={sort!r}")
    
    try:
        # Calculate offset from page if offset not explicitly provided
        if offset == 0 and page > 1:
            offset = (page - 1) * limit
        
        # Parse requested types, normalizing legacy aliases to the current scheme.
        # People are now split into two distinct categories:
        #   - "leaders"  -> government officials (contact_official)
        #   - "persons"  -> real people (mdm_person; now also residents/homeowners)
        # Legacy aliases kept for backward compat (old clients still send these):
        #   'contacts'/'officials'/'contact' -> 'leaders'
        #   'people'/'person'                -> 'persons'
        _TYPE_ALIASES = {
            'contacts': 'leaders',
            'contact': 'leaders',
            'officials': 'leaders',
            'leader': 'leaders',
            'people': 'persons',
            'person': 'persons',
        }
        if types:
            requested_types = [
                _TYPE_ALIASES.get(t.strip(), t.strip())
                for t in types.split(',')
                if t.strip()
            ]
        else:
            requested_types = ['leaders', 'persons', 'meetings', 'organizations', 'causes', 'jurisdictions', 'bills', 'topics', 'decisions', 'documents', 'grants']
        
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
        
        # Each requested type is an independent indexed PostgreSQL query. Run them
        # CONCURRENTLY (asyncio.gather) instead of sequentially: a multi-type search
        # used to await each type back-to-back, so their latencies *compounded* (5
        # types ~= sum of 5 query times). Concurrent dispatch makes the endpoint as
        # slow as its single slowest type, and isolates a slow/failing type so it
        # can't block the others. The pool (max_size=20) comfortably covers the
        # handful of in-flight per-type queries.
        # (label, coroutine) pairs — built only for requested types.
        search_tasks: List[tuple] = []

        # "persons" — real people from the MDM person master (mdm_person), fast
        # trigram name search. (Aliases 'people'/'person' already normalized above.)
        # A parallel data change is folding homeowners/residents into mdm_person, so
        # this category will include residents automatically — no API change needed.
        if 'persons' in requested_types:
            search_tasks.append(('persons', search_postgres.search_persons_pg(q, state, city=city, jurisdiction_id=jurisdiction_id, limit=search_limit)))

        # "leaders" — elected/appointed government officials (public.contact_official),
        # title-aware so a query like "Mayor" returns officials (result_type='leader').
        # This is now its OWN category, distinct from "persons". (Aliases
        # 'contacts'/'officials' already normalized to 'leaders' above.)
        if 'leaders' in requested_types:
            search_tasks.append(('leaders', search_postgres.search_officials_pg(q, state, city=city, limit=search_limit)))

        if 'meetings' in requested_types:
            search_tasks.append(('meetings', search_postgres.search_events_pg(q, state, limit=search_limit)))

        if 'organizations' in requested_types:
            search_tasks.append(('organizations', search_postgres.search_organizations_pg(q, state, city, ntee_code, ein, jurisdiction_id=jurisdiction_id, limit=search_limit, offset=search_offset, sort=sort)))

        if 'bills' in requested_types:
            search_tasks.append(('bills', search_postgres.search_bills_pg(q, state, session, city=city, limit=search_limit)))

        if 'grants' in requested_types:
            # Nonprofit grants (public.grant) — ILIKE over grantor/grantee/purpose,
            # ordered by amount DESC. Location filter is by GRANTOR geography
            # (jurisdiction_id via the org bridge, else state/city direct).
            # Graceful no-op if the mart is unbuilt.
            search_tasks.append(('grants', search_postgres.search_grants_pg(q, state, city=city, jurisdiction_id=jurisdiction_id, limit=search_limit, offset=search_offset)))

        if 'topics' in requested_types:
            search_tasks.append(('topics', search_postgres.search_topics_pg(q, state, ntee_code, limit=search_limit)))

        if 'decisions' in requested_types:
            search_tasks.append(('decisions', search_postgres.search_decisions_pg(q, state, city=city, sort=sort, limit=search_limit)))

        if 'documents' in requested_types:
            # Full-text search over meeting transcripts (public.event_documents)
            search_tasks.append(('documents', search_postgres.search_documents_pg(q, state, limit=search_limit)))

        if 'causes' in requested_types:
            # NTEE causes now come from public.tag (vocabulary='ntee'); the old
            # causes_ntee_codes.parquet feed was retired.
            search_tasks.append(('causes', search_postgres.search_causes_pg(q, limit=search_limit)))

        if 'jurisdictions' in requested_types:
            search_tasks.append(('jurisdictions', search_postgres.search_jurisdictions_pg(q, state, city, jurisdiction_levels_list, limit=search_limit, offset=search_offset)))

        if search_tasks:
            # return_exceptions=True so one failing type degrades gracefully
            # (empty results for it) instead of failing the whole search.
            labels = [label for label, _ in search_tasks]
            # Parent span over the concurrent fan-out; each sub-search opens its
            # own child span (search.person, search.organizations, ...) so the
            # person-vs-org timing we debugged is visible per type in traces.
            with tracer.start_as_current_span(
                "search.dispatch", kind=SpanKind.INTERNAL
            ) as dispatch_span:
                dispatch_span.set_attribute("search.types", ",".join(labels))
                dispatch_span.set_attribute("search.type_count", len(labels))
                dispatch_span.set_attribute(
                    "search.q.length", len(q.strip()) if q else 0
                )
                dispatch_span.set_attribute("search.has_query", bool(q and q.strip()))
                dispatch_span.set_attribute("search.has_state", bool(state))
                gathered = await asyncio.gather(
                    *(
                        _traced_subsearch(label, coro, q=q, state=state)
                        for label, coro in search_tasks
                    ),
                    return_exceptions=True,
                )
            for label, outcome in zip(labels, gathered):
                if isinstance(outcome, Exception):
                    logger.error(f"❌ {label} search failed: {outcome}")
                    continue
                converted = [convert_pg_result(r) for r in outcome]
                logger.info(f"🔎 {label} search returned {len(converted)} results")
                all_results.extend(converted)

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
        
        # Group by type for response.
        # Two DISTINCT people categories now:
        #   - 'leaders'  <- result_type 'leader'  (government officials)
        #   - 'persons'  <- result_type 'person'  (real people / residents)
        # The old combined 'person'/'contacts' grouping is removed.
        grouped_results = {
            'leaders': [r.to_dict() for r in paginated_results if r.result_type == 'leader'],
            'persons': [r.to_dict() for r in paginated_results if r.result_type == 'person'],
            'meetings': [r.to_dict() for r in paginated_results if r.result_type == 'meeting'],
            'organizations': [r.to_dict() for r in paginated_results if r.result_type == 'organization'],
            'bills': [r.to_dict() for r in paginated_results if r.result_type == 'bill'],
            'topics': [r.to_dict() for r in paginated_results if r.result_type == 'topic'],
            'decisions': [r.to_dict() for r in paginated_results if r.result_type == 'decision'],
            'causes': [r.to_dict() for r in paginated_results if r.result_type == 'cause'],
            'jurisdictions': [r.to_dict() for r in paginated_results if r.result_type == 'jurisdiction'],
            'documents': [r.to_dict() for r in paginated_results if r.result_type == 'document'],
            'grants': [r.to_dict() for r in paginated_results if r.result_type == 'grant'],
        }

        logger.info(f"📦 Grouped results - leaders:{len(grouped_results['leaders'])}, persons:{len(grouped_results['persons'])}, meetings:{len(grouped_results['meetings'])}, organizations:{len(grouped_results['organizations'])}, bills:{len(grouped_results['bills'])}, topics:{len(grouped_results['topics'])}, decisions:{len(grouped_results['decisions'])}, causes:{len(grouped_results['causes'])}, jurisdictions:{len(grouped_results['jurisdictions'])}, grants:{len(grouped_results['grants'])}")

        # Calculate total results per type (from all_results before pagination).
        # leaders and persons each report their OWN total.
        type_totals = {
            'leaders': len([r for r in all_results if r.result_type == 'leader']),
            'persons': len([r for r in all_results if r.result_type == 'person']),
            'meetings': len([r for r in all_results if r.result_type == 'meeting']),
            'organizations': len([r for r in all_results if r.result_type == 'organization']),
            'bills': len([r for r in all_results if r.result_type == 'bill']),
            'topics': len([r for r in all_results if r.result_type == 'topic']),
            'decisions': len([r for r in all_results if r.result_type == 'decision']),
            'causes': len([r for r in all_results if r.result_type == 'cause']),
            'jurisdictions': len([r for r in all_results if r.result_type == 'jurisdiction']),
            'documents': len([r for r in all_results if r.result_type == 'document']),
            'grants': len([r for r in all_results if r.result_type == 'grant']),
        }
        
        # Calculate total results.
        #
        # The fetched-list lengths above are only an honest total when the whole
        # match set fits in one fetch. For a filtered search (a query and/or a
        # city/state/jurisdiction scope) the search functions cap their candidate
        # scans, so len(all_results) under-reports the true count and the pager
        # collapses (total_pages -> 1, has_next -> False), hiding later pages.
        #
        # Fix: for the common, paginated types we replace the fetched-length
        # estimate with a real DB COUNT that mirrors each search's WHERE clause:
        #   - organizations: count_organizations (browse mode, as before)
        #   - leaders:       count_leaders   (NEW — query/state/city aware)
        #   - persons:       count_persons   (NEW — query/state/city/jurisdiction)
        # total_results is then the SUM of the per-type type_totals (accurate
        # where we have a COUNT, fetched-length estimate otherwise).
        #
        # REMAINING ESTIMATES: meetings, bills, topics, decisions, causes,
        # jurisdictions, documents, and grants still report fetched-length totals
        # (their type_totals can under-count a broad filtered search). Adding
        # COUNT helpers for those is a follow-up; scoped here to the high-traffic
        # leaders + persons (+ existing organizations) path.
        is_filtered = bool(q) or bool(state) or bool(city) or bool(jurisdiction_id)

        if not q and len(requested_types) == 1 and 'organizations' in requested_types:
            # Single-type org browse: accurate count (unchanged behavior).
            type_totals['organizations'] = await count_organizations(
                state=state, ntee_code=ntee_code, query=q
            )

        # Accurate per-type counts for the paginated people categories whenever
        # the result set is filtered (query and/or location scope).
        if is_filtered and 'leaders' in requested_types:
            type_totals['leaders'] = await count_leaders(
                query=q, state=state, city=city
            )
        if is_filtered and 'persons' in requested_types:
            type_totals['persons'] = await count_persons(
                query=q, state=state, city=city, jurisdiction_id=jurisdiction_id
            )

        # Derive the grand total from the (now partly-accurate) per-type totals
        # rather than the fetched-list length, so total_pages/has_next reflect
        # the real match count for leaders/persons/organizations.
        total_results = sum(type_totals.values())

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
                "city": city,
                "jurisdiction_id": jurisdiction_id,
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
