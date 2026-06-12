"""
PostgreSQL-based search functions
Uses indexed search tables for fast queries (10-100x faster than parquet)
"""
from typing import Any, Optional, List
from urllib.parse import quote
from loguru import logger
import asyncpg
import os
import re
from datetime import datetime
from dataclasses import dataclass
from api.utils.formatters import format_organization_id, format_role_type, format_title
from api.database import DATA_SEARCH_PATH

# Database configuration
# Priority: NEON_DATABASE_URL_DEV (local) > NEON_DATABASE_URL (production)
NEON_DATABASE_URL_DEV = os.getenv('NEON_DATABASE_URL_DEV')
NEON_DATABASE_URL = os.getenv('NEON_DATABASE_URL')

# Use dev database for local development, production database for deployed environments
DATABASE_URL = NEON_DATABASE_URL_DEV or NEON_DATABASE_URL

# Person search (mdm_person ~13.8M rows): cap how many ILIKE-matched candidates
# we rank/dedup so a broad substring (e.g. '%jo%' ~ 900k rows) can't stall the
# query. Selective name queries return far fewer than this and are unaffected.
PERSON_CANDIDATE_CAP = 3000

# Organization search (mdm_organization 4.2M JOIN nonprofit satellite 3.6M):
# - Browse/name sorts order by org_name_norm (btree-indexed) instead of org_name,
#   so the first page is an index scan, not a 3.6M-row sort (~6s -> instant).
# - For a text query, ts_rank over the full match set is fatal: a common word like
#   "school" matches ~530k orgs and even COUNTing them takes ~5s. Cap the FTS
#   candidate scan (the GIN index fills the cap and stops), then rank/sort only
#   those — selective queries return far fewer and rank exactly as before.
ORG_CANDIDATE_CAP = 2000

# Document search: ts_headline + detoasting the matched transcript bodies
# (content averages 43KB and is TOASTed) costs ~40ms/row, so the cost scales with
# how many rows we snippet. The unified search over-fetches (limit + 100) to mix
# across types, but every document shares a constant score=1.0 (the buffer never
# changes their order), so snippeting 120 rows to show ~20 is pure waste. Cap the
# rows we rank+snippet to a page's worth: turns a ~5s document search into <1s.
DOCUMENT_RESULT_CAP = 25

# A common 2-word query (e.g. "school board") matches ~half of the 119k
# transcripts; ts_rank-sorting that whole set detoasts every large content_tsv
# and stalls ~12s. Instead we pull a bounded, GIN-indexed pool of the most
# RECENT matches and rank only that pool — turning the 12s into <200ms. The pool
# is sized to cover the requested page; results are still ordered by ts_rank
# (relevance) within it, with recency as the tie-break.
DOCUMENT_CANDIDATE_POOL = 400

# Connection pools (created on first request)
_db_pool = None  # Production database pool (Neon)

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

# SQL CASE mapping a 2-letter code back to a full state name, derived from
# STATE_NAME_TO_CODE so the two never drift. Used to recover the full `state`
# name when serving orgs from mdm_organization (which carries only state_code).
# References an unqualified `state_code` so it can run in an outer projection over
# already-filtered/capped rows (computing this 50-branch CASE per row before the
# candidate cap, over the full 3.6M-row join, was a major org-search slowdown).
_STATE_NAME_CASE = "CASE state_code\n" + "\n".join(
    f"                    WHEN '{code}' THEN '{name.replace(chr(39), chr(39) * 2)}'"
    for name, code in STATE_NAME_TO_CODE.items()
) + "\n                    ELSE NULL END"

# Python reverse of STATE_NAME_TO_CODE: 2-letter code -> full state name. Used
# to render human-friendly locations ("MA" -> "Massachusetts") in serving
# strings (e.g. the grant subtitle) without a round-trip to the DB CASE above.
_STATE_CODE_TO_NAME = {code: name for name, code in STATE_NAME_TO_CODE.items()}


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
    # None when the row has no stable detail key (e.g. an MDM person with a
    # null person_uid) — the frontend renders these as non-clickable so they
    # can't navigate to a 404.
    url: Optional[str]
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
        
        _db_pool = await asyncpg.create_pool(
            DATABASE_URL, min_size=2, max_size=20,
            server_settings={"search_path": DATA_SEARCH_PATH},
        )
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
                # Filter on the canonical jurisdiction_type column (the mart exposes
                # the API-level values city/county/town/.../state under that name).
                where_clauses.append(f"jurisdiction_type IN ({placeholders})")
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


async def search_persons_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
    limit: int = 10
) -> List[SearchResult]:
    """
    Search people using PostgreSQL, backed by the MDM person master (mdm_person).

    - Deduplicates to one result per RESOLVED person (master_person_id), picking
      the best source occurrence.
    - Matches names with trigram similarity (typo-tolerant; uses the
      mdm_person_full_name_trgm_idx GIN index).
    - Joins mdm_bridge_person_organization for the person's top org / title.

    Location scoping (city / jurisdiction_id) goes through the MDM
    person<->jurisdiction bridge (mdm_bridge_person_jurisdiction), keyed on
    p.person_uid — the same allocation pattern used for orgs:
      - jurisdiction_id -> EXISTS on that exact jurisdiction_id.
      - city (+ state) -> resolve to the city/town jurisdiction(s) and keep persons
        bridged to one of them.
    The existing state filter (direct p.state_code) and the org-name anti-join are
    preserved.

    Replaces the retired `contact` table feed (which no longer exists).

    Args:
        query: Search text (person name)
        state: Filter by state code ('MA') or full name ('Massachusetts')
        city: Filter by city name (resolved to a city/town jurisdiction via the bridge)
        jurisdiction_id: Exact jurisdiction scope (city, county, or state) via the bridge
        limit: Max results

    Returns:
        List of SearchResult objects (result_type='person')
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)

    try:
        pool = await get_db_pool()

        where_clauses = []
        params = []
        idx = 1

        if state:
            where_clauses.append(f"p.state_code = ${idx}")
            params.append(state.upper())
            idx += 1

        # Location scope via the MDM person<->jurisdiction bridge, keyed on
        # p.person_uid (mdm_person's true PK). Mirrors the org bridge filter.
        if jurisdiction_id:
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM mdm_bridge_person_jurisdiction bj "
                f"WHERE bj.person_uid = p.person_uid "
                f"AND bj.jurisdiction_id = ${idx})"
            )
            params.append(jurisdiction_id)
            idx += 1
        elif city:
            city_pred = (
                f"p.person_uid IN ("
                f"SELECT bj.person_uid FROM mdm_bridge_person_jurisdiction bj "
                f"JOIN jurisdictions j ON j.jurisdiction_id = bj.jurisdiction_id "
                f"WHERE lower(j.name) = lower(${idx}) "
                f"AND j.jurisdiction_type IN ('city','town')"
            )
            params.append(city.strip())
            idx += 1
            if state:
                city_pred += f" AND j.state_code = ${idx}"
                params.append(state.upper())
                idx += 1
            city_pred += ")"
            where_clauses.append(city_pred)

        # A 1-char name query is all noise and matches millions; skip the work
        # (the per-keystroke typeahead starts firing useful results at 2 chars).
        if query and query.strip() and len(query.strip()) < 2 and not state:
            return []

        has_query = bool(query and query.strip())
        if has_query:
            q = query.strip()
            params.append(f"%{q}%")
            like_idx = idx
            idx += 1
            params.append(q)
            sim_idx = idx
            idx += 1
            where_clauses.append(f"p.full_name ILIKE ${like_idx}")
            sim_select = f"similarity(p.full_name, ${sim_idx}) AS sim"
            # DISTINCT ON requires the partition key first; pick the best
            # occurrence per resolved person.
            inner_order = f"p.master_person_id, similarity(p.full_name, ${sim_idx}) DESC, p.match_confidence DESC NULLS LAST"
            outer_order = "sim DESC NULLS LAST, full_name ASC"
        else:
            sim_select = "0::real AS sim"
            inner_order = "p.master_person_id"
            outer_order = "full_name ASC"

        # mdm_person is officer-derived (source_system='bronze_990_officers'), so a
        # chunk of "people" are really organization names that leaked in from the
        # Form 990 officer roster (e.g. "World Resources Institute", "Elias Law
        # Group", "Carequest Institute For Oral Health"). Those belong under
        # Organizations, not People. Drop any candidate whose normalized name is an
        # exact known organization name. name_norm and org_name_norm use the same
        # normalization, so this is precise (a real person like "Bill Center" has no
        # matching org and is kept). Cheap on the typeahead path: it runs only over
        # the trgm-capped candidate set and probes the mdm_organization_org_name_norm_idx.
        where_clauses.append(
            "NOT EXISTS (SELECT 1 FROM mdm_organization o WHERE o.org_name_norm = p.name_norm)"
        )

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # limit param is shared by both branches
        limit_idx = idx
        params.append(limit)

        base_select = f"""
            p.master_person_id,
            p.person_uid,
            p.source_pk,
            p.full_name,
            p.email,
            p.phone,
            p.city_norm,
            p.state_code,
            {sim_select}"""

        # Org affiliation (top by recency / reported comp). The bridge's
        # officer_person_uid = md5(name_norm|ein) == mdm_person.source_pk for
        # officer-sourced people (person_uid is a *different*, double-hashed key,
        # so we must join on source_pk). Indexed by
        # mdm_bridge_person_organization_officer_uid_idx.
        lateral = """
            LEFT JOIN LATERAL (
                SELECT b.org_name, b.master_org_id, b.title, b.reportable_comp_org,
                       n.ein, n.ntee_description, n.ntee_code,
                       n.gt990_total_revenue, n.gt990_total_assets, n.gt990_source_url
                FROM mdm_bridge_person_organization b
                LEFT JOIN mdm_organization_nonprofit n
                    ON n.master_org_id = b.master_org_id
                WHERE b.officer_person_uid = d.source_pk
                ORDER BY tax_year DESC NULLS LAST, reportable_comp_org DESC NULLS LAST
                LIMIT 1
            ) o ON TRUE"""

        if has_query:
            # A bare substring like '%jo%' matches ~900k of the 13.8M people, and
            # ranking/deduping that whole set takes ~20s — fatal for per-keystroke
            # typeahead. Cap the candidate scan first (the trgm GIN index lets the
            # ILIKE fill the cap fast); we then dedup+rank only those. Selective
            # queries ("john bowyer" -> 3 rows) never hit the cap.
            sql = f"""
                SELECT d.*, o.org_name, o.master_org_id, o.title, o.reportable_comp_org,
                       o.ein, o.ntee_description, o.ntee_code,
                       o.gt990_total_revenue, o.gt990_total_assets, o.gt990_source_url
                FROM (
                    SELECT * FROM (
                        SELECT DISTINCT ON (p.master_person_id)
                            {base_select}
                        FROM (
                            SELECT master_person_id, person_uid, source_pk, full_name,
                                   email, phone, city_norm, state_code, match_confidence
                            FROM mdm_person p
                            WHERE {where_sql}
                            LIMIT {PERSON_CANDIDATE_CAP}
                        ) p
                        ORDER BY {inner_order}
                    ) dd
                    ORDER BY {outer_order}
                    LIMIT ${limit_idx}
                ) d
                {lateral}
                ORDER BY {outer_order}
            """
        else:
            # Browse (no name query): cap the candidate scan FIRST so a city filter
            # that resolves to tens of thousands of person<->jurisdiction bridge rows
            # (e.g. Tuscaloosa ~29k) can't force a full materialize + on-disk sort for
            # a 20-row page. Without the cap, `DISTINCT ON ... ORDER BY master_person_id
            # LIMIT 20` builds every matching row and external-merge sorts it (~1.1s,
            # spills to disk) because the `person_uid IN (bridge)` filter isn't aligned
            # with the master_person_id sort order. The inner LIMIT lets Postgres stop
            # after PERSON_CANDIDATE_CAP matched rows; we then dedup those to distinct
            # people. Browse is unranked, so capping only affects *which* arbitrary page
            # of people shows, not correctness.
            sql = f"""
                SELECT d.*, o.org_name, o.master_org_id, o.title, o.reportable_comp_org,
                       o.ein, o.ntee_description, o.ntee_code,
                       o.gt990_total_revenue, o.gt990_total_assets, o.gt990_source_url
                FROM (
                    SELECT DISTINCT ON (p.master_person_id)
                        {base_select}
                    FROM (
                        SELECT master_person_id, person_uid, source_pk, full_name,
                               email, phone, city_norm, state_code, match_confidence
                        FROM mdm_person p
                        WHERE {where_sql}
                        LIMIT {PERSON_CANDIDATE_CAP}
                    ) p
                    ORDER BY p.master_person_id
                    LIMIT ${limit_idx}
                ) d
                {lateral}
                ORDER BY {outer_order}
            """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                name = row['full_name'] or 'Unknown'
                org = row['org_name']
                org_display = org if org else 'No known organization'
                title = format_title(row['title']) if row['title'] else 'Person'
                # Title-case the (lowercased) city and expand the 2-letter code
                # to the full state name ("boston", "MA" -> "Boston,
                # Massachusetts"). Raw values stay in metadata below.
                _p_city = (row['city_norm'] or '').strip()
                _p_city_display = _p_city.title() if _p_city else ''
                _p_code = row['state_code'] or ''
                _p_state_display = _STATE_CODE_TO_NAME.get(_p_code, _p_code)
                location = ", ".join(p for p in (_p_city_display, _p_state_display) if p)

                # Key the detail URL on person_uid (the true unique PK), NOT
                # master_person_id. The MDM resolved-entity id badly over-merges
                # (one master_person_id can blob together 50+ unrelated people in
                # the same city), so it does not identify the person the user
                # clicked. person_uid is one row per real source occurrence.
                # When person_uid is null there is no key that resolves to this
                # exact person, so emit no url — a name slug would just 404.
                person_uid = row['person_uid']
                person_url = f"/person/{quote(str(person_uid), safe='')}" if person_uid else None

                results.append(SearchResult(
                    result_type='person',
                    title=name,
                    subtitle=f"{title} - {org_display}" if org else title,
                    description=f"Person in {location}" if location else 'Person',
                    url=person_url,
                    score=float(row['sim']) if row['sim'] is not None else 1.0,
                    metadata={
                        'name': name,
                        'master_person_id': row['master_person_id'],
                        'title': row['title'],
                        'organization': org_display,
                        'master_org_id': row['master_org_id'],
                        'state': row['state_code'],
                        'state_code': row['state_code'],
                        'city': row['city_norm'],
                        'compensation': row['reportable_comp_org'],
                        'email': row['email'],
                        'phone': row['phone'],
                        'ein': row['ein'],
                        'cause': row['ntee_description'],
                        'ntee_code': row['ntee_code'],
                        'total_revenue': float(row['gt990_total_revenue']) if row['gt990_total_revenue'] is not None else None,
                        'total_assets': float(row['gt990_total_assets']) if row['gt990_total_assets'] is not None else None,
                        'filing_url': row['gt990_source_url'],
                    }
                ))

            logger.info(f"👤 PostgreSQL person search: {len(results)} results")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL person search error: {e}")
        return []


# NOTE: the former `search_contacts_pg = search_persons_pg` back-compat alias was
# removed — there were no callers, and the "contacts" naming is retired in favor
# of the two distinct categories: "persons" (mdm_person, search_persons_pg) and
# "leaders" (contact_official, search_officials_pg).


# Officials search (contact_official ~34k rows): cap how many ILIKE/trgm
# candidates we rank so a broad title term (e.g. "Council Member" matches
# thousands) can't degrade the typeahead. The pg_trgm GIN indexes on full_name
# and title fill the cap fast; selective queries return far fewer.
OFFICIAL_CANDIDATE_CAP = 2000


async def search_officials_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 10,
) -> List[SearchResult]:
    """
    Search elected/appointed officials, backed by the contact_official mart.

    Replaces the retired gold parquet officials feed
    (data/gold/states/<ST>/contact_official.parquet, consolidated
    data/gold/contact_official.parquet). Reads ONLY the public schema — no parquet,
    no DuckDB.

    Title-aware: the query is matched against BOTH full_name AND title, so "Mayor"
    returns every mayor (optionally narrowed by state) while a name query still
    returns the person. Ranking, highest first:
        1. exact / prefix name match
        2. title match (exact > prefix > substring)
        3. jurisdiction substring match
        4. trigram name similarity (typo tolerance)
    Both ILIKE branches ride the pg_trgm GIN indexes on full_name and title.

    is_current officials sort ahead of historical ones.

    These are government officials — they surface in the unified search under the
    dedicated **"leaders"** category (result_type='leader'), distinct from the
    "persons" category (real people from mdm_person via search_persons_pg).

    Args:
        query: Search text (matched against full_name AND title; jurisdiction too)
        state: Filter by state code ('AL') or full name ('Alabama')
        city: Filter by city name (substring-matched against contact_official.jurisdiction)
        limit: Max results

    Returns:
        List of SearchResult objects (result_type='leader')
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)

    has_query = bool(query and query.strip())
    q = query.strip() if has_query else ""

    # A 1-char query is all noise (matches the whole table); mirror the persons
    # search early-return so the per-keystroke typeahead only fires at >=2 chars.
    # When a state or city is supplied we still allow a bare browse (no query).
    if has_query and len(q) < 2 and not state and not city:
        return []

    try:
        pool = await get_db_pool()

        where_clauses: List[str] = []
        params: List = []
        idx = 1

        if state:
            where_clauses.append(f"state_code = ${idx}")
            params.append(state.upper())
            idx += 1

        # Additive city scope: contact_official.jurisdiction holds the place name
        # (e.g. "Tuscaloosa"); a substring ILIKE keeps officials for that city.
        # Bound as a parameter ($N) like every other predicate here — no string
        # interpolation of user input.
        if city and city.strip():
            # A city filter must not leak COUNTY officials: a bare
            # ILIKE '%Tuscaloosa%' also matches "Tuscaloosa County". Keep the
            # substring match on the city name but exclude county-level
            # jurisdictions so /search?city=Tuscaloosa returns city offices only.
            where_clauses.append(
                f"(jurisdiction ILIKE ${idx} AND jurisdiction NOT ILIKE '%county%')"
            )
            params.append(f"%{city.strip()}%")
            idx += 1

        if has_query:
            # One %q% pattern (drives both full_name and title ILIKE, both
            # trgm-indexed) plus the raw term for similarity()/prefix scoring.
            params.append(f"%{q}%")
            like_idx = idx
            idx += 1
            params.append(q)
            term_idx = idx
            idx += 1
            params.append(f"{q}%")
            prefix_idx = idx
            idx += 1

            # Match if the term hits the name, the title, OR the jurisdiction.
            where_clauses.append(
                f"(full_name ILIKE ${like_idx} "
                f"OR title ILIKE ${like_idx} "
                f"OR jurisdiction ILIKE ${like_idx})"
            )

            # Composite relevance score. Name match dominates, then title, then
            # jurisdiction, with a trigram tail for typo tolerance.
            score_select = f"""(
                CASE
                    WHEN LOWER(full_name) = LOWER(${term_idx}) THEN 5.0
                    WHEN full_name ILIKE ${prefix_idx} THEN 4.0
                    WHEN full_name ILIKE ${like_idx} THEN 3.0
                    ELSE 0.0
                END
                + CASE
                    WHEN LOWER(title) = LOWER(${term_idx}) THEN 2.5
                    WHEN title ILIKE ${prefix_idx} THEN 2.0
                    WHEN title ILIKE ${like_idx} THEN 1.5
                    ELSE 0.0
                END
                + CASE WHEN jurisdiction ILIKE ${like_idx} THEN 1.0 ELSE 0.0 END
                + similarity(full_name, ${term_idx})
            ) AS score"""
            # is_current first, then composite score, then name.
            order_by = (
                "is_current DESC NULLS LAST, score DESC, full_name ASC"
            )
        else:
            # Browse (state-scoped, no query): current officials, mayors first.
            score_select = """(
                CASE
                    WHEN title ILIKE '%mayor%' THEN 2.0
                    WHEN title ILIKE '%council%' THEN 1.8
                    WHEN title ILIKE '%commission%' THEN 1.7
                    ELSE 1.5
                END
            ) AS score"""
            order_by = "is_current DESC NULLS LAST, score DESC, full_name ASC"

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        limit_idx = idx
        params.append(limit)

        cols = """id, full_name, title, jurisdiction, state_code, state,
                  party, district, office, email, phone, photo_url, is_current"""

        # Inner query caps the candidate scan (trgm GIN fills it fast); the outer
        # select ranks + orders only the capped set, then trims to `limit`.
        sql = f"""
            SELECT {cols}, score
            FROM (
                SELECT {cols}, {score_select}
                FROM contact_official
                WHERE {where_sql}
                LIMIT {OFFICIAL_CANDIDATE_CAP}
            ) cand
            ORDER BY {order_by}
            LIMIT ${limit_idx}
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                name = row["full_name"] or "Unknown"
                title = row["title"] or "Official"
                jurisdiction = row["jurisdiction"]
                state_full = row["state"]
                state_code = row["state_code"]

                # Location: prefer the office's jurisdiction, fall back to state.
                location = jurisdiction or state_full or state_code or ""

                contact_info = []
                if row["email"]:
                    contact_info.append(f"📧 {row['email']}")
                if row["phone"]:
                    contact_info.append(f"📞 {row['phone']}")
                # Description carries NEW info (party, district, contact) rather
                # than repeating the subtitle, which already reads "{title} - {location}".
                desc_parts: list[str] = []
                if row["party"]:
                    desc_parts.append(row["party"])
                if row["district"]:
                    desc_parts.append(row["district"])
                desc_parts.extend(contact_info)
                description = " • ".join(desc_parts) if desc_parts else (location or title)

                results.append(SearchResult(
                    result_type="leader",
                    title=name,
                    subtitle=f"{title} - {location}" if location else title,
                    description=description,
                    # Drill into the shared person-detail route. The id is
                    # contact_official.id (an OCD id containing a '/'), so it is
                    # percent-encoded to stay a single URL segment for the
                    # frontend router; /person/{id:path} falls back to
                    # contact_official when no mdm_person row matches.
                    url=f"/person/{quote(row['id'], safe='')}",
                    score=float(row["score"]) if row["score"] is not None else 1.0,
                    metadata={
                        "id": row["id"],
                        "name": name,
                        "title": title,
                        "jurisdiction": jurisdiction,
                        # Naming contract: expose BOTH state_code and full state.
                        "state": state_full,
                        "state_code": state_code,
                        "party": row["party"],
                        "district": row["district"],
                        "office": row["office"],
                        "email": row["email"],
                        "phone": row["phone"],
                        "photo_url": row["photo_url"],
                        "is_current": row["is_current"],
                        "contact_type": "official",
                        "data_source": "contact_official",
                    },
                ))

            logger.info(f"🏛️  PostgreSQL officials search: {len(results)} results")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL officials search error: {e}")
        return []


async def search_organizations_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    ntee_code: Optional[str] = None,
    ein: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    sort: str = 'relevance'
) -> List[SearchResult]:
    """
    Search nonprofit organizations using PostgreSQL

    Location scoping goes through the MDM org<->jurisdiction bridge
    (mdm_bridge_org_jurisdiction), NOT the org's own free-text city. The bridge
    allocates each org to the city/county/state jurisdiction(s) it operates in, so
    "orgs in Tuscaloosa" returns every city-linked org (~4,535) rather than only
    rows whose stored city string happens to equal "Tuscaloosa".

    - jurisdiction_id (exact city/county/state scope) -> EXISTS over the bridge on
      that jurisdiction_id (preferred, most precise).
    - city (+ state) -> resolve to the matching CITY/TOWN jurisdiction(s) and filter
      orgs whose master_org_id is bridged to one of them.
    - state only (no city/jurisdiction_id) -> direct state_code match (no bridge).

    Args:
        query: Search text (organization name)
        state: Filter by state code (e.g., 'MA') or full name (e.g., 'Massachusetts')
        city: Filter by city name (resolved to a city/town jurisdiction via the bridge)
        ntee_code: Filter by NTEE code prefix
        ein: Exact EIN match
        jurisdiction_id: Exact jurisdiction scope (city, county, or state) via the bridge
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

        # Location scope via the MDM org<->jurisdiction bridge.
        # jurisdiction_id (exact) wins; else city+state resolves to a city/town
        # jurisdiction; else a bare state falls back to a direct state_code match.
        if jurisdiction_id:
            # EXISTS over the bridge for this exact jurisdiction (city/county/state).
            # base.master_org_id is exposed by the inner projection below.
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM mdm_bridge_org_jurisdiction b "
                f"WHERE b.master_org_id = base.master_org_id "
                f"AND b.jurisdiction_id = ${param_idx})"
            )
            params.append(jurisdiction_id)
            param_idx += 1
        elif city:
            # Resolve the city/town jurisdiction(s) by name (+ state) and filter
            # orgs bridged to one of them. This is what makes "orgs in Tuscaloosa"
            # return the city-linked set, not just stored-city string matches.
            city_pred = (
                f"base.master_org_id IN ("
                f"SELECT b.master_org_id FROM mdm_bridge_org_jurisdiction b "
                f"JOIN jurisdictions j ON j.jurisdiction_id = b.jurisdiction_id "
                f"WHERE lower(j.name) = lower(${param_idx}) "
                f"AND j.jurisdiction_type IN ('city','town')"
            )
            params.append(city.strip())
            param_idx += 1
            if state:
                city_pred += f" AND j.state_code = ${param_idx}"
                params.append(state.upper())
                param_idx += 1
            city_pred += ")"
            where_clauses.append(city_pred)
        elif state:
            # State-only scope: direct state_code match (no bridge needed).
            where_clauses.append(f"state_code = ${param_idx}")
            params.append(state.upper())
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
        
        has_text_query = bool(query and query.strip() and not ein)

        # Name sorts order by org_name_norm (btree-indexed) rather than org_name so
        # browse is an index scan instead of a 3.6M-row sort. They sort identically
        # to the user (normalized lower-case of the same name).
        if sort == 'name-asc':
            order_by = "org_name_norm ASC"
        elif sort == 'name-desc':
            order_by = "org_name_norm DESC"
        elif sort == 'revenue-asc':
            order_by = "revenue ASC NULLS LAST"
        elif sort == 'revenue-desc':
            order_by = "revenue DESC NULLS LAST"
        elif sort == 'assets-asc':
            order_by = "assets ASC NULLS LAST"
        elif sort == 'assets-desc':
            order_by = "assets DESC NULLS LAST"
        elif has_text_query:
            # Relevance ranking for text search — now applied only to the capped
            # candidate set (see ORG_CANDIDATE_CAP), so recomputing to_tsvector here
            # is bounded instead of running over a 530k-row match set.
            order_by = f"ts_rank(to_tsvector('english', name), plainto_tsquery('english', ${param_idx - 1})) DESC, org_name_norm ASC"
        else:
            order_by = "org_name_norm ASC"

        # Cap the candidate scan for text queries only (browse/exact-filter modes
        # ride the org_name_norm index and need the full ordered scan).
        cap_sql = f"LIMIT {ORG_CANDIDATE_CAP}" if has_text_query else ""

        # Org identity/location now come from the golden master (mdm_organization);
        # nonprofit financial/NTEE/990 detail from the mdm_organization_nonprofit
        # satellite. The CTE re-exposes the same column names the WHERE/ORDER BY
        # builders above reference (name, city, state_code, ntee_code, revenue, ...).
        # county lives in the address layer (not the org master) -> NULL here.
        # Inner `cand` does the join + filters + (text-query) candidate cap with a
        # CHEAP column projection only. The expensive display derivations — INITCAP
        # on city and the 50-branch state-name CASE — run in the OUTER select, over
        # at most a page (browse) or the capped candidate set, never over the full
        # 3.6M-row join. (Computing them below the cap was what made a named-CTE
        # version 15s+ for a common word.) `cand` re-exposes the alias names the
        # WHERE/ORDER BY builders reference (name, city, state_code, ntee_code, ...).
        sql = f"""
            SELECT
                master_org_id,
                ein,
                name,
                INITCAP(city) AS city,
                state_code,
                {_STATE_NAME_CASE} AS state,
                NULL::text AS county,
                ntee_code, ntee_description, revenue, assets, income, tax_period,
                gt990_tax_year, gt990_total_revenue, gt990_total_expenses,
                gt990_total_assets, gt990_mission, has_gt990_data
            FROM (
                -- `base` does cheap column renames so the WHERE/cap can reference
                -- the builder alias names (name, city, ...); it has no LIMIT so
                -- Postgres flattens it into the filter+cap, letting the FTS GIN
                -- index drive and the cap stop the scan early.
                SELECT * FROM (
                    SELECT
                        m.master_org_id,
                        s.ein,
                        m.org_name AS name,
                        m.org_name_norm,
                        m.city_norm AS city,
                        m.state_code,
                        s.ntee_code,
                        s.ntee_description,
                        s.revenue,
                        s.assets,
                        s.income,
                        s.tax_period,
                        s.gt990_tax_year,
                        s.gt990_total_revenue,
                        s.gt990_total_expenses,
                        s.gt990_total_assets,
                        s.gt990_mission,
                        s.has_gt990_data
                    FROM mdm_organization m
                    JOIN mdm_organization_nonprofit s USING (master_org_id)
                ) base
                WHERE {where_sql}
                {cap_sql}
            ) cand
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
                        'master_org_id': row['master_org_id'],
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


async def get_nonprofit_compensation_pg(
    ein: Optional[str] = None,
    state: Optional[str] = None,
    person: Optional[str] = None,
    min_comp: Optional[int] = None,
    limit: int = 25,
    offset: int = 0,
    sort: str = 'comp-desc',
) -> List[dict]:
    """
    Person-level executive/board compensation from the GivingTuesday 990 datamarts.

    Reads organization_nonprofit_compensation (Form 990 Part VII-A enriched
    with Schedule J detail + org context). Returns one record per person-filing.

    Args:
        ein: Exact EIN match (a single organization's people).
        state: Filter by state code or full name.
        person: Case-insensitive substring match on person name.
        min_comp: Minimum reportable compensation from the organization.
        limit/offset: Pagination.
        sort: 'comp-desc' (default), 'comp-asc', or 'name-asc'.
    """
    state = normalize_state_input(state)

    try:
        pool = await get_db_pool()

        where_clauses: List[str] = []
        params: List = []
        idx = 1
        if ein:
            where_clauses.append(f"ein = ${idx}"); params.append(ein); idx += 1
        if state:
            where_clauses.append(f"state_code = ${idx}"); params.append(state); idx += 1
        if person:
            where_clauses.append(f"person_name ILIKE ${idx}"); params.append(f"%{person}%"); idx += 1
        if min_comp is not None:
            where_clauses.append(f"reportable_comp_org >= ${idx}"); params.append(min_comp); idx += 1
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        order_by = {
            'comp-asc': "reportable_comp_org ASC NULLS LAST",
            'name-asc': "person_name ASC",
        }.get(sort, "reportable_comp_org DESC NULLS LAST")

        sql = f"""
            SELECT
                ein, tax_year, person_name, title,
                org_name, city, state_code, ntee_code,
                is_officer, is_director_trustee, is_key_employee,
                is_highest_comp, is_former, avg_hours_org,
                reportable_comp_org, reportable_comp_related, other_comp, total_comp,
                has_schedule_j, base_comp_org, bonus_org, deferred_comp_org,
                nontaxable_benefits_org, sch_j_total_comp_org, source_url
            FROM organization_nonprofit_compensation
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.append(limit); params.append(offset)

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            results = [dict(row) for row in rows]
            logger.info(f"💰 PostgreSQL compensation: {len(results)} records (ein={ein}, state={state})")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL compensation query error: {e}")
        return []


async def search_events_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    topic_tsquery: Optional[str] = None,
) -> List[SearchResult]:
    """
    Search meetings using PostgreSQL.

    Returns a merged, deduped feed of TWO legs, both surfaced under the
    `meeting` result type:

    1. ANALYZED meetings — `public.event_meeting`, the AI-analyzed meeting mart
       (~6k rows: body name + jurisdiction + summary + video). These have a real
       drilldown page (`/meetings/{event_meeting_id}` -> GET /api/meetings/{id},
       decisions + financial items), so every analyzed result is clickable.
    2. UNANALYZED meetings — orphan transcripts in `public.event_documents`
       (`event_id IS NULL`), i.e. raw transcripts that exist but have not been
       through Gemini analysis yet. Cities like Atlanta have 100s of transcripts
       and 0 analyzed meetings; without this leg their Meetings tab reads empty.
       Zero new Gemini cost — the transcripts already exist on disk/in the mart.

    Dedup: the unanalyzed leg excludes any `video_id` already represented in
    `event_meeting` (NOT EXISTS on video_id), so an analyzed meeting never shows
    twice. Ranking is `is_analyzed DESC` first (analyzed before pending), then
    ISO meeting date DESC, then a stable id tiebreaker. LIMIT/OFFSET are applied
    in SQL across the MERGED set via a UNION ALL + outer wrapper, so single-type
    browse pagination stays correct.

    We intentionally do NOT search the raw `public.event` table (~153k scraped
    rows): those have no transcript, no summary, and no detail page.

    Args:
        query: Search text (meeting body / jurisdiction / summary, and — for the
            unanalyzed leg — the transcript body via content_tsv).
        state: Filter by state code ('MA') or full name ('Massachusetts').
        city: Filter by city name (matched against jurisdiction_name / city).
        limit: Max results.
        offset: Rows to skip, for single-type browse pagination.

    Returns:
        List of SearchResult objects (result_type='meeting').
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)

    try:
        pool = await get_db_pool()

        has_query = bool(query and query.strip())
        q = query.strip() if has_query else ""

        # --- Shared parameter bag for the UNION ALL. asyncpg uses positional $n,
        # so we register each value once and reuse its index across both legs.
        params: List[Any] = []

        q_like_idx = q_fts_idx = None
        if has_query:
            params.append(f"%{q}%")
            q_like_idx = len(params)   # %q% for ILIKE (both legs)
            params.append(q)
            q_fts_idx = len(params)    # raw q for plainto_tsquery (both legs)

        state_idx = None
        if state:
            params.append(state.upper())
            state_idx = len(params)

        city_idx = None
        if city and city.strip():
            params.append(city.strip())
            city_idx = len(params)

        # Civic-topic filter (Advanced): the named topic's OR-tsquery, applied to
        # both legs (meeting text / its decisions, and the transcript body).
        topic_idx = None
        if topic_tsquery:
            params.append(topic_tsquery)
            topic_idx = len(params)

        # ---- Analyzed leg (event_meeting) -------------------------------------
        em_where: List[str] = []
        if has_query:
            # Meetings inherit matches from their child decisions: a meeting's own
            # body/jurisdiction/summary may never mention the term (e.g. "Fluoride"),
            # but a decision taken at that meeting does. OR in an EXISTS over
            # event_decision linked by c1_event_id, using the SAME English-FTS
            # predicate as search_decisions_pg / count_decisions.
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
            # Meeting matches the topic if its own body/summary/jurisdiction text
            # does, OR a decision taken at it does (same c1_event_id inheritance as
            # the query leg above).
            em_where.append(
                f"(to_tsvector('english', COALESCE(em.body_name, '') || ' ' "
                f"|| COALESCE(em.meeting_summary, '') || ' ' || COALESCE(em.jurisdiction_name, '')) "
                f"@@ to_tsquery('english', ${topic_idx}) "
                f"OR EXISTS (SELECT 1 FROM event_decision d "
                f"WHERE d.c1_event_id = em.c1_event_id "
                f"AND d.search_tsv @@ to_tsquery('english', ${topic_idx})))"
            )
        em_where_sql = " AND ".join(em_where) if em_where else "TRUE"

        # ---- Unanalyzed leg (event_documents WHERE event_id IS NULL) ----------
        # Scope by state_code + exact city name (the view has NO jurisdiction_id),
        # exactly like search_documents_pg. Dedup against analyzed meetings on
        # video_id. NOTE: event_documents may carry multiple rows per video_id
        # (different document_type/source), so DISTINCT ON (video_id) collapses
        # each video to a single representative transcript row.
        ed_where: List[str] = ["ed.event_id IS NULL"]
        if has_query:
            # Body match is the whole point: surface transcript-BODY hits, not
            # just title hits. content_tsv is the precomputed, GIN-indexable
            # vector (ranking/matching never re-tokenizes the 43KB-avg content).
            ed_where.append(
                f"(ed.event_title ILIKE ${q_like_idx} "
                f"OR ed.content_tsv @@ plainto_tsquery('english', ${q_fts_idx}))"
            )
        if state_idx:
            ed_where.append(f"ed.state_code = ${state_idx}")
        if city_idx:
            ed_where.append(
                f"(lower(ed.jurisdiction_name) = lower(${city_idx}) "
                f"OR lower(ed.city) = lower(${city_idx}))"
            )
        if topic_idx:
            ed_where.append(f"ed.content_tsv @@ to_tsquery('english', ${topic_idx})")
        # Dedup: never show a transcript whose video is already an analyzed meeting.
        ed_where.append(
            "NOT EXISTS (SELECT 1 FROM event_meeting em2 WHERE em2.video_id = ed.video_id)"
        )
        ed_where_sql = " AND ".join(ed_where)

        # meeting_date is mostly ISO 'YYYY-MM-DD' text, but ~180 rows carry the
        # literal 'unknown' (and a few are NULL). A bare lexical DESC would float
        # 'unknown' above every real date, so null out anything that isn't an ISO
        # date in the sort key. event_documents.event_date is a real DATE, so just
        # cast to text — no regex guard needed. The id tiebreaker keeps OFFSET
        # paging stable when rows share a date (or are undated).
        em_iso = "(CASE WHEN em.meeting_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' THEN em.meeting_date END)"

        # LIMIT/OFFSET apply to the MERGED set so single-type browse paging is
        # correct. Registered AFTER all WHERE params so the $n indices above hold.
        params.append(limit)
        limit_idx = len(params)
        params.append(max(offset, 0))
        offset_idx = len(params)

        # Aligned projection across both legs. `is_analyzed` drives the primary
        # sort; `row_id` is the per-leg stable tiebreaker. Snippet/detoast is
        # deferred to the OUTER select so only the LIMIT/OFFSET window is
        # headlined — never the full 119k-row transcript corpus.
        if has_query:
            ed_snippet = (
                f"ts_headline('english', ed.content, plainto_tsquery('english', ${q_fts_idx}), "
                f"'MaxFragments=2, MinWords=5, MaxWords=18, StartSel=<mark>, StopSel=</mark>')"
            )
        else:
            ed_snippet = "LEFT(ed.content, 200)"

        sql = f"""
            WITH merged AS (
                SELECT
                    TRUE  AS is_analyzed,
                    em.event_meeting_id           AS row_id,
                    em.event_meeting_id,
                    NULL::bigint                  AS event_document_id,
                    em.body_name,
                    em.jurisdiction_name,
                    em.jurisdiction_type,
                    em.state_code,
                    em.state,
                    em.city,
                    {em_iso}                      AS iso_date,
                    em.meeting_summary,
                    em.agenda_summary,
                    NULL::text                    AS content,
                    em.video_id,
                    NULL::text                    AS video_url
                FROM event_meeting em
                WHERE {em_where_sql}

                UNION ALL

                SELECT * FROM (
                    SELECT DISTINCT ON (ed.video_id)
                        FALSE AS is_analyzed,
                        ed.event_document_id          AS row_id,
                        NULL::bigint                  AS event_meeting_id,
                        ed.event_document_id,
                        ed.event_title                AS body_name,
                        ed.jurisdiction_name,
                        ed.jurisdiction_type,
                        ed.state_code,
                        ed.state,
                        ed.city,
                        ed.event_date::text           AS iso_date,
                        NULL::text                    AS meeting_summary,
                        NULL::text                    AS agenda_summary,
                        ed.content,
                        ed.video_id,
                        ed.video_url
                    FROM event_documents ed
                    WHERE {ed_where_sql}
                    ORDER BY ed.video_id, ed.event_date DESC NULLS LAST, ed.event_document_id DESC
                ) ed_distinct
            )
            SELECT
                is_analyzed, event_meeting_id, event_document_id,
                body_name, jurisdiction_name, jurisdiction_type,
                state_code, state, city, iso_date,
                video_id, video_url,
                CASE
                    WHEN is_analyzed THEN LEFT(COALESCE(meeting_summary, agenda_summary, ''), 200)
                    ELSE {ed_snippet.replace('ed.content', 'content')}
                END AS snippet
            FROM merged
            ORDER BY is_analyzed DESC, iso_date DESC NULLS LAST, row_id DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                location = (
                    f"{row['jurisdiction_name']}, {row['state']}"
                    if row['jurisdiction_name'] and row['state']
                    else (row['jurisdiction_name'] or '')
                )
                # iso_date is already null-guarded in SQL (real ISO date or NULL).
                date_str = row['iso_date'] or ''
                # body_name is the meeting's display name (analyzed: "City Council";
                # unanalyzed: the transcript's event_title). Fall back to the
                # jurisdiction when both are empty.
                title = row['body_name'] or row['jurisdiction_name'] or 'Meeting'

                subtitle = location
                if date_str:
                    subtitle = f"{location} - {date_str}" if location else date_str

                description = row['snippet'] or ''
                # Match the legacy "..." affordance for the truncated-summary case.
                if row['is_analyzed'] and len(description) == 200:
                    description += "..."

                if row['is_analyzed']:
                    results.append(SearchResult(
                        result_type='meeting',
                        title=title,
                        subtitle=subtitle,
                        description=description,
                        url=f"/meetings/{row['event_meeting_id']}",
                        score=1.0,
                        metadata={
                            'jurisdiction': row['jurisdiction_name'],
                            'jurisdiction_type': row['jurisdiction_type'],
                            'state': row['state'],
                            'state_code': row['state_code'],
                            'city': row['city'],
                            'date': date_str,
                            'event_meeting_id': row['event_meeting_id'],
                            'meeting_id': row['event_meeting_id'],
                            'video_id': row['video_id'],
                            'analysis_pending': False,
                        }
                    ))
                else:
                    # Unanalyzed transcript: no /meetings/{id} drilldown exists, so
                    # link to the source video. Most orphan transcripts carry only
                    # a YouTube video_id (video_url null), so synthesize the watch
                    # URL from it. analysis_pending=True is the frontend contract
                    # for the "Analysis pending" badge.
                    if row['video_url']:
                        url = row['video_url']
                    elif row['video_id']:
                        url = f"https://www.youtube.com/watch?v={row['video_id']}"
                    else:
                        url = ''
                    results.append(SearchResult(
                        result_type='meeting',
                        title=title,
                        subtitle=subtitle,
                        description=description,
                        url=url,
                        score=0.5,
                        metadata={
                            'jurisdiction': row['jurisdiction_name'],
                            'jurisdiction_type': row['jurisdiction_type'],
                            'state': row['state'],
                            'state_code': row['state_code'],
                            'city': row['city'],
                            'date': date_str,
                            'video_id': row['video_id'],
                            'document_id': row['event_document_id'],
                            'analysis_pending': True,
                        }
                    ))

            logger.info(f"📅 PostgreSQL events search: {len(results)} results")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL events search error: {e}")
        return []


async def _suggest_corrected_query(conn, raw: str) -> Optional[str]:
    """Map a misspelled document query to its nearest real corpus spelling.

    Splits the raw query into alphabetic terms and, for each term that is NOT
    already a known corpus lexeme, finds the closest lexeme in
    public.event_document_lexicon by trigram similarity (pg_trgm `%` operator +
    its GIN index, so this is an indexed lookup, not a scan). Returns the
    rebuilt query string only if at least one term was actually corrected,
    otherwise None — so the caller knows whether a fuzzy retry is worthwhile.

    Guards: requires the candidate to share the term's first character (kills
    wild substitutions while still allowing the common transposition/omission
    typos that keep the leading letter, e.g. "flouride" -> "fluoride"). Any
    error (e.g. the lexicon table not yet built) yields None — fuzzy fallback
    is best-effort and never breaks the primary search.
    """
    terms = re.findall(r"[a-zA-Z]{3,}", raw or "")
    if not terms:
        return None

    corrected: List[str] = []
    changed = False
    try:
        for term in terms:
            term_l = term.lower()
            row = await conn.fetchrow(
                """
                SELECT word, (word = $1) AS exact
                FROM event_document_lexicon
                WHERE word % $1
                  AND left(word, 1) = left($1, 1)
                ORDER BY (word = $1) DESC, similarity(word, $1) DESC, document_count DESC
                LIMIT 1
                """,
                term_l,
            )
            if row is None or row["exact"]:
                # Unknown term with no candidate, or already a real word: keep it.
                corrected.append(term)
            else:
                corrected.append(row["word"])
                changed = True
    except Exception as e:  # lexicon missing / pg_trgm absent — skip correction
        logger.debug(f"document query correction skipped: {e}")
        return None

    return " ".join(corrected) if changed else None


async def search_documents_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 10,
    offset: int = 0
) -> List[SearchResult]:
    """
    Full-text search over event documents (meeting transcripts) using PostgreSQL.

    Searches the body text of public.event_documents (transcripts today) and
    returns a highlighted snippet of the matching passage so results show *why*
    they matched, plus the linkable meeting it belongs to.

    Args:
        query: Search text (matched against the document body)
        state: Filter by state code ('MA') or full name ('Massachusetts')
        city: Filter by city name (matched against jurisdiction_name / city)
        limit: Max results

    Returns:
        List of SearchResult objects
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)

    try:
        pool = await get_db_pool()

        where_clauses = []
        params = []
        param_idx = 1

        if state:
            where_clauses.append(f"state_code = ${param_idx}")
            params.append(state.upper())
            param_idx += 1

        # City scope — exact, case-insensitive match on jurisdiction_name OR city
        # (mirrors search_events_pg / search_bills_pg), so a city browse doesn't
        # leak the rest of the state's transcripts. jurisdiction_name is the
        # reliably-populated column; city is the OR fallback.
        if city and city.strip():
            where_clauses.append(
                f"(lower(jurisdiction_name) = lower(${param_idx}) OR lower(city) = lower(${param_idx}))"
            )
            params.append(city.strip())
            param_idx += 1

        # Full-text body search against the STORED content_tsv vector (GIN-indexed
        # by event_documents_content_tsv_idx). Match AND rank both read the
        # precomputed lexemes — ranking off to_tsvector(content) instead would
        # re-tokenize every 43KB-avg transcript per match (a common word matches
        # thousands of rows -> 25s+ stall). ts_headline below still reads the raw
        # `content` text, but only for the handful of rows we actually return.
        if query and query.strip():
            where_clauses.append(
                f"content_tsv @@ plainto_tsquery('english', ${param_idx})"
            )
            params.append(query)
            q_idx = param_idx
            param_idx += 1

            order_by = (
                f"ts_rank(content_tsv, "
                f"plainto_tsquery('english', ${q_idx})) DESC, event_date DESC NULLS LAST"
            )
            # Highlighted snippet around the matching passage
            snippet_sql = (
                f"ts_headline('english', content, plainto_tsquery('english', ${q_idx}), "
                f"'MaxFragments=2, MinWords=5, MaxWords=18, StartSel=<mark>, StopSel=</mark>')"
            )
        else:
            order_by = "event_date DESC NULLS LAST"
            snippet_sql = "LEFT(content, 200)"

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        capped_limit = min(limit, DOCUMENT_RESULT_CAP)
        safe_offset = max(offset, 0)

        # Columns every result row needs, shared by both query shapes below.
        select_cols = (
            "event_document_id, event_id, document_type, document_source, "
            "video_id, event_title, event_date, jurisdiction_name, "
            "jurisdiction_type, state_code, state, city, video_url, word_count"
        )

        if query and query.strip():
            # Two-phase: a GIN-indexed pool of the most RECENT matches (cheap —
            # the index alone, no per-row detoast), then ts_rank + ts_headline
            # only that bounded pool. Avoids ranking/detoasting ~64k rows for a
            # common term. Pool covers the requested page.
            pool_size = max(DOCUMENT_CANDIDATE_POOL, safe_offset + capped_limit)
            sql = f"""
                WITH candidates AS (
                    SELECT {select_cols}, content, content_tsv
                    FROM event_documents
                    WHERE {where_sql}
                    ORDER BY event_date DESC NULLS LAST, event_document_id DESC
                    LIMIT {pool_size}
                )
                SELECT {select_cols}, {snippet_sql} AS snippet
                FROM candidates
                ORDER BY {order_by}, event_document_id DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
        else:
            # No text query → just the most recent transcripts (optionally scoped
            # to a place). event_date is btree-indexed, so this is already cheap.
            sql = f"""
                SELECT {select_cols}, {snippet_sql} AS snippet
                FROM event_documents
                WHERE {where_sql}
                ORDER BY {order_by}, event_document_id DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
        # Bound the snippet/detoast work regardless of the caller's over-fetch.
        params.append(capped_limit)
        params.append(safe_offset)

        async with pool.acquire() as conn:
            # The planner under-costs the content_tsv detoast and prefers a seq
            # scan over the GIN index; for the bounded candidate pool the index
            # is ~60x faster, so force it for this single-table query only
            # (transaction-scoped via SET LOCAL — never leaks to the pooled
            # connection). Both the initial fetch AND the fuzzy retry run inside,
            # so the corrected-spelling pass stays fast too.
            async with conn.transaction():
                if query and query.strip():
                    await conn.execute("SET LOCAL enable_seqscan = off")
                rows = await conn.fetch(sql, *params)

                # Fuzzy fallback: a correctly-formed full-text query that matches
                # nothing is almost always a misspelling ("flouride"). Map each
                # term to its nearest real corpus spelling and retry once so the
                # user gets the meetings they meant instead of an empty page.
                # First page only, and only when there is a text query (q_idx set).
                corrected_query: Optional[str] = None
                if query and query.strip() and not rows and offset == 0:
                    suggestion = await _suggest_corrected_query(conn, query)
                    if suggestion and suggestion.lower() != query.strip().lower():
                        params[q_idx - 1] = suggestion
                        rows = await conn.fetch(sql, *params)
                        if rows:
                            corrected_query = suggestion
                        logger.info(
                            f"📄 documents fuzzy fallback: {query!r} -> "
                            f"{suggestion!r} ({len(rows)} rows)"
                        )

            results = []
            for row in rows:
                location = f"{row['jurisdiction_name']}, {row['state']}" if row['jurisdiction_name'] and row['state'] else ''
                date_str = row['event_date'].strftime('%Y-%m-%d') if row['event_date'] else ''
                title = row['event_title'] or 'Meeting transcript'
                subtitle = f"{location} - {date_str}".strip(' -')

                # event_id is nullable (orphan transcripts have no golden event);
                # deep-link to the meeting when one exists, else fall back to the
                # source video. Most orphan transcripts carry only a YouTube
                # video_id (video_url is null), so synthesize the watch URL from
                # it — otherwise the card has nothing to link to.
                if row['event_id'] is not None:
                    url = f"/documents?meeting_id={row['event_id']}"
                elif row['video_url']:
                    url = row['video_url']
                elif row['video_id']:
                    url = f"https://www.youtube.com/watch?v={row['video_id']}"
                else:
                    url = ''

                results.append(SearchResult(
                    result_type='document',
                    title=title,
                    subtitle=subtitle,
                    description=row['snippet'] or '',
                    url=url,
                    score=1.0,
                    metadata={
                        'document_id': row['event_document_id'],
                        'document_type': row['document_type'],
                        'document_source': row['document_source'],
                        'meeting_id': row['event_id'],
                        'video_id': row['video_id'],
                        'jurisdiction': row['jurisdiction_name'],
                        'jurisdiction_type': row['jurisdiction_type'],
                        'state': row['state'],
                        'state_code': row['state_code'],
                        'city': row['city'],
                        'date': date_str,
                        'video_url': row['video_url'],
                        'word_count': row['word_count'],
                        # Present only when the original query matched nothing and
                        # we transparently searched a corrected spelling instead.
                        # Lets the UI show a "showing results for X" affordance.
                        'corrected_from': query if corrected_query else None,
                        'corrected_query': corrected_query,
                    }
                ))

            logger.info(f"📄 PostgreSQL documents search: {len(results)} results")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL documents search error: {e}")
        return []


async def search_bills_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    session: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 10,
    offset: int = 0
) -> List[SearchResult]:
    """
    Search legislation referenced in meetings, backed by the public.event_bill mart
    (AI-extracted bill / ordinance references from meeting analysis).

    Replaces the retired `bills_search` table. event_bill is a thinner,
    meeting-derived feed: it carries no abstract / legislative session / action
    history, so the `session` filter is accepted for back-compat but NOT applied
    (there is no session column to filter on).

    Args:
        query: Search text (matched against bill title + official number)
        state: Filter by state code (e.g., 'MA') or full name (e.g., 'Massachusetts')
        session: Accepted for back-compat; event_bill has no session column (ignored)
        limit: Max results

    Returns:
        List of SearchResult objects (result_type='bill')
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

        # Location scope. event_bill is local legislation (ordinances/resolutions);
        # jurisdiction_name is always populated, city only sometimes. A city browse
        # (e.g. "Tuscaloosa") must not leak the rest of the state's bills, so match
        # the requested city against either column.
        if city and city.strip():
            where_clauses.append(
                f"(lower(jurisdiction_name) = lower(${param_idx}) OR lower(city) = lower(${param_idx}))"
            )
            params.append(city.strip())
            param_idx += 1

        # Text search across title + official number (the only text event_bill carries)
        if query and query.strip():
            where_clauses.append(f"""(
                to_tsvector('english', COALESCE(title, '')) @@ plainto_tsquery('english', ${param_idx})
                OR LOWER(official_number) LIKE LOWER(${param_idx + 1})
            )""")
            params.append(query)
            params.append(f"%{query}%")
            param_idx += 2

            order_by = (
                f"ts_rank(to_tsvector('english', COALESCE(title, '')), "
                f"plainto_tsquery('english', ${param_idx - 2})) DESC, extracted_at DESC"
            )
        else:
            order_by = "extracted_at DESC"

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        sql = f"""
            SELECT
                event_bill_id,
                official_number,
                title,
                leg_type,
                status,
                relevance,
                jurisdiction_name,
                jurisdiction_type,
                state_code,
                state,
                city,
                c1_event_id,
                analysis_id,
                extracted_at
            FROM event_bill
            WHERE {where_sql}
            ORDER BY {order_by}, event_bill_id DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.append(limit)
        params.append(max(offset, 0))

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                # Format title
                bill_title = row['title'] or 'Untitled legislation'
                number = row['official_number']
                title = f"{number}: {bill_title}" if number else bill_title
                if len(title) > 120:
                    title = title[:117] + "..."

                # Subtitle: location + status
                location = (
                    f"{row['jurisdiction_name']}, {row['state']}"
                    if row['jurisdiction_name'] and row['state']
                    else (row['state'] or '')
                )
                subtitle = " • ".join(p for p in (location, row['status']) if p)

                # Description: the AI relevance note, else the title itself
                description = row['relevance'] or bill_title
                if description and len(description) > 200:
                    description = description[:200] + "..."

                results.append(SearchResult(
                    result_type='bill',
                    title=title,
                    subtitle=subtitle,
                    description=description,
                    url=f"/bills/{row['event_bill_id']}",
                    score=1.0,
                    metadata={
                        'event_bill_id': row['event_bill_id'],
                        'official_number': row['official_number'],
                        'leg_type': row['leg_type'],
                        'status': row['status'],
                        'relevance': row['relevance'],
                        'jurisdiction': row['jurisdiction_name'],
                        'jurisdiction_type': row['jurisdiction_type'],
                        'state': row['state'],
                        'state_code': row['state_code'],
                        'city': row['city'],
                        'meeting_id': row['analysis_id'],
                        'c1_event_id': row['c1_event_id'],
                        'extracted_at': row['extracted_at'].isoformat() if row['extracted_at'] else None,
                    }
                ))

            # Also surface REAL legislation from the OpenStates bills serving
            # relation (`bills`; title GIN-indexed by bills_title_fts_idx).
            # event_bill above is only the meeting-derived ordinance feed, so a
            # policy term ("fluoride") never reached actual statehouse bills.
            # Unqualified `bills` resolves via the connection search_path to the
            # serving layer published by publish_public_serving: a full view over
            # gold.bills in dev (search_path=public; or gold.bills directly on the
            # private gold instance), and a Neon-scoped TABLE (recent sessions,
            # lean columns + its own FTS index) on the Neon-served prod. Wrapped in
            # try/except so it degrades to nothing where `bills` isn't published.
            # Only runs on a text query: a no-query browse of 1.55M bills belongs
            # on the dedicated /bills page, not the unified search.
            if query and query.strip():
                try:
                    q = query.strip()
                    # Title FTS ONLY — served by the bills_title_fts_idx GIN index
                    # (sub-ms over 1.55M rows). Do NOT OR-in an `identifier ILIKE
                    # '%q%'`: a leading-wildcard ILIKE is un-indexable, and OR-ing it
                    # with the GIN match forces a full 1.55M-row seq scan (~11s ->
                    # trips SUBSEARCH_TIMEOUT_S and degrades bills to empty). Bill
                    # numbers don't contain policy words, so there's nothing to lose.
                    leg_params = [q]
                    leg_state = ""
                    if state:
                        leg_params.append(state.upper())
                        leg_state = " AND state_code = $2"
                    leg_params.append(limit)
                    leg_sql = f"""
                        SELECT identifier, title, session_name, state_code, year
                        FROM bills
                        WHERE to_tsvector('english', coalesce(title, '')) @@ plainto_tsquery('english', $1){leg_state}
                        ORDER BY ts_rank(to_tsvector('english', coalesce(title, '')),
                                         plainto_tsquery('english', $1)) DESC,
                                 year DESC NULLS LAST
                        LIMIT ${len(leg_params)}
                    """
                    for lr in await conn.fetch(leg_sql, *leg_params):
                        ident = lr['identifier'] or ''
                        ltitle = lr['title'] or 'Untitled bill'
                        disp = f"{ident}: {ltitle}" if ident else ltitle
                        if len(disp) > 120:
                            disp = disp[:117] + "..."
                        sc = lr['state_code']
                        # Detail route /bill/{state}-{identifier} (BillDetail page ->
                        # /api/bills/{state}-{number}); only linkable with both parts.
                        url = f"/bill/{sc.lower()}-{ident}" if (sc and ident) else ""
                        # year -> string at the JSON/wire boundary (never a number).
                        year_str = str(lr['year']) if lr['year'] is not None else None
                        subtitle = " • ".join(
                            b for b in (sc, lr['session_name'], year_str) if b
                        )
                        results.append(SearchResult(
                            result_type='bill',
                            title=disp,
                            subtitle=subtitle,
                            description=ltitle,
                            url=url,
                            # Just below the meeting-derived event_bill (1.0) so the
                            # locally-relevant ordinance references lead the tab.
                            score=0.95,
                            metadata={
                                'identifier': ident,
                                'state_code': sc,
                                'session_name': lr['session_name'],
                                'year': year_str,
                                'source': 'legislation',
                            }
                        ))
                except Exception as leg_err:
                    # `bills` serving relation not yet published, or any error:
                    # degrade to just the event_bill results.
                    logger.debug(f"Legislative bills search skipped: {leg_err}")

            logger.info(f"📜 PostgreSQL bills search: {len(results)} results")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL bills search error: {e}")
        return []


async def search_topics_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    ntee_code: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    topic_tsquery: Optional[str] = None,
) -> List[SearchResult]:
    """
    Search meeting topics, backed by the public.event_topic mart (AI-extracted
    discussion themes from meeting analysis).

    Replaces the retired `bronze.bronze_topics` table. event_topic is thinner: it
    carries a primary_theme + headline but no NTEE classification, so the
    `ntee_code` filter is accepted for back-compat but NOT applied. Unlike the old
    bronze feed it DOES carry state, so the `state` filter now works.

    Args:
        query: Search query (matched against headline + primary_theme)
        state: Filter by state code (e.g., 'MA') or full name (e.g., 'Massachusetts')
        ntee_code: Accepted for back-compat; event_topic has no NTEE column (ignored)
        limit: Max results to return

    Returns:
        List of SearchResult objects (result_type='topic')
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)

    try:
        pool = await get_db_pool()

        where_conditions = []
        params = []
        param_idx = 1

        if state:
            where_conditions.append(f"state_code = ${param_idx}")
            params.append(state.upper())
            param_idx += 1

        # Location scope. event_topic carries jurisdiction_name (always set) and a
        # sparser city column; a city browse must not leak the rest of the state's
        # topics, so match the city against either (mirrors bills/decisions).
        if city and city.strip():
            where_conditions.append(
                f"(lower(jurisdiction_name) = lower(${param_idx}) OR lower(city) = lower(${param_idx}))"
            )
            params.append(city.strip())
            param_idx += 1

        if query and query.strip():
            where_conditions.append(f"""(
                to_tsvector('english', COALESCE(headline, '') || ' ' || COALESCE(primary_theme, ''))
                @@ plainto_tsquery('english', ${param_idx})
                OR primary_theme ILIKE ${param_idx + 1}
            )""")
            params.append(query)
            params.append(f"%{query}%")
            param_idx += 2

            order_by = (
                f"ts_rank(to_tsvector('english', COALESCE(headline, '') || ' ' || COALESCE(primary_theme, '')), "
                f"plainto_tsquery('english', ${param_idx - 2})) DESC, extracted_at DESC"
            )
        else:
            order_by = "extracted_at DESC"

        if topic_tsquery:
            # Civic-topic filter (Advanced): narrow extracted themes to those whose
            # headline/theme text matches the chosen named topic's keyword set
            # (OR-tsquery built by the caller from public.civicsearch_topic).
            where_conditions.append(
                f"to_tsvector('english', COALESCE(headline, '') || ' ' || COALESCE(primary_theme, '')) "
                f"@@ to_tsquery('english', ${param_idx})"
            )
            params.append(topic_tsquery)
            param_idx += 1

        where_sql = " AND ".join(where_conditions) if where_conditions else "TRUE"

        sql = f"""
            SELECT
                event_topic_id,
                analysis_id,
                decision_id,
                primary_theme,
                headline,
                jurisdiction_name,
                jurisdiction_type,
                state_code,
                state,
                city,
                c1_event_id,
                extracted_at
            FROM event_topic
            WHERE {where_sql}
            ORDER BY {order_by}, event_topic_id DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.append(limit)
        params.append(max(offset, 0))

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                # event_topic has no standalone topic field; the theme names it
                title = row['primary_theme'] or 'Untitled Topic'
                if len(title) > 100:
                    title = title[:100] + "..."

                # Subtitle: location
                location = (
                    f"{row['jurisdiction_name']}, {row['state']}"
                    if row['jurisdiction_name'] and row['state']
                    else (row['state'] or '')
                )
                subtitle = location

                # Description is the headline
                description = row['headline'] or ''
                if description and len(description) > 200:
                    description = description[:200] + "..."

                results.append(SearchResult(
                    result_type='topic',
                    title=title,
                    subtitle=subtitle,
                    description=description,
                    url=f"/topics/{row['event_topic_id']}",
                    score=1.0,
                    metadata={
                        'id': row['event_topic_id'],
                        'decision_id': row['decision_id'],
                        'meeting_id': row['analysis_id'],
                        'primary_theme': row['primary_theme'],
                        'jurisdiction': row['jurisdiction_name'],
                        'jurisdiction_type': row['jurisdiction_type'],
                        'state': row['state'],
                        'state_code': row['state_code'],
                        'city': row['city'],
                        'c1_event_id': row['c1_event_id'],
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
    city: Optional[str] = None,
    sort: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    question_id: Optional[str] = None,
    topic_tsquery: Optional[str] = None,
) -> List[SearchResult]:
    """
    Search governance decisions, backed by the public.event_decision mart
    (AI-extracted policy decisions from meeting analysis).

    Replaces the retired `bronze.bronze_decisions` table. event_decision has no
    standalone `topic` / `decision_method` / `decision_date` columns (those lived
    in the old bronze feed); it does carry state, so the `state` filter now works.

    Args:
        query: Search query (matched against headline, decision_statement, primary_theme)
        state: Filter by state code (e.g., 'MA') or full name (e.g., 'Massachusetts')
        outcome: Filter by outcome (APPROVED, DENIED, DEFERRED, etc.)
        limit: Max results to return

    Returns:
        List of SearchResult objects (result_type='decision')
    """
    # Normalize state input to 2-letter code
    state = normalize_state_input(state)

    try:
        pool = await get_db_pool()

        where_conditions = []
        params = []
        param_idx = 1

        if state:
            where_conditions.append(f"d.state_code = ${param_idx}")
            params.append(state.upper())
            param_idx += 1

        # Location scope. event_decision carries jurisdiction_name (always set) and
        # a sparser city column; a city browse (e.g. "Tuscaloosa") must not leak
        # decisions from the rest of the state, so match the city against either.
        if city and city.strip():
            where_conditions.append(
                f"(lower(d.jurisdiction_name) = lower(${param_idx}) OR lower(d.city) = lower(${param_idx}))"
            )
            params.append(city.strip())
            param_idx += 1

        has_query = bool(query and query.strip())
        rank_idx = None
        if has_query:
            # d.search_tsv is the persisted, GIN-indexed tsvector over
            # headline || decision_statement || primary_theme (built in the
            # event_decision mart) — same expression the column was generated
            # from, so this is a drop-in for the old ad-hoc to_tsvector and uses
            # the index instead of recomputing per row.
            where_conditions.append(f"(d.search_tsv @@ plainto_tsquery('english', ${param_idx}))")
            params.append(query.strip())
            rank_idx = param_idx
            param_idx += 1

        if outcome:
            # event_decision stores title-case outcomes ('Approved'); match
            # case-insensitively so callers can pass any casing.
            where_conditions.append(f"LOWER(d.outcome) = LOWER(${param_idx})")
            params.append(outcome)
            param_idx += 1

        if question_id:
            # Policy-question filter (Advanced): keep only decisions that
            # instantiate the chosen cross-jurisdiction question. public.question_instance
            # bridges a local_decision's event_decision_id to a policy_question.
            where_conditions.append(
                f"EXISTS (SELECT 1 FROM question_instance qi "
                f"WHERE qi.source_type = 'local_decision' "
                f"AND qi.source_id = d.event_decision_id "
                f"AND qi.question_id = ${param_idx})"
            )
            params.append(question_id)
            param_idx += 1

        if topic_tsquery:
            # Civic-topic filter (Advanced): narrow to decisions whose searchable
            # text matches the chosen named topic's keyword set. topic_tsquery is an
            # OR-tsquery ('kw1 | kw2 | ...') built by the caller from the served
            # public.civicsearch_topic catalog; search_tsv is the GIN-indexed vector.
            where_conditions.append(f"d.search_tsv @@ to_tsquery('english', ${param_idx})")
            params.append(topic_tsquery)
            param_idx += 1

        where_sql = " AND ".join(where_conditions) if where_conditions else "TRUE"

        # Meeting date (full ISO text) + body name come from event_meeting joined on
        # c1_event_id; event_date is often blank, so fall back to meeting_date. Some
        # rows carry the literal 'unknown' instead of a date — only accept a real
        # ISO YYYY-MM-DD so it sorts correctly and never renders "(unknown)".
        meeting_date_expr = (
            "CASE WHEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) "
            "~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' "
            "THEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) END"
        )

        # Sort modes — the pager shows 20 per page; let users reorder them.
        s = (sort or 'relevance').lower()
        if s in ('date_asc', 'oldest'):
            order_by = f"{meeting_date_expr} ASC NULLS LAST, d.extracted_at ASC"
        elif s in ('date_desc', 'newest', 'date'):
            order_by = f"{meeting_date_expr} DESC NULLS LAST, d.extracted_at DESC"
        elif s == 'theme':
            order_by = "d.primary_theme ASC NULLS LAST, d.extracted_at DESC"
        elif s == 'outcome':
            order_by = "d.outcome ASC NULLS LAST, d.extracted_at DESC"
        elif has_query:
            # relevance (default when there's a text query)
            order_by = (
                f"ts_rank(d.search_tsv, "
                f"plainto_tsquery('english', ${rank_idx})) DESC, {meeting_date_expr} DESC NULLS LAST"
            )
        else:
            # relevance with no query -> newest meeting first
            order_by = f"{meeting_date_expr} DESC NULLS LAST, d.extracted_at DESC"

        sql = f"""
            SELECT
                d.event_decision_id,
                d.analysis_id,
                d.decision_id,
                d.subject_id,
                d.headline,
                d.decision_statement,
                d.outcome,
                d.primary_theme,
                d.vote_tally,
                d.jurisdiction_name,
                d.jurisdiction_type,
                d.state_code,
                d.state,
                d.city,
                d.c1_event_id,
                d.extracted_at,
                m.body_name AS meeting_name,
                {meeting_date_expr} AS meeting_date,
                m.video_id AS meeting_video_id,
                ii.competing_views_count AS competing_views_count,
                ii.votes_yes AS ii_votes_yes,
                ii.votes_no AS ii_votes_no
            FROM event_decision d
            LEFT JOIN event_meeting m ON m.c1_event_id = d.c1_event_id
            LEFT JOIN item_interestingness ii ON ii.event_decision_id = d.event_decision_id
            WHERE {where_sql}
            ORDER BY {order_by}, d.event_decision_id DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.append(limit)
        params.append(max(offset, 0))

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                # Title is the headline (the actual decision)
                title = row['headline'] or row['decision_statement'] or 'Untitled Decision'
                if len(title) > 150:
                    title = title[:150] + "..."

                # Subtitle includes theme + outcome + location
                subtitle_parts = []
                if row['primary_theme']:
                    subtitle_parts.append(row['primary_theme'])
                if row['outcome']:
                    subtitle_parts.append(row['outcome'])
                location = (
                    f"{row['jurisdiction_name']}, {row['state']}"
                    if row['jurisdiction_name'] and row['state']
                    else (row['state'] or '')
                )
                if location:
                    subtitle_parts.append(location)
                # Meeting + date so each row shows where/when the decision happened.
                meeting_date = row['meeting_date']
                meeting_name = row['meeting_name']
                meeting_bits = " ".join(
                    p for p in (
                        meeting_name,
                        f"({meeting_date})" if meeting_date else None,
                    ) if p
                )
                if meeting_bits:
                    subtitle_parts.append(meeting_bits)
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
                    url=f"/decisions/{row['event_decision_id']}",
                    score=1.0,
                    metadata={
                        'id': row['event_decision_id'],
                        'decision_id': row['decision_id'],
                        'subject_id': row['subject_id'],
                        'meeting_id': row['analysis_id'],
                        'meeting_name': meeting_name,
                        'meeting_date': meeting_date,
                        'meeting_video_id': row['meeting_video_id'],
                        # Canonical thumbnail key the frontend reads
                        # (result.metadata.video_id); from the meeting recording
                        # joined on c1_event_id. None when there's no recording.
                        'video_id': row['meeting_video_id'],
                        'outcome': row['outcome'],
                        'primary_theme': row['primary_theme'],
                        'vote_tally': row['vote_tally'],
                        # Contestedness signals from public.item_interestingness
                        # (LEFT JOIN — None when the decision has no scored row).
                        'competing_views_count': row['competing_views_count'],
                        'votes_yes': row['ii_votes_yes'],
                        'votes_no': row['ii_votes_no'],
                        'jurisdiction': row['jurisdiction_name'],
                        'jurisdiction_type': row['jurisdiction_type'],
                        'state': row['state'],
                        'state_code': row['state_code'],
                        'city': row['city'],
                        'c1_event_id': row['c1_event_id'],
                        'extracted_at': row['extracted_at'].isoformat() if row['extracted_at'] else None
                    }
                ))

            logger.info(f"⚖️ PostgreSQL decisions search: {len(results)} results")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL decisions search error: {e}")
        return []


async def search_questions_pg(
    query: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    question_id: Optional[str] = None,
) -> List[SearchResult]:
    """
    Search the cross-jurisdiction policy-question registry, backed by the
    public.policy_question mart (canonical questions clustered from decisions and
    bills, e.g. "Should the city fluoridate its water?").

    Query mode matches canonical_text with a case-insensitive ILIKE (the registry
    is small — curated/clustered questions — so a trigram-style ILIKE mirrors the
    lighter sibling types like causes/topics without needing an FTS index). Browse
    mode (no query) surfaces the curated featured questions first
    (is_featured desc, display_order asc nulls last), then the rest by reach.

    Args:
        query: Search text (matched against canonical_text)
        limit: Max results
        offset: Pagination offset

    Returns:
        List of SearchResult objects (result_type='question')
    """
    try:
        pool = await get_db_pool()

        where_conditions: List[str] = []
        params: List[Any] = []
        param_idx = 1

        # For now the whole site focuses on the curated/pinned "big questions"
        # only, so search (browse AND query mode) is scoped to the featured set.
        # Drop this predicate to search the full clustered registry again.
        where_conditions.append("is_featured = true")

        has_query = bool(query and query.strip())
        if has_query:
            where_conditions.append(f"canonical_text ILIKE ${param_idx}")
            params.append(f"%{query.strip()}%")
            param_idx += 1
            # Shorter (more specific) canonical_text first, then by reach.
            order_by = "length(canonical_text) ASC, instances_total DESC NULLS LAST"
        else:
            # Browse: curated featured rows first, in editorial order, then reach.
            order_by = (
                "is_featured DESC, display_order ASC NULLS LAST, "
                "instances_total DESC NULLS LAST"
            )

        if question_id:
            # Question filter (Advanced): pin the registry to the single chosen
            # question so the Questions tab mirrors the decisions filtered alongside it.
            where_conditions.append(f"question_id = ${param_idx}")
            params.append(question_id)
            param_idx += 1

        where_sql = " AND ".join(where_conditions) if where_conditions else "TRUE"

        sql = f"""
            SELECT
                question_id,
                canonical_text,
                topic_code,
                primary_theme,
                scope,
                status,
                instances_total,
                jurisdictions_total,
                jurisdictions_approved,
                is_featured,
                display_order
            FROM policy_question
            WHERE {where_sql}
            ORDER BY {order_by}, question_id ASC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.append(limit)
        params.append(max(offset, 0))

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                title = row['canonical_text'] or 'Untitled Question'
                if len(title) > 200:
                    title = title[:200] + "..."

                # Humanize the coarse theme bucket for the subtitle (same
                # replace/title convention the jurisdictions type uses).
                theme = row['primary_theme']
                theme_label = theme.replace('_', ' ').title() if theme else ''

                # Comparative-reach hint when the rollup is populated.
                reach_bits = []
                if row['jurisdictions_total']:
                    reach_bits.append(f"{row['jurisdictions_total']} jurisdictions")
                if row['instances_total']:
                    reach_bits.append(f"{row['instances_total']} instances")
                reach = " • ".join(reach_bits)

                subtitle = " • ".join(p for p in (theme_label, reach) if p)
                description = theme_label

                results.append(SearchResult(
                    result_type='question',
                    title=title,
                    subtitle=subtitle,
                    description=description,
                    url=f"/policy-question/{row['question_id']}",
                    score=1.0,
                    metadata={
                        'id': row['question_id'],
                        'question_id': row['question_id'],
                        'topic_code': row['topic_code'],
                        'primary_theme': row['primary_theme'],
                        'scope': row['scope'],
                        'status': row['status'],
                        'instances_total': row['instances_total'],
                        'jurisdictions_total': row['jurisdictions_total'],
                        'jurisdictions_approved': row['jurisdictions_approved'],
                        'is_featured': row['is_featured'],
                        'display_order': row['display_order'],
                    }
                ))

            logger.info(f"❓ PostgreSQL questions search: {len(results)} results")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL questions search error: {e}")
        return []


async def search_causes_pg(
    query: Optional[str] = None,
    limit: int = 10,
    offset: int = 0
) -> List[SearchResult]:
    """
    Search causes / NTEE categories, backed by the public.tag mart
    (vocabulary='ntee' — the hierarchical NTEE taxonomy).

    Replaces the retired `data/gold/reference/causes_ntee_codes.parquet` feed.
    Supports browse mode (no query): returns the most popular / lowest codes first.

    Args:
        query: Search text (matched against the NTEE label, description, and code)
        limit: Max results

    Returns:
        List of SearchResult objects (result_type='cause')
    """
    try:
        pool = await get_db_pool()

        where_clauses = ["vocabulary = 'ntee'"]
        params = []
        param_idx = 1

        if query and query.strip():
            where_clauses.append(f"""(
                to_tsvector('english', COALESCE(label, '') || ' ' || COALESCE(description, ''))
                @@ plainto_tsquery('english', ${param_idx})
                OR source_code ILIKE ${param_idx + 1}
            )""")
            params.append(query)
            params.append(f"%{query}%")
            param_idx += 2

            order_by = (
                f"ts_rank(to_tsvector('english', COALESCE(label, '') || ' ' || COALESCE(description, '')), "
                f"plainto_tsquery('english', ${param_idx - 2})) DESC, source_code ASC"
            )
        else:
            # Browse mode: popularity first, then code order
            order_by = "COALESCE(popularity_rank, 2147483647) ASC, source_code ASC"

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT
                tag_id,
                source_code,
                label,
                description,
                breadcrumb,
                category,
                subcategory,
                depth
            FROM tag
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.append(limit)
        params.append(max(offset, 0))

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                code = row['source_code']
                title = row['label'] or code or 'NTEE Category'
                # Prefer the hierarchy breadcrumb as context, else the description
                description = row['breadcrumb'] or row['description'] or row['category'] or ''

                results.append(SearchResult(
                    result_type='cause',
                    title=title,
                    subtitle=f"NTEE Code: {code}" if code else 'NTEE Category',
                    description=description,
                    url=f"/nonprofits?ntee_code={code}",
                    score=1.0,
                    metadata={
                        'tag_id': row['tag_id'],
                        'ntee_code': code,
                        'ntee_type': 'ntee',
                        'category': row['category'],
                        'subcategory': row['subcategory'],
                        'breadcrumb': row['breadcrumb'],
                        'depth': row['depth'],
                    }
                ))

            logger.info(f"🎯 PostgreSQL causes search: {len(results)} results")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL causes search error: {e}")
        return []


async def search_grants_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> List[SearchResult]:
    """
    Search nonprofit grants, backed by the public.grant mart (GivingTuesday 990
    Schedule I Part II grant lines: grantor org -> grantee, cash amount, purpose).

    public.grant has no FTS / tsvector column, so the query is matched with ILIKE
    against grantor_name, grantee_name, and purpose.

    Location is filtered by the GRANTOR's geography:
      - jurisdiction_id -> grantor_master_org_id is bridged to that jurisdiction
        (mdm_bridge_org_jurisdiction), the same exact-scope path as org search.
      - else state -> direct grantor_state_code match (indexed, ~100% populated).
      - else/also city -> direct lower(grantor_city_norm) match (indexed alongside
        grantor_state_code). Direct is fine for v1 given the coverage.

    Results are ordered by amount DESC (biggest grants first), so a bare browse
    (no query) returns the largest grants.

    Args:
        query: Search text (matched against grantor_name, grantee_name, purpose)
        state: Filter by grantor state code ('MA') or full name ('Massachusetts')
        city: Filter by grantor city (direct grantor_city_norm match)
        jurisdiction_id: Exact grantor jurisdiction scope via the org bridge
        limit: Max results
        offset: Pagination offset

    Returns:
        List of SearchResult objects (result_type='grant')
    """
    # Normalize state input to 2-letter code (matches grantor_state_code)
    state = normalize_state_input(state)

    try:
        pool = await get_db_pool()

        where_clauses = []
        params = []
        param_idx = 1

        # Grantor-location scope. jurisdiction_id (exact) goes through the org
        # bridge; otherwise fall back to the indexed direct grantor columns.
        if jurisdiction_id:
            where_clauses.append(
                f"grantor_master_org_id IN ("
                f"SELECT master_org_id FROM mdm_bridge_org_jurisdiction "
                f"WHERE jurisdiction_id = ${param_idx})"
            )
            params.append(jurisdiction_id)
            param_idx += 1
        else:
            if state:
                where_clauses.append(f"grantor_state_code = ${param_idx}")
                params.append(state.upper())
                param_idx += 1
            if city:
                where_clauses.append(f"lower(grantor_city_norm) = lower(${param_idx})")
                params.append(city.strip())
                param_idx += 1

        # No tsvector column on public.grant — ILIKE the one %q% pattern across the
        # three text columns the grant carries.
        has_query = bool(query and query.strip())
        if has_query:
            q = query.strip()
            where_clauses.append(f"""(
                grantor_name ILIKE ${param_idx}
                OR grantee_name ILIKE ${param_idx}
                OR purpose ILIKE ${param_idx}
            )""")
            params.append(f"%{q}%")
            param_idx += 1

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        sql = f"""
            SELECT
                grant_id,
                grantor_name,
                grantor_state_code,
                grantor_city_norm,
                grantee_name,
                grantee_city,
                grantee_state_code,
                amount,
                purpose,
                tax_year,
                source_url
            FROM "grant"
            WHERE {where_sql}
            ORDER BY amount DESC NULLS LAST
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.append(limit)
        params.append(offset)

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                grantor = row['grantor_name'] or 'Unknown grantor'
                grantee = row['grantee_name'] or 'Unknown grantee'
                title = f"{grantor} → {grantee}"

                amount = row['amount']
                amount_str = f"${amount:,}" if amount is not None else None

                # Grantor location for context: title-case the (lowercased)
                # city and expand the 2-letter code to the full state name
                # ("boston", "MA" -> "Boston, Massachusetts"). Raw codes stay in
                # metadata below; this only affects the human-facing subtitle.
                _city = (row['grantor_city_norm'] or '').strip()
                _city_display = _city.title() if _city else ''
                _code = row['grantor_state_code'] or ''
                _state_display = _STATE_CODE_TO_NAME.get(_code, _code)
                grantor_location = ", ".join(
                    p for p in (_city_display, _state_display) if p
                )

                subtitle = " • ".join(
                    p for p in (amount_str, grantor_location) if p
                )

                # Description: amount + purpose (truncated if long).
                purpose = row['purpose'] or ''
                if len(purpose) > 200:
                    purpose = purpose[:197] + "..."
                description = " • ".join(
                    p for p in (amount_str, purpose) if p
                ) or 'Nonprofit grant'

                results.append(SearchResult(
                    result_type='grant',
                    title=title,
                    subtitle=subtitle,
                    description=description,
                    url=f"/grants/{row['grant_id']}",
                    score=1.0,
                    metadata={
                        'grant_id': row['grant_id'],
                        'grantor_name': grantor,
                        'grantee_name': grantee,
                        'amount': amount,
                        'purpose': row['purpose'],
                        'tax_year': str(row['tax_year']) if row['tax_year'] is not None else None,
                        # Naming contract: grantor location is the card's geography.
                        'state': row['grantor_state_code'],
                        'state_code': row['grantor_state_code'],
                        'city': row['grantor_city_norm'],
                        'grantee_city': row['grantee_city'],
                        'grantee_state_code': row['grantee_state_code'],
                        'source_url': row['source_url'],
                    }
                ))

            logger.info(f"💰 PostgreSQL grants search: {len(results)} results")
            return results

    except asyncpg.exceptions.UndefinedTableError as e:
        # The grant mart may be unbuilt in some envs — degrade gracefully instead
        # of 500-ing the whole unified search.
        logger.warning(f"public.grant not found, skipping grants search: {e}")
        return []
    except Exception as e:
        logger.error(f"PostgreSQL grants search error: {e}")
        return []


async def search_grant_opportunities_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> List[SearchResult]:
    """
    Search federal grant OPPORTUNITIES, backed by the public.grant_opportunity
    mart (Grants.gov Search2 — prospective funding open / forecasted for
    application).

    DISTINCT from search_grants_pg: that searches the 990 Schedule I `grant` mart
    ("who got funded"); this searches open opportunities ("what's available now")
    and returns result_type='grant_opportunity'.

    public.grant_opportunity has no FTS / tsvector column, so the query is matched
    with ILIKE against title, agency_name, and opportunity_number.

    Location: opportunities carry no resolved org/jurisdiction geography yet, so
    `state` / `city` / `jurisdiction_id` are accepted for signature parity with
    the other search functions but do not filter results (federal opportunities
    are national). When geography enrichment lands, scope here.

    Ordering: still-open opportunities first (is_open DESC), then soonest
    application deadline (close_date ASC), so a bare browse surfaces the most
    actionable opportunities.

    Returns:
        List of SearchResult objects (result_type='grant_opportunity'). The url is the
        canonical public Grants.gov detail page (external_url).
    """
    try:
        pool = await get_db_pool()

        where_clauses = []
        params: list = []
        param_idx = 1

        has_query = bool(query and query.strip())
        if has_query:
            q = query.strip()
            where_clauses.append(f"""(
                title ILIKE ${param_idx}
                OR agency_name ILIKE ${param_idx}
                OR opportunity_number ILIKE ${param_idx}
            )""")
            params.append(f"%{q}%")
            param_idx += 1

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        sql = f"""
            SELECT
                opportunity_id,
                opportunity_number,
                title,
                agency_code,
                agency_name,
                open_date,
                close_date,
                opp_status,
                aln,
                is_open,
                external_url
            FROM grant_opportunity
            WHERE {where_sql}
            ORDER BY is_open DESC, close_date ASC NULLS LAST
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.append(limit)
        params.append(offset)

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                title = row['title'] or row['opportunity_number'] or 'Grant opportunity'

                agency = row['agency_name'] or row['agency_code'] or ''
                # close_date is a real date -> ISO string at the JSON boundary.
                close_date = row['close_date']
                close_str = close_date.isoformat() if close_date else None
                status = (row['opp_status'] or '').capitalize()

                subtitle = " • ".join(
                    p for p in (agency, status) if p
                )

                if close_str:
                    deadline = (
                        f"Closes {close_str}" if row['is_open']
                        else f"Closed {close_str}"
                    )
                else:
                    deadline = "No close date"
                description = " • ".join(
                    p for p in (row['opportunity_number'], deadline) if p
                ) or 'Federal grant opportunity'

                results.append(SearchResult(
                    result_type='grant_opportunity',
                    title=title,
                    subtitle=subtitle,
                    description=description,
                    # External Grants.gov detail page (no internal detail route).
                    url=row['external_url'] or '',
                    score=1.0,
                    metadata={
                        'opportunity_id': row['opportunity_id'],
                        'opportunity_number': row['opportunity_number'],
                        'agency_code': row['agency_code'],
                        'agency_name': row['agency_name'],
                        'open_date': row['open_date'].isoformat() if row['open_date'] else None,
                        'close_date': close_str,
                        'opp_status': row['opp_status'],
                        'aln': row['aln'],
                        'is_open': row['is_open'],
                        'external_url': row['external_url'],
                    }
                ))

            logger.info(f"🏛️ PostgreSQL grant opportunities search: {len(results)} results")
            return results

    except asyncpg.exceptions.UndefinedTableError as e:
        # The grant_opportunity mart may be unbuilt in some envs — degrade
        # gracefully instead of 500-ing the whole unified search.
        logger.warning(f"public.grant_opportunity not found, skipping grant opportunities search: {e}")
        return []
    except Exception as e:
        logger.error(f"PostgreSQL grant opportunities search error: {e}")
        return []

