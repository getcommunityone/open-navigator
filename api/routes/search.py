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
import json
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
# (search_contacts_hf removed: officials now come from contact_official via
# search_postgres.search_officials_pg, not the HF/parquet officials feed.)
from api.routes.hf_search import (
    search_organizations_hf,
    search_jurisdictions_hf,
    is_dataset_indexed
)

router = APIRouter(tags=["search"])

# Per-type sub-search timeout (seconds). The unified search fans every requested
# type out concurrently (asyncio.gather), so the combined response is only as fast
# as its SLOWEST type. Every well-indexed type returns sub-second; a pathological
# one (e.g. an un-capped ILIKE over public.grant) can take ~20s and, with no
# ceiling, drags the whole homepage past the frontend's fetch-abort window so NO
# category renders. Cap each sub-search: a slow type degrades to empty results for
# that type (the dispatcher already treats a per-type failure as empty via
# return_exceptions=True) instead of sinking the fast types. Override with
# SEARCH_SUBSEARCH_TIMEOUT_S.
#
# Value: a BACKSTOP, not a tuning knob. The legitimately heaviest types (orgs FTS,
# persons over mdm_person) run ~5-6s on a broad term, so the cap sits above them
# to avoid clipping real results to empty; it exists to kill true pathologies
# (the old ~19s un-indexed grants leg) well under the frontend's 20s fetch-abort.
SUBSEARCH_TIMEOUT_S = float(os.getenv("SEARCH_SUBSEARCH_TIMEOUT_S", "10.0"))

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

# Upper bound for the grants pager total. public.grant is ~6.7M rows with no
# full-text index, so even a location-scoped count is capped via a LIMIT subquery
# so a large state can't run long; a returned value == GRANT_COUNT_CAP means
# "this many or more". 5000 / 20-per-page = 250 pages, far past any real browse.
GRANT_COUNT_CAP = 5000

# Scope cut (Neon free-tier storage): the "persons" category serves
# mdm_person (~13.8M rows) plus its bridges and 990 compensation records —
# ~38 GB and almost entirely NON-government people (nonprofit officers, residents).
# Government leaders are served separately by the "leaders" category
# (contact_official). With this flag False, "persons" is stripped from
# every search so mdm_person / mdm_bridge_person_* / organization_nonprofit_compensation
# never get queried — and therefore don't need to be mirrored to Neon. Flip to
# True to restore full people search once storage allows.
PERSONS_SEARCH_ENABLED = False

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
# (contact_official, title-aware). The old parquet/DuckDB-backed
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
    (contact_official): the same state_code filter, the same additive
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
    (mdm_person): the direct state_code filter, the jurisdiction_id /
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


async def resolve_topic_tsquery(topic_id: int) -> Optional[str]:
    """Build an OR-tsquery from a named civic topic's label + keyword set.

    The named civic-topic catalog (public.civicsearch_topic) is a keyword cluster,
    not an FK to events, so the Advanced "Topic" filter narrows results by matching
    the topic's defining keywords. Returns a to_tsquery-safe ``'kw1 | kw2 | ...'``
    string (lowercase alphabetic lexemes, deduped), or None if the topic is unknown
    or has no usable terms. keyword_stats arrives as TEXT (the pool has no JSONB
    codec), so it is json.loads()'d like topics.py does.
    """
    try:
        pool = await search_postgres.get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name, keyword_stats FROM civicsearch_topic WHERE topic_id = $1",
                topic_id,
            )
    except Exception as e:  # noqa: BLE001
        logger.error(f"resolve_topic_tsquery error: {e}")
        return None
    if not row:
        return None

    raw_kw = row["keyword_stats"]
    keywords: List[str] = []
    if isinstance(raw_kw, list):
        keywords = [str(k) for k in raw_kw]
    elif isinstance(raw_kw, str):
        try:
            parsed = json.loads(raw_kw)
            if isinstance(parsed, list):
                keywords = [str(k) for k in parsed]
        except (TypeError, ValueError):
            keywords = []

    terms: List[str] = []
    seen: set[str] = set()
    for blob in [row["name"], *keywords]:
        if not blob:
            continue
        # Split phrases into alphabetic word lexemes so the result is a clean,
        # injection-safe to_tsquery; len>=3 drops noise tokens ("of", "to").
        for tok in re.findall(r"[a-z]+", str(blob).lower()):
            if len(tok) >= 3 and tok not in seen:
                seen.add(tok)
                terms.append(tok)
    if not terms:
        return None
    return " | ".join(terms)


# EveryOrg cause -> keyword vocabulary. KEEP IN SYNC with the dbt models
# int_meeting_cause / int_transcript_keyword_cause / int_decision_cause (same
# editorial civic vocabulary, NOT fabricated data). Multi-word entries are matched
# as ordered phrases (<->) so e.g. "mental health" doesn't fire on bare "health".
CAUSE_KEYWORDS: Dict[str, List[str]] = {
    'animals': ['animal', 'animals', 'pet', 'pets', 'animal shelter', 'wildlife', 'veterinary', 'leash'],
    'arts': ['arts', 'culture', 'cultural', 'museum', 'theater', 'theatre', 'mural', 'gallery', 'public art'],
    'climate': ['climate', 'emissions', 'greenhouse gas', 'carbon', 'sustainability', 'resilience', 'renewable energy', 'solar'],
    'disasters': ['disaster', 'emergency', 'hurricane', 'tornado', 'flood', 'fema', 'evacuation', 'disaster relief'],
    'education': ['education', 'school', 'schools', 'student', 'students', 'teacher', 'classroom', 'curriculum', 'literacy'],
    'environment': ['environment', 'environmental', 'pollution', 'conservation', 'recycling', 'wetland', 'watershed', 'habitat'],
    'foodbanks': ['food bank', 'hunger', 'food insecurity', 'food pantry', 'nutrition', 'meals'],
    'health': ['health', 'healthcare', 'hospital', 'clinic', 'medical', 'public health', 'vaccine'],
    'humanitarian': ['humanitarian', 'refugee', 'humanitarian aid', 'displaced'],
    'justice': ['justice', 'civil rights', 'equity', 'discrimination', 'police reform', 'reentry'],
    'lgbt': ['lgbtq', 'lgbt', 'transgender', 'pride'],
    'mental-health': ['mental health', 'suicide', 'counseling', 'behavioral health', 'addiction', 'substance abuse'],
    'religion': ['church', 'faith', 'religious', 'congregation', 'ministry', 'worship'],
    'seniors': ['senior', 'seniors', 'elderly', 'aging', 'retirement', 'medicare'],
    'water': ['drinking water', 'wastewater', 'sewer', 'watershed', 'stormwater', 'clean water'],
    'women': ['women', 'gender', 'maternal', 'domestic violence'],
    'youth': ['youth', 'children', 'juvenile', 'after-school', 'childcare', 'recreation'],
}


def resolve_cause_tsquery(cause_id: str) -> Optional[str]:
    """Build an OR-tsquery from an EveryOrg cause's curated keyword set.

    The Advanced "Cause" filter is the cause counterpart to resolve_topic_tsquery:
    it narrows decisions/meetings/topics by the cause's defining keywords. Each
    keyword becomes an injection-safe term — single word as a lexeme, multi-word as
    an ordered phrase (``word1<->word2``) so generic heads ("health") don't fire on
    every mention. Returns a ``to_tsquery``-safe ``'t1 | t2 | ...'`` string, or None
    for an unknown cause / no usable terms. Synchronous: reads an in-process dict,
    no DB round-trip (unlike resolve_topic_tsquery).
    """
    keywords = CAUSE_KEYWORDS.get((cause_id or "").strip().lower())
    if not keywords:
        return None
    terms: List[str] = []
    seen: set[str] = set()
    for kw in keywords:
        toks = [t for t in re.findall(r"[a-z]+", kw.lower()) if len(t) >= 3]
        if not toks:
            continue
        term = "<->".join(toks) if len(toks) > 1 else toks[0]
        if term not in seen:
            seen.add(term)
            terms.append(term)
    if not terms:
        return None
    return " | ".join(terms)


async def count_events(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    topic_tsquery: Optional[str] = None,
) -> int:
    """Count meetings matching the events search filters.

    Mirrors the WHERE predicates of search_postgres.search_events_pg over BOTH
    legs of the merged Meetings feed, so the type_total matches the results:

    1. ANALYZED — public.event_meeting: the same state_code filter, the same
       exact-name city scope (jurisdiction_name OR city), and the same
       body/jurisdiction/summary/city ILIKE (+ child-decision FTS) for a query.
    2. UNANALYZED — DISTINCT video_id from public.event_documents where
       event_id IS NULL, same state/city scope, query = event_title ILIKE OR
       to_tsvector('english', content) @@ plainto_tsquery, EXCLUDING video_ids
       already present in event_meeting (NOT EXISTS), so the dedup matches
       search_events_pg.

    Without the unanalyzed leg the tab would read 0 for transcript-only cities
    (e.g. Atlanta) while results still appear. Used to report an HONEST
    type_total — the lightweight tab-counts call sends limit=1, which would
    otherwise cap the fetched-length estimate at 1.

    event_meeting is small (~6k rows); the unanalyzed DISTINCT-video_id count is
    bounded by the state/city filters + the to_tsvector('english', content)
    expression GIN index. Cached for 1 hour.
    """
    norm_state = search_postgres.normalize_state_input(state)
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_events_{norm_state}_{city}_{query}_{topic_tsquery}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_events") as span:
        span.set_attribute("search.has_state", bool(norm_state))
        span.set_attribute("search.has_city", bool(city and city.strip()))
        span.set_attribute("search.has_query", has_query)
        try:
            # Shared parameter bag for the two-leg count. asyncpg uses positional
            # $n, so each value is registered once and its index reused.
            params: List[Any] = []

            q_like_idx = q_fts_idx = None
            if has_query:
                params.append(f"%{q}%")
                q_like_idx = len(params)
                params.append(q)
                q_fts_idx = len(params)

            state_idx = None
            if norm_state:
                params.append(norm_state.upper())
                state_idx = len(params)

            city_idx = None
            if city and city.strip():
                params.append(city.strip())
                city_idx = len(params)

            # Civic-topic filter (mirrors search_events_pg topic narrowing).
            topic_idx = None
            if topic_tsquery:
                params.append(topic_tsquery)
                topic_idx = len(params)

            # ---- Analyzed leg (event_meeting) ----
            em_where: List[str] = []
            if has_query:
                # Mirror search_events_pg: a meeting counts when its own text
                # matches OR when a child decision (linked by c1_event_id) matches
                # the same English-FTS used by count_decisions.
                em_where.append(
                    f"(em.body_name ILIKE ${q_like_idx} OR em.jurisdiction_name ILIKE ${q_like_idx} "
                    f"OR em.meeting_summary ILIKE ${q_like_idx} OR em.city ILIKE ${q_like_idx} "
                    f"OR EXISTS (SELECT 1 FROM event_decision d "
                    f"WHERE d.c1_event_id = em.c1_event_id "
                    f"AND d.search_tsv @@ plainto_tsquery('english', ${q_fts_idx})))"
                )
            if state_idx:
                em_where.append(f"em.state_code = ${state_idx}")
            if city_idx:
                em_where.append(
                    f"(lower(em.jurisdiction_name) = lower(${city_idx}) "
                    f"OR lower(em.city) = lower(${city_idx}))"
                )
            if topic_idx:
                em_where.append(
                    f"(to_tsvector('english', COALESCE(em.body_name, '') || ' ' "
                    f"|| COALESCE(em.meeting_summary, '') || ' ' || COALESCE(em.jurisdiction_name, '')) "
                    f"@@ to_tsquery('english', ${topic_idx}) "
                    f"OR EXISTS (SELECT 1 FROM event_decision d "
                    f"WHERE d.c1_event_id = em.c1_event_id "
                    f"AND d.search_tsv @@ to_tsquery('english', ${topic_idx})))"
                )
            em_where_sql = " AND ".join(em_where) if em_where else "TRUE"

            # ---- Unanalyzed leg (every meeting-video not already analyzed) ----
            # Each event_documents row is a transcribed meeting video. We count
            # every distinct video that isn't already an analyzed event_meeting
            # (the NOT EXISTS dedup below), so the Meetings total reflects all
            # meeting sessions, not only the AI-analyzed slice. (Previously gated
            # on event_id IS NULL, which dropped ~99k videos linked to an event
            # but not analyzed.)
            ed_where: List[str] = []
            if has_query:
                ed_where.append(
                    f"(ed.event_title ILIKE ${q_like_idx} "
                    f"OR to_tsvector('english', ed.content) @@ plainto_tsquery('english', ${q_fts_idx}))"
                )
            if state_idx:
                ed_where.append(f"ed.state_code = ${state_idx}")
            if city_idx:
                ed_where.append(
                    f"(lower(ed.jurisdiction_name) = lower(${city_idx}) "
                    f"OR lower(ed.city) = lower(${city_idx}))"
                )
            if topic_idx:
                ed_where.append(f"to_tsvector('english', ed.content) @@ to_tsquery('english', ${topic_idx})")
            # Same dedup as search_events_pg: exclude videos already analyzed.
            ed_where.append(
                "NOT EXISTS (SELECT 1 FROM event_meeting em2 WHERE em2.video_id = ed.video_id)"
            )
            ed_where_sql = " AND ".join(ed_where)

            sql = f"""
                SELECT
                    (SELECT count(*) FROM event_meeting em WHERE {em_where_sql})
                  + (SELECT count(DISTINCT ed.video_id)
                       FROM event_documents ed WHERE {ed_where_sql})
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
            logger.error(f"Events count error: {e}")
            span.record_exception(e)
            return 0


async def count_decisions(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    question_id: Optional[str] = None,
    topic_tsquery: Optional[str] = None,
) -> int:
    """Count governance decisions matching the decisions search filters.

    Mirrors the WHERE predicates of search_postgres.search_decisions_pg over
    public.event_decision: the same state_code filter, the same exact-name city
    scope (jurisdiction_name OR city), and the same English-FTS over
    headline/decision_statement/primary_theme for a query. Used to report an
    HONEST type_total for "decisions" so the count is independent of the caller's
    limit — the lightweight tab-counts call sends limit=1, which would otherwise
    cap the fetched-length estimate at 1 in single-type browse mode.

    event_decision is small (~9k rows) so this uncapped count(*) is sub-millisecond.
    Result cached for 1 hour.
    """
    norm_state = search_postgres.normalize_state_input(state)
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_decisions_{norm_state}_{city}_{query}_{question_id}_{topic_tsquery}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_decisions") as span:
        span.set_attribute("search.has_state", bool(norm_state))
        span.set_attribute("search.has_city", bool(city and city.strip()))
        span.set_attribute("search.has_query", has_query)
        try:
            where_clauses: List[str] = []
            params: List[Any] = []
            idx = 1

            if norm_state:
                where_clauses.append(f"d.state_code = ${idx}")
                params.append(norm_state.upper())
                idx += 1

            if city and city.strip():
                where_clauses.append(
                    f"(lower(d.jurisdiction_name) = lower(${idx}) OR lower(d.city) = lower(${idx}))"
                )
                params.append(city.strip())
                idx += 1

            if has_query:
                # d.search_tsv: persisted GIN-indexed tsvector on event_decision
                # (headline||decision_statement||primary_theme) — index-backed
                # replacement for the old ad-hoc to_tsvector, matching
                # search_decisions_pg.
                where_clauses.append(
                    f"(d.search_tsv @@ plainto_tsquery('english', ${idx}))"
                )
                params.append(q)
                idx += 1

            if question_id:
                # Mirror search_decisions_pg: only decisions instantiating the question.
                where_clauses.append(
                    f"EXISTS (SELECT 1 FROM question_instance qi "
                    f"WHERE qi.source_type = 'local_decision' "
                    f"AND qi.source_id = d.event_decision_id "
                    f"AND qi.question_id = ${idx})"
                )
                params.append(question_id)
                idx += 1

            if topic_tsquery:
                # Mirror search_decisions_pg civic-topic narrowing.
                where_clauses.append(f"d.search_tsv @@ to_tsquery('english', ${idx})")
                params.append(topic_tsquery)
                idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            sql = f"SELECT count(*) FROM event_decision d WHERE {where_sql}"

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Decisions count error: {e}")
            span.record_exception(e)
            return 0


async def count_bills(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
) -> int:
    """Count meeting-referenced legislation matching the bills search filters.

    Mirrors the WHERE predicates of search_postgres.search_bills_pg over
    public.event_bill: the same state_code filter, the same exact-name city scope
    (jurisdiction_name OR city), and the same title-FTS / official_number LIKE for
    a query. Used to report an HONEST type_total for "bills" so the count is
    independent of the caller's limit — the tab-counts call sends limit=1, which
    would otherwise cap the fetched-length estimate at 1 in single-type browse.

    event_bill is small (~14k rows) so this uncapped count(*) is sub-second.
    Result cached for 1 hour.
    """
    norm_state = search_postgres.normalize_state_input(state)
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_bills_{norm_state}_{city}_{query}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_bills") as span:
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
                where_clauses.append(
                    f"(lower(jurisdiction_name) = lower(${idx}) OR lower(city) = lower(${idx}))"
                )
                params.append(city.strip())
                idx += 1

            if has_query:
                where_clauses.append(
                    f"(to_tsvector('english', COALESCE(title, '')) "
                    f"@@ plainto_tsquery('english', ${idx}) "
                    f"OR LOWER(official_number) LIKE LOWER(${idx + 1}))"
                )
                params.append(q)
                params.append(f"%{q}%")
                idx += 2

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            sql = f"SELECT count(*) FROM event_bill WHERE {where_sql}"

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)

            # search_bills_pg also surfaces OpenStates legislation from the `bills`
            # serving relation (title-FTS, query-gated, state-only). Count those too
            # so the badge reflects the FULL bills match set, not just event_bill —
            # otherwise "fluoride" reads "Bills 4" while the tab shows 100+. Title
            # FTS is GIN-indexed (sub-ms); wrapped so it degrades to the event_bill
            # count where `bills` isn't published.
            if has_query:
                try:
                    leg_params: List[Any] = [q]
                    leg_state = ""
                    if norm_state:
                        leg_params.append(norm_state.upper())
                        leg_state = " AND state_code = $2"
                    leg_sql = (
                        "SELECT count(*) FROM bills "
                        "WHERE to_tsvector('english', coalesce(title, '')) "
                        f"@@ plainto_tsquery('english', $1){leg_state}"
                    )
                    async with pool.acquire() as conn:
                        leg_count = await conn.fetchval(leg_sql, *leg_params)
                    count += int(leg_count or 0)
                except Exception as leg_err:
                    logger.debug(f"Legislative bills count skipped: {leg_err}")

            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Bills count error: {e}")
            span.record_exception(e)
            return 0


async def count_documents(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
) -> int:
    """Count meeting transcripts matching the documents search filters.

    Mirrors the WHERE predicates of search_postgres.search_documents_pg over
    public.event_documents: the same state_code filter, the same exact-name city
    scope (jurisdiction_name OR city), and the same full-text match on the
    EXPRESSION to_tsvector('english', content) (backed by the expression GIN index
    event_documents_content_fts_idx, so this count is index-backed and fast even
    though the search's ts_headline/ts_rank work is not). Reports an HONEST
    type_total for "documents" so the count is independent of the caller's limit.

    Result cached for 1 hour.
    """
    norm_state = search_postgres.normalize_state_input(state)
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_documents_{norm_state}_{city}_{query}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_documents") as span:
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
                where_clauses.append(
                    f"(lower(jurisdiction_name) = lower(${idx}) OR lower(city) = lower(${idx}))"
                )
                params.append(city.strip())
                idx += 1

            if has_query:
                where_clauses.append(
                    f"to_tsvector('english', content) @@ plainto_tsquery('english', ${idx})"
                )
                params.append(q)
                idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            sql = f"SELECT count(*) FROM event_documents WHERE {where_sql}"

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Documents count error: {e}")
            span.record_exception(e)
            return 0


async def count_meeting_documents(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    document_type: Optional[str] = None,
) -> int:
    """Count official meeting documents matching the search filters.

    Mirrors the WHERE predicates of search_postgres.search_meeting_documents_pg
    over public.event_meeting_document: the same state_code filter, the same
    whitelisted document_type filter, the same jurisdiction_id-slug city scope, and
    the same full-text match against the STORED content_tsv vector (GIN-indexed).
    Reports an HONEST type_total for "meeting_documents" so the count is
    independent of the caller's limit. Result cached for 1 hour.
    """
    norm_state = search_postgres.normalize_state_input(state)
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_meeting_documents_{norm_state}_{city}_{document_type}_{query}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_meeting_documents") as span:
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

            if document_type and document_type.strip().lower() in {'agenda', 'minutes', 'attachment'}:
                where_clauses.append(f"document_type = ${idx}")
                params.append(document_type.strip().lower())
                idx += 1

            if city and city.strip():
                where_clauses.append(
                    "regexp_replace(lower(regexp_replace(jurisdiction_id, '_[^_]*$', '')), "
                    f"'[^a-z0-9]+', ' ', 'g') = lower(${idx})"
                )
                params.append(city.strip())
                idx += 1

            if has_query:
                where_clauses.append(
                    f"content_tsv @@ plainto_tsquery('english', ${idx})"
                )
                params.append(q)
                idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            sql = f"SELECT count(*) FROM event_meeting_document WHERE {where_sql}"

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Meeting documents count error: {e}")
            span.record_exception(e)
            return 0


async def count_topics(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    topic_tsquery: Optional[str] = None,
) -> int:
    """Count meeting topics matching the topics search filters.

    Mirrors the WHERE predicates of search_postgres.search_topics_pg over
    public.event_topic: the same state_code filter, the same exact-name city scope
    (jurisdiction_name OR city), and the same headline/theme FTS + theme ILIKE for
    a query. event_topic is small (~12k rows) so this count(*) is sub-second.
    Result cached for 1 hour.
    """
    norm_state = search_postgres.normalize_state_input(state)
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_topics_{norm_state}_{city}_{query}_{topic_tsquery}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_topics") as span:
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
                where_clauses.append(
                    f"(lower(jurisdiction_name) = lower(${idx}) OR lower(city) = lower(${idx}))"
                )
                params.append(city.strip())
                idx += 1

            if has_query:
                where_clauses.append(
                    f"(to_tsvector('english', COALESCE(headline, '') || ' ' || "
                    f"COALESCE(primary_theme, '')) @@ plainto_tsquery('english', ${idx}) "
                    f"OR primary_theme ILIKE ${idx + 1})"
                )
                params.append(q)
                params.append(f"%{q}%")
                idx += 2

            if topic_tsquery:
                # Mirror search_topics_pg civic-topic narrowing.
                where_clauses.append(
                    f"to_tsvector('english', COALESCE(headline, '') || ' ' || "
                    f"COALESCE(primary_theme, '')) @@ to_tsquery('english', ${idx})"
                )
                params.append(topic_tsquery)
                idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            sql = f"SELECT count(*) FROM event_topic WHERE {where_sql}"

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Topics count error: {e}")
            span.record_exception(e)
            return 0


async def count_causes(query: Optional[str] = None) -> int:
    """Count NTEE causes matching the causes search filter.

    Mirrors the WHERE predicates of search_postgres.search_causes_pg over
    public.tag (vocabulary='ntee'): the label/description FTS + source_code ILIKE
    for a query. tag(ntee) is a tiny bounded vocabulary (~200 rows). Causes carry
    no geography, so there is no state/city filter. Result cached for 1 hour.
    """
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_causes_{query}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_causes") as span:
        span.set_attribute("search.has_query", has_query)
        try:
            where_clauses: List[str] = ["vocabulary = 'ntee'"]
            params: List[Any] = []
            idx = 1

            if has_query:
                where_clauses.append(
                    f"(to_tsvector('english', COALESCE(label, '') || ' ' || "
                    f"COALESCE(description, '')) @@ plainto_tsquery('english', ${idx}) "
                    f"OR source_code ILIKE ${idx + 1})"
                )
                params.append(q)
                params.append(f"%{q}%")
                idx += 2

            where_sql = " AND ".join(where_clauses)
            sql = f"SELECT count(*) FROM tag WHERE {where_sql}"

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Causes count error: {e}")
            span.record_exception(e)
            return 0


async def count_questions(query: Optional[str] = None, question_id: Optional[str] = None) -> int:
    """Count policy questions matching the questions search filter.

    Mirrors the WHERE predicate of search_postgres.search_questions_pg over
    public.policy_question: the canonical_text ILIKE for a query (browse counts the
    whole registry). The policy-question registry is a small curated/clustered set
    (no FTS index needed) and carries no geography, so there is no state/city
    filter. Result cached for 1 hour.
    """
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_questions_{query}_{question_id}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_questions") as span:
        span.set_attribute("search.has_query", has_query)
        try:
            where_clauses: List[str] = []
            params: List[Any] = []
            idx = 1

            if question_id:
                # Question filter (Advanced): pin to the single chosen question
                # (mirrors search_questions_pg's question_id predicate). The exact
                # question may not be featured, so this is NOT gated on is_featured.
                where_clauses.append(f"question_id = ${idx}")
                params.append(question_id)
                idx += 1
            else:
                # For now the whole site focuses on the curated/pinned "big questions"
                # only — mirror search_questions_pg and count just the featured set.
                where_clauses.append("is_featured = true")

                if has_query:
                    # Mirror search_questions_pg: match canonical_text OR any alias
                    # (e.g. 'airbnb'/'vrbo' -> short-term-rental question) so the
                    # tab count agrees with the returned results.
                    where_clauses.append(
                        f"(canonical_text ILIKE ${idx} "
                        f"OR EXISTS (SELECT 1 FROM unnest(aliases) a WHERE a ILIKE ${idx}))"
                    )
                    params.append(f"%{q}%")
                    idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            sql = f"SELECT count(*) FROM policy_question WHERE {where_sql}"

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Questions count error: {e}")
            span.record_exception(e)
            return 0


async def count_grants(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
) -> int:
    """Count nonprofit grants matching the grants search filters (CAPPED).

    Mirrors the WHERE predicates of search_postgres.search_grants_pg over
    public.grant: grantor-location scope (jurisdiction_id via the org bridge, else
    indexed grantor_state_code / grantor_city_norm) and the grantor/grantee/purpose
    ILIKE for a query.

    public.grant is ~6.7M rows with NO full-text index, so an UNSCOPED count is a
    ~10s seq-scan (over the sub-search timeout). The caller therefore only invokes
    this when the search is LOCATION-SCOPED — those hit the indexed grantor columns
    and count in <0.5s. The count is additionally capped via a LIMIT subquery
    (GRANT_COUNT_CAP) so even a large state can't run long; a returned value == the
    cap means "this many or more". Result cached for 1 hour.
    """
    norm_state = search_postgres.normalize_state_input(state)
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_grants_{norm_state}_{city}_{jurisdiction_id}_{query}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_grants") as span:
        span.set_attribute("search.has_state", bool(norm_state))
        span.set_attribute("search.has_city", bool(city and city.strip()))
        span.set_attribute("search.has_jurisdiction", bool(jurisdiction_id))
        span.set_attribute("search.has_query", has_query)
        try:
            where_clauses: List[str] = []
            params: List[Any] = []
            idx = 1

            # Grantor-location scope (mirrors search_grants_pg). jurisdiction_id
            # (exact) goes through the org bridge; else indexed direct columns.
            if jurisdiction_id:
                where_clauses.append(
                    f"grantor_master_org_id IN ("
                    f"SELECT master_org_id FROM mdm_bridge_org_jurisdiction "
                    f"WHERE jurisdiction_id = ${idx})"
                )
                params.append(jurisdiction_id)
                idx += 1
            else:
                if norm_state:
                    where_clauses.append(f"grantor_state_code = ${idx}")
                    params.append(norm_state.upper())
                    idx += 1
                if city and city.strip():
                    where_clauses.append(f"lower(grantor_city_norm) = lower(${idx})")
                    params.append(city.strip())
                    idx += 1

            if has_query:
                where_clauses.append(
                    f"(grantor_name ILIKE ${idx} OR grantee_name ILIKE ${idx} "
                    f"OR purpose ILIKE ${idx})"
                )
                params.append(f"%{q}%")
                idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            # Cap the work: stop counting once GRANT_COUNT_CAP matches are seen.
            sql = (
                f'SELECT count(*) FROM '
                f'(SELECT 1 FROM "grant" WHERE {where_sql} LIMIT {GRANT_COUNT_CAP}) t'
            )

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Grants count error: {e}")
            span.record_exception(e)
            return 0


async def count_grant_opportunities(query: Optional[str] = None) -> int:
    """Count federal grant opportunities matching the search filter.

    Mirrors the WHERE predicates of search_postgres.search_grant_opportunities_pg
    over public.grant_opportunity: the title/agency/number ILIKE for a query.
    Opportunities carry no resolved geography, so (like the search) state/city are
    NOT applied — the feed is national. ~1.9k rows, so count(*) is sub-millisecond.
    Result cached for 1 hour.
    """
    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    cache_key = f"count_grant_opportunities_{query}"
    now = datetime.now()
    if cache_key in _count_cache:
        cached_time = _count_cache_ttl.get(cache_key)
        if cached_time and (now - cached_time).total_seconds() < 3600:
            return _count_cache[cache_key]

    with tracer.start_as_current_span("search.count_grant_opportunities") as span:
        span.set_attribute("search.has_query", has_query)
        try:
            where_clauses: List[str] = []
            params: List[Any] = []
            idx = 1

            if has_query:
                where_clauses.append(
                    f"(title ILIKE ${idx} OR agency_name ILIKE ${idx} "
                    f"OR opportunity_number ILIKE ${idx})"
                )
                params.append(f"%{q}%")
                idx += 1

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            sql = f"SELECT count(*) FROM grant_opportunity WHERE {where_sql}"

            pool = await search_postgres.get_db_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(sql, *params)

            count = int(count or 0)
            span.set_attribute("search.count", count)
            _count_cache[cache_key] = count
            _count_cache_ttl[cache_key] = now
            return count
        except Exception as e:
            logger.error(f"Grant opportunities count error: {e}")
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
        # Bound each sub-search so one slow type can't sink the whole fan-out.
        # On timeout we record it on the span and re-raise: the dispatcher's
        # return_exceptions=True path then logs it and degrades this type to
        # empty results, leaving the fast types intact.
        try:
            outcome = await asyncio.wait_for(coro, timeout=SUBSEARCH_TIMEOUT_S)
        except asyncio.TimeoutError:
            span.set_attribute("search.timed_out", True)
            span.set_attribute("search.timeout_s", SUBSEARCH_TIMEOUT_S)
            logger.warning(
                f"⏱️ {label} search exceeded {SUBSEARCH_TIMEOUT_S}s — degrading to empty results"
            )
            raise
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
    types: Optional[str] = Query(None, description="Comma-separated result types: leaders,persons,meetings,organizations,causes,jurisdictions,bills,topics,decisions,questions,documents,meeting_documents,grants,grant_opportunities. Legacy aliases accepted: 'contacts'/'officials' -> 'leaders', 'people'/'person' -> 'persons'"),
    state: Optional[str] = Query(None, description="Filter by state (2-letter code)"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    jurisdiction_id: Optional[str] = Query(None, description="Filter by exact jurisdiction_id (city, county, or state) — scopes orgs/persons/grants through the MDM jurisdiction bridges"),
    jurisdiction_levels: Optional[str] = Query(None, description="Comma-separated jurisdiction levels: city,county,town,village,school_district,special_district,state"),
    ntee_code: Optional[str] = Query(None, description="Filter organizations by NTEE code"),
    ein: Optional[str] = Query(None, description="Filter organizations by exact EIN (for direct organization links)"),
    session: Optional[str] = Query(None, description="Filter bills by legislative session"),
    document_type: Optional[str] = Query(None, description="Filter meeting_documents by type: 'agenda', 'minutes', or 'attachment'"),
    topic_id: Optional[int] = Query(None, description="Filter by a named civic topic (public.civicsearch_topic.topic_id) — narrows decisions/meetings/topics to that topic's keyword set"),
    cause_id: Optional[str] = Query(None, description="Filter by an EveryOrg cause slug (e.g. 'housing','education','mental-health') — narrows decisions/meetings/topics to that cause's keyword set, matched through child decisions then transcript content"),
    question_id: Optional[str] = Query(None, description="Filter by a policy question (public.policy_question.question_id) — narrows decisions to those instantiating it, plus the question itself"),
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
    logger.info(f"🔍 SEARCH REQUEST: q={q!r}, types={types!r}, state={state!r}, city={city!r}, jurisdiction_id={jurisdiction_id!r}, jurisdiction_levels={jurisdiction_levels!r}, ntee_code={ntee_code!r}, ein={ein!r}, session={session!r}, topic_id={topic_id!r}, question_id={question_id!r}, limit={limit}, offset={offset}, page={page}, enrich={enrich}, sort={sort!r}")
    
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
            requested_types = ['leaders', 'persons', 'meetings', 'organizations', 'causes', 'jurisdictions', 'bills', 'topics', 'decisions', 'questions', 'documents', 'meeting_documents', 'grants', 'grant_opportunities']

        # Scope cut: drop the non-government "persons" category (mdm_person) unless
        # explicitly re-enabled. Stripping it here (rather than per-task) means
        # neither search_persons_pg nor count_persons runs, so the heavy mdm_person
        # graph is never touched. 'people'/'person' aliases already normalized to
        # 'persons' above, so they're covered too. See PERSONS_SEARCH_ENABLED.
        if not PERSONS_SEARCH_ENABLED:
            requested_types = [t for t in requested_types if t != 'persons']

        # Advanced "Topic" / "Question" filters. Each narrows the result set to the
        # types it can honor, dropping the rest so the filter genuinely constrains
        # what is shown (mirrors how the org-only Cause filter scopes its effect):
        #   - topic_id  -> a named civic topic (civicsearch_topic): keyword-narrows
        #     decisions / meetings / topics. Resolved to an OR-tsquery once here.
        #   - question_id -> a policy question (policy_question): narrows decisions
        #     that instantiate it (via question_instance) + pins the questions tab.
        # When both are set the supported sets intersect to {decisions}.
        #   - cause_id  -> an EveryOrg cause (CAUSE_KEYWORDS): keyword-narrows the
        #     same decisions/meetings/topics set. A cause is just another keyword
        #     cluster, so it resolves to the SAME kind of OR-tsquery and rides the
        #     identical decision-FTS + transcript-content path (cause -> decision ->
        #     meeting, transcript fallback). topic & cause AND together when both set.
        topic_tsquery = None
        _facet_parts: List[str] = []
        if topic_id is not None:
            _tq = await resolve_topic_tsquery(topic_id)
            if _tq:
                _facet_parts.append(_tq)
        if cause_id:
            _cq = resolve_cause_tsquery(cause_id)
            if _cq:
                _facet_parts.append(_cq)
        if _facet_parts:
            # Each facet is an OR-cluster; AND the facets so both narrow the result.
            topic_tsquery = " & ".join(f"({p})" for p in _facet_parts)
            _topic_types = {'decisions', 'meetings', 'topics'}
            requested_types = [t for t in requested_types if t in _topic_types] or list(_topic_types)
        if question_id:
            _question_types = {'decisions', 'questions'}
            requested_types = [t for t in requested_types if t in _question_types] or list(_question_types)

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

        # "leaders" — elected/appointed government officials (contact_official),
        # title-aware so a query like "Mayor" returns officials (result_type='leader').
        # This is now its OWN category, distinct from "persons". (Aliases
        # 'contacts'/'officials' already normalized to 'leaders' above.)
        if 'leaders' in requested_types:
            search_tasks.append(('leaders', search_postgres.search_officials_pg(q, state, city=city, limit=search_limit)))

        if 'meetings' in requested_types:
            search_tasks.append(('meetings', search_postgres.search_events_pg(q, state, city=city, limit=search_limit, offset=search_offset, topic_tsquery=topic_tsquery)))

        if 'organizations' in requested_types:
            search_tasks.append(('organizations', search_postgres.search_organizations_pg(q, state, city, ntee_code, ein, jurisdiction_id=jurisdiction_id, limit=search_limit, offset=search_offset, sort=sort)))

        if 'bills' in requested_types:
            search_tasks.append(('bills', search_postgres.search_bills_pg(q, state, session, city=city, limit=search_limit, offset=search_offset)))

        if 'grants' in requested_types:
            # Nonprofit grants (public.grant) — ILIKE over grantor/grantee/purpose,
            # ordered by amount DESC. Location filter is by GRANTOR geography
            # (jurisdiction_id via the org bridge, else state/city direct).
            # Graceful no-op if the mart is unbuilt.
            search_tasks.append(('grants', search_postgres.search_grants_pg(q, state, city=city, jurisdiction_id=jurisdiction_id, limit=search_limit, offset=search_offset)))

        if 'grant_opportunities' in requested_types:
            # Federal grant opportunities (public.grant_opportunity) — Grants.gov
            # open/forecasted funding ("what's available now"), DISTINCT from the
            # 990 'grants' bucket above. ILIKE over title/agency/number, ordered
            # open-first then soonest deadline. Graceful no-op if the mart is unbuilt.
            search_tasks.append(('grant_opportunities', search_postgres.search_grant_opportunities_pg(q, state, city=city, jurisdiction_id=jurisdiction_id, limit=search_limit, offset=search_offset)))

        if 'topics' in requested_types:
            search_tasks.append(('topics', search_postgres.search_topics_pg(q, state, ntee_code, city=city, limit=search_limit, offset=search_offset, topic_tsquery=topic_tsquery)))

        if 'decisions' in requested_types:
            search_tasks.append(('decisions', search_postgres.search_decisions_pg(q, state, city=city, sort=sort, limit=search_limit, offset=search_offset, question_id=question_id, topic_tsquery=topic_tsquery)))

        if 'questions' in requested_types:
            # Cross-jurisdiction policy-question registry (public.policy_question):
            # canonical_text ILIKE on a query, curated featured rows first on browse.
            # National registry (no geography), so state/city filters don't apply.
            search_tasks.append(('questions', search_postgres.search_questions_pg(q, limit=search_limit, offset=search_offset, question_id=question_id)))

        if 'documents' in requested_types:
            # Full-text search over meeting transcripts (public.event_documents)
            search_tasks.append(('documents', search_postgres.search_documents_pg(q, state, city=city, limit=search_limit, offset=search_offset)))

        if 'meeting_documents' in requested_types:
            # Full-text search over official meeting documents — agenda / minutes /
            # attachments (public.event_meeting_document), filterable by document_type.
            search_tasks.append(('meeting_documents', search_postgres.search_meeting_documents_pg(q, state, city=city, document_type=document_type, limit=search_limit, offset=search_offset)))

        if 'causes' in requested_types:
            # NTEE causes now come from public.tag (vocabulary='ntee'); the old
            # causes_ntee_codes.parquet feed was retired.
            search_tasks.append(('causes', search_postgres.search_causes_pg(q, limit=search_limit, offset=search_offset)))

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
            'questions': [r.to_dict() for r in paginated_results if r.result_type == 'question'],
            'causes': [r.to_dict() for r in paginated_results if r.result_type == 'cause'],
            'jurisdictions': [r.to_dict() for r in paginated_results if r.result_type == 'jurisdiction'],
            'documents': [r.to_dict() for r in paginated_results if r.result_type == 'document'],
            'meeting_documents': [r.to_dict() for r in paginated_results if r.result_type == 'meeting_document'],
            'grants': [r.to_dict() for r in paginated_results if r.result_type == 'grant'],
            'grant_opportunities': [r.to_dict() for r in paginated_results if r.result_type == 'grant_opportunity'],
        }

        logger.info(f"📦 Grouped results - leaders:{len(grouped_results['leaders'])}, persons:{len(grouped_results['persons'])}, meetings:{len(grouped_results['meetings'])}, organizations:{len(grouped_results['organizations'])}, bills:{len(grouped_results['bills'])}, topics:{len(grouped_results['topics'])}, decisions:{len(grouped_results['decisions'])}, causes:{len(grouped_results['causes'])}, jurisdictions:{len(grouped_results['jurisdictions'])}, grants:{len(grouped_results['grants'])}, grant_opportunities:{len(grouped_results['grant_opportunities'])}")

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
            'questions': len([r for r in all_results if r.result_type == 'question']),
            'causes': len([r for r in all_results if r.result_type == 'cause']),
            'jurisdictions': len([r for r in all_results if r.result_type == 'jurisdiction']),
            'documents': len([r for r in all_results if r.result_type == 'document']),
            'meeting_documents': len([r for r in all_results if r.result_type == 'meeting_document']),
            'grants': len([r for r in all_results if r.result_type == 'grant']),
            'grant_opportunities': len([r for r in all_results if r.result_type == 'grant_opportunity']),
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
        # jurisdictions, documents, grants, and grant_opportunities still report fetched-length totals
        # (their type_totals can under-count a broad filtered search). Adding
        # COUNT helpers for those is a follow-up; scoped here to the high-traffic
        # leaders + persons (+ existing organizations) path.
        is_filtered = bool(q) or bool(state) or bool(city) or bool(jurisdiction_id)

        # The per-type COUNT helpers below are each cached (1h), but on a COLD
        # cache they used to run back-to-back with `await`, so their latencies
        # COMPOUNDED: a fresh broad search ("affordable housing" with no scope)
        # paid sum(counts) over ~11 types (~10s), even though every count is an
        # independent indexed query. Dispatch them CONCURRENTLY — exactly like the
        # subsearch fan-out above — so the count phase is as slow as its single
        # slowest count, not their sum. Each (key, coro) carries the SAME guard as
        # before, so the set of counts run is unchanged; only the scheduling
        # differs. return_exceptions keeps one slow/failing count from sinking the
        # whole search: that type silently falls back to its fetched-length
        # estimate (the pre-existing type_totals value).
        count_tasks: List[tuple] = []

        if not q and len(requested_types) == 1 and 'organizations' in requested_types:
            # Single-type org browse: accurate count (unchanged behavior).
            count_tasks.append(('organizations', count_organizations(
                state=state, ntee_code=ntee_code, query=q
            )))

        # Accurate per-type counts for the paginated people categories whenever
        # the result set is filtered (query and/or location scope).
        if is_filtered and 'leaders' in requested_types:
            count_tasks.append(('leaders', count_leaders(query=q, state=state, city=city)))
        if is_filtered and 'persons' in requested_types:
            count_tasks.append(('persons', count_persons(
                query=q, state=state, city=city, jurisdiction_id=jurisdiction_id
            )))

        # Meetings: event_meeting is tiny (~6k rows) so a real COUNT is sub-ms.
        # Always use it (not the fetched-length estimate) so the count is
        # independent of the caller's limit — the lightweight tab-counts call
        # sends limit=1, which would otherwise cap the meetings total at 1 in
        # single-type browse mode (header said "1 results" over a 20-row page).
        if 'meetings' in requested_types:
            count_tasks.append(('meetings', count_events(
                query=q, state=state, city=city, topic_tsquery=topic_tsquery
            )))

        # Decisions: event_decision is small (~9k rows) so a real COUNT is sub-ms.
        # Always use it (like meetings) so the count is independent of the caller's
        # limit — the tab-counts call sends limit=1, which would otherwise cap the
        # decisions total and leave the homepage "Search in" badge blank in browse.
        if 'decisions' in requested_types:
            count_tasks.append(('decisions', count_decisions(
                query=q, state=state, city=city, question_id=question_id, topic_tsquery=topic_tsquery
            )))

        # Bills & transcripts: the other small meeting-derived civic marts. Real
        # COUNTs (event_bill ~14k ILIKE/title-FTS; event_documents via the GIN
        # content_tsv) so their tab badges and pagers don't collapse to the
        # fetched-length estimate under the limit=1 tab-counts call.
        if 'bills' in requested_types:
            count_tasks.append(('bills', count_bills(query=q, state=state, city=city)))
        if 'documents' in requested_types:
            count_tasks.append(('documents', count_documents(query=q, state=state, city=city)))

        # Meeting documents: the tiny (~2,900-row) official-document mart
        # (event_meeting_document). Honest GIN-backed count so the tab badge/pager
        # don't collapse under the limit=1 tab-counts call.
        if 'meeting_documents' in requested_types:
            count_tasks.append(('meeting_documents', count_meeting_documents(query=q, state=state, city=city, document_type=document_type)))

        # Topics: city-scoped meeting-derived mart (event_topic, ~12k), same shape
        # as bills/decisions — honest count so the badge/pager don't collapse.
        if 'topics' in requested_types:
            count_tasks.append(('topics', count_topics(
                query=q, state=state, city=city, topic_tsquery=topic_tsquery
            )))

        # Causes: tiny national NTEE vocabulary (public.tag, ~200 rows), no
        # geography — honest count over the matched taxonomy.
        if 'causes' in requested_types:
            count_tasks.append(('causes', count_causes(query=q)))

        # Questions: small curated/clustered policy-question registry
        # (public.policy_question), no geography — honest canonical_text count so
        # the tab badge/pager don't collapse under the limit=1 tab-counts call.
        if 'questions' in requested_types:
            count_tasks.append(('questions', count_questions(query=q, question_id=question_id)))

        # Grant opportunities: small national feed (~1.9k) — cheap honest count.
        if 'grant_opportunities' in requested_types:
            count_tasks.append(('grant_opportunities', count_grant_opportunities(query=q)))

        # Grants: public.grant is ~6.7M rows with NO full-text index, so an
        # UNSCOPED count is a ~10s seq-scan (over the sub-search timeout). Only run
        # the (capped) honest count when the search is LOCATION-SCOPED — those use
        # the indexed grantor columns / org bridge and count in <0.5s. Otherwise
        # leave the fetched-length estimate rather than risk the slow path.
        if 'grants' in requested_types and (state or city or jurisdiction_id):
            count_tasks.append(('grants', count_grants(
                query=q, state=state, city=city, jurisdiction_id=jurisdiction_id
            )))

        if count_tasks:
            count_keys = [key for key, _ in count_tasks]
            with tracer.start_as_current_span(
                "search.counts", kind=SpanKind.INTERNAL
            ) as count_span:
                count_span.set_attribute("search.count_types", ",".join(count_keys))
                count_span.set_attribute("search.count_type_count", len(count_keys))
                # Bound each count the same way the subsearch fan-out is bounded
                # (asyncio.wait_for at SUBSEARCH_TIMEOUT_S). A pathological count —
                # e.g. an event_documents FTS leg that runs long under pool
                # contention — must not be able to drag the whole response past
                # the frontend's fetch-abort window. On timeout the count raises,
                # the return_exceptions=True path below logs it, and that type
                # silently keeps its fetched-length estimate.
                counted = await asyncio.gather(
                    *(
                        asyncio.wait_for(coro, timeout=SUBSEARCH_TIMEOUT_S)
                        for _, coro in count_tasks
                    ),
                    return_exceptions=True,
                )
            for key, outcome in zip(count_keys, counted):
                if isinstance(outcome, Exception):
                    # Degrade gracefully: keep the fetched-length estimate already
                    # in type_totals rather than failing the whole search.
                    logger.error(f"❌ {key} count failed: {outcome}")
                    continue
                type_totals[key] = outcome

        # NOTE: the per-type counts are dispatched once, concurrently, in the
        # count_tasks gather above. There is intentionally NO sequential per-type
        # `await count_*()` block here: an earlier refactor (#154) moved these
        # counts into the concurrent gather but left a duplicate sequential block
        # behind, so every count ran twice — and the sequential copies dropped the
        # topic_tsquery / question_id filters, silently overwriting the correct
        # concurrent results with unfiltered ones. Add any new count to
        # count_tasks above, not here.

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
                "topic_id": topic_id,
                "cause_id": cause_id,
                "question_id": question_id,
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
