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
    limit: int = 10
) -> List[SearchResult]:
    """
    Search people using PostgreSQL, backed by the MDM person master (mdm_person).

    - Deduplicates to one result per RESOLVED person (master_person_id), picking
      the best source occurrence.
    - Matches names with trigram similarity (typo-tolerant; uses the
      mdm_person_full_name_trgm_idx GIN index).
    - Joins mdm_bridge_person_organization for the person's top org / title.

    Replaces the retired `contact` table feed (which no longer exists).

    Args:
        query: Search text (person name)
        state: Filter by state code ('MA') or full name ('Massachusetts')
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
                SELECT org_name, master_org_id, title, reportable_comp_org
                FROM mdm_bridge_person_organization b
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
                SELECT d.*, o.org_name, o.master_org_id, o.title, o.reportable_comp_org
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
            # Browse (no name query): stop after `limit` distinct people in
            # master_person_id order so we never sort the full 2.2M-row table.
            sql = f"""
                SELECT d.*, o.org_name, o.master_org_id, o.title, o.reportable_comp_org
                FROM (
                    SELECT DISTINCT ON (p.master_person_id)
                        {base_select}
                    FROM mdm_person p
                    WHERE {where_sql}
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
                location = f"{row['city_norm']}, {row['state_code']}" if row['city_norm'] and row['state_code'] else (row['state_code'] or '')

                # Key the detail URL on person_uid (the true unique PK), NOT
                # master_person_id. The MDM resolved-entity id badly over-merges
                # (one master_person_id can blob together 50+ unrelated people in
                # the same city), so it does not identify the person the user
                # clicked. person_uid is one row per real source occurrence.
                # Fall back to the legacy name slug only if person_uid is null.
                person_uid = row['person_uid']
                person_url = (
                    f"/person/{person_uid}"
                    if person_uid
                    else f"/people/{name.replace(' ', '-')}"
                )

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
                    }
                ))

            logger.info(f"👤 PostgreSQL person search: {len(results)} results")
            return results

    except Exception as e:
        logger.error(f"PostgreSQL person search error: {e}")
        return []


# Back-compat alias: the dispatcher and any external callers may still reference
# the old name. Person search is now MDM-backed (mdm_person).
search_contacts_pg = search_persons_pg


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

    Reads public.organization_nonprofit_compensation (Form 990 Part VII-A enriched
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

        cols = """event_id, event_title, event_description, event_date,
                jurisdiction_name, jurisdiction_type, state_code, state,
                city, video_url, agenda_url"""

        has_query = bool(query and query.strip())
        params = []

        if has_query:
            # The title-FTS / jurisdiction-substring match used to be a single
            # `to_tsvector(title) @@ q OR LOWER(jurisdiction) LIKE '%q%'`. The
            # leading-wildcard LIKE in an OR is un-indexable, forcing a full
            # 153k-row seq scan that recomputed to_tsvector on every row (~3.8s
            # for a common term). Split into a UNION of two index-backed branches:
            #   - title @@ query  -> event_title_fts_idx (GIN on to_tsvector)
            #   - jurisdiction ILIKE -> event_jurisdiction_trgm_idx (GIN pg_trgm)
            # Order by event_date (recent first) instead of ts_rank: the result
            # score is a constant 1.0 anyway, so ranking was only internal
            # tie-breaking, and ranking a large match set was itself the stall.
            q = query.strip()
            params.append(q)
            q_pos = len(params)
            params.append(f"%{q}%")
            like_pos = len(params)
            state_clause = ""
            if state:
                params.append(state.upper())
                state_clause = f" AND state_code = ${len(params)}"
            params.append(limit)
            lim_pos = len(params)

            sql = f"""
                WITH matched AS (
                    SELECT event_id FROM event
                    WHERE to_tsvector('english', event_title) @@ plainto_tsquery('english', ${q_pos}){state_clause}
                    UNION
                    SELECT event_id FROM event
                    WHERE jurisdiction_name ILIKE ${like_pos}{state_clause}
                )
                SELECT {cols}
                FROM event e
                JOIN matched m USING (event_id)
                ORDER BY e.event_date DESC NULLS LAST
                LIMIT ${lim_pos}
            """
        else:
            # Browse: most recent meetings first (optionally state-scoped).
            where_sql = "TRUE"
            if state:
                params.append(state.upper())
                where_sql = f"state_code = ${len(params)}"
            params.append(limit)
            sql = f"""
                SELECT {cols}
                FROM event
                WHERE {where_sql}
                ORDER BY event_date DESC NULLS LAST
                LIMIT ${len(params)}
            """

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


async def search_documents_pg(
    query: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 10
) -> List[SearchResult]:
    """
    Full-text search over event documents (meeting transcripts) using PostgreSQL.

    Searches the body text of public.event_documents (transcripts today) and
    returns a highlighted snippet of the matching passage so results show *why*
    they matched, plus the linkable meeting it belongs to.

    Args:
        query: Search text (matched against the document body)
        state: Filter by state code ('MA') or full name ('Massachusetts')
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

        sql = f"""
            SELECT
                event_document_id,
                event_id,
                document_type,
                document_source,
                video_id,
                event_title,
                event_date,
                jurisdiction_name,
                jurisdiction_type,
                state_code,
                state,
                city,
                video_url,
                word_count,
                {snippet_sql} AS snippet
            FROM event_documents
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ${param_idx}
        """
        # Bound the snippet/detoast work regardless of the caller's over-fetch.
        params.append(min(limit, DOCUMENT_RESULT_CAP))

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            results = []
            for row in rows:
                location = f"{row['jurisdiction_name']}, {row['state']}" if row['jurisdiction_name'] and row['state'] else ''
                date_str = row['event_date'].strftime('%Y-%m-%d') if row['event_date'] else ''
                title = row['event_title'] or 'Meeting transcript'
                subtitle = f"{location} - {date_str}".strip(' -')

                # event_id is nullable (orphan transcripts have no golden event);
                # deep-link to the meeting when one exists, else fall back to the
                # source video.
                if row['event_id'] is not None:
                    url = f"/documents?meeting_id={row['event_id']}"
                else:
                    url = row['video_url'] or ''

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
    limit: int = 10
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
            ORDER BY {order_by}
            LIMIT ${param_idx}
        """
        params.append(limit)

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
                    url=f"/bills/{row['state_code']}/{number}" if number and row['state_code'] else '',
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
            ORDER BY {order_by}
            LIMIT ${param_idx}
        """
        params.append(limit)

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
    limit: int = 10
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
            where_conditions.append(f"state_code = ${param_idx}")
            params.append(state.upper())
            param_idx += 1

        if query and query.strip():
            where_conditions.append(f"""(
                to_tsvector('english', COALESCE(headline, '') || ' ' || COALESCE(decision_statement, '') || ' ' || COALESCE(primary_theme, ''))
                @@ plainto_tsquery('english', ${param_idx})
            )""")
            params.append(query)
            param_idx += 1

            order_by = (
                f"ts_rank(to_tsvector('english', COALESCE(headline, '') || ' ' || COALESCE(decision_statement, '') || ' ' || COALESCE(primary_theme, '')), "
                f"plainto_tsquery('english', ${param_idx - 1})) DESC, extracted_at DESC"
            )
        else:
            order_by = "extracted_at DESC"

        if outcome:
            # event_decision stores title-case outcomes ('Approved'); match
            # case-insensitively so callers can pass any casing.
            where_conditions.append(f"LOWER(outcome) = LOWER(${param_idx})")
            params.append(outcome)
            param_idx += 1

        where_sql = " AND ".join(where_conditions) if where_conditions else "TRUE"

        sql = f"""
            SELECT
                event_decision_id,
                analysis_id,
                decision_id,
                subject_id,
                headline,
                decision_statement,
                outcome,
                primary_theme,
                vote_tally,
                jurisdiction_name,
                jurisdiction_type,
                state_code,
                state,
                city,
                c1_event_id,
                extracted_at
            FROM event_decision
            WHERE {where_sql}
            ORDER BY {order_by}
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
                        'outcome': row['outcome'],
                        'primary_theme': row['primary_theme'],
                        'vote_tally': row['vote_tally'],
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


async def search_causes_pg(
    query: Optional[str] = None,
    limit: int = 10
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
            LIMIT ${param_idx}
        """
        params.append(limit)

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

