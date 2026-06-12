"""
Bills API Routes — Postgres-backed (public serving layer).

All endpoints read the `bills` / `bill_sponsorship` marts and the
`rpt_bill_map_aggregate` mart from the public schema (thin views over gold,
published by the publish_public_serving dbt macro). Parquet/DuckDB reads were
retired — only bronze ingestion should ever touch parquet.

Column mapping (gold.bills mart -> legacy API field names kept for the frontend):
    identifier                 -> bill_number
    session_identifier         -> session
    latest_action_description  -> latest_action
    bill_uid                   -> bill_id
`first_action_date`, `abstract`, `source_url`, and per-bill `actions` are not
present in the current marts and surface as null/empty (the frontend renders
them conditionally).
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import asyncpg
import json
from loguru import logger
import os
from datetime import datetime, timedelta

from api.errors import parse_error
from api.database import DATA_SEARCH_PATH

router = APIRouter(prefix="/bills", tags=["bills"])

# Database configuration
NEON_DATABASE_URL_DEV = os.getenv("NEON_DATABASE_URL_DEV")
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")
DATABASE_URL = NEON_DATABASE_URL_DEV or NEON_DATABASE_URL

if DATABASE_URL:
    logger.info(f"🗄️  Bills using: {'DEV' if NEON_DATABASE_URL_DEV else 'PROD'} Postgres (public schema)")
else:
    logger.warning("⚠️  No database URL configured. Bills endpoints will not work.")

# Connection pool
_pool = None

# Cache for map data (TTL: 5 minutes)
_map_cache = {}
_map_cache_time = None
MAP_CACHE_DURATION = timedelta(minutes=5)


async def get_pool():
    """Get or create asyncpg connection pool (search_path = data schema, public)."""
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


def _maybe_json(value: Any) -> Any:
    """Decode a JSONB column that the pool returns as TEXT (no jsonb codec)."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _classification_list(value: Any) -> List[str]:
    decoded = _maybe_json(value)
    if isinstance(decoded, list):
        return decoded
    if decoded is None:
        return []
    return [decoded]


# Chamber / bill-type prefix predicates operate on the `identifier` column
# (e.g. "SB 180", "HB 12"). Kept identical to the prior parquet logic.
_CHAMBER_PREDICATES = {
    "house": "(identifier LIKE 'HB%' OR identifier LIKE 'HR%' OR identifier LIKE 'HJR%' OR identifier LIKE 'HCR%' OR identifier LIKE 'HJM%' OR identifier LIKE 'H %')",
    "senate": "(identifier LIKE 'SB%' OR identifier LIKE 'SR%' OR identifier LIKE 'SJR%' OR identifier LIKE 'SCR%' OR identifier LIKE 'SJM%' OR identifier LIKE 'S %')",
    "joint": "(identifier LIKE '%JR%' OR identifier LIKE '%JM%')",
}

_TYPE_PREDICATES = {
    "bill": "(identifier LIKE 'HB%' OR identifier LIKE 'SB%' OR identifier LIKE 'AB%')",
    "resolution": "(identifier LIKE 'HR%' OR identifier LIKE 'SR%' OR identifier LIKE 'AR%')",
    "joint_resolution": "(identifier LIKE 'HJR%' OR identifier LIKE 'SJR%' OR identifier LIKE 'AJR%')",
    "concurrent_resolution": "(identifier LIKE 'HCR%' OR identifier LIKE 'SCR%')",
    "memorial": "(identifier LIKE 'HJM%' OR identifier LIKE 'SJM%')",
}

_TOPIC_KEYWORDS = {
    'fluoride': ['fluorid'],
    'dental': ['dental'],
    'medicaid': ['medicaid'],
    'oral health': ['oral', 'dental', 'teeth'],
    'health': ['health'],
    'education': ['education', 'school'],
}

_STATUS_KEYWORDS = {
    'enacted': ['Enacted'],
    'passed': ['passed', 'Passed'],
    'adopted': ['Adopted', 'adopted'],
    'failed': ['Failed', 'failed'],
    'introduced': ['Introduced', 'introduced'],
    'referred': ['referred', 'Referred'],
    'reported': ['reported', 'Reported'],
}


class _Filters:
    """Accumulates an asyncpg ($1, $2, …) WHERE clause for the bills mart."""

    def __init__(self, state: str):
        self.clauses = ["state_code = $1"]
        self.params: List[Any] = [state]

    def _ph(self) -> str:
        return f"${len(self.params) + 1}"

    def add(
        self,
        q: Optional[str] = None,
        sessions: Optional[List[str]] = None,
        topic: Optional[str] = None,
        chambers: Optional[List[str]] = None,
        bill_types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
    ) -> "_Filters":
        if topic:
            keywords = _TOPIC_KEYWORDS.get(topic.lower(), [topic])
            parts = []
            for kw in keywords:
                parts.append(f"LOWER(title) LIKE LOWER({self._ph()})")
                self.params.append(f"%{kw}%")
            self.clauses.append(f"({' OR '.join(parts)})")

        if q:
            p1 = self._ph()
            self.params.append(f"%{q}%")
            p2 = self._ph()
            self.params.append(f"%{q}%")
            self.clauses.append(f"(LOWER(title) LIKE LOWER({p1}) OR LOWER(identifier) LIKE LOWER({p2}))")

        if sessions:
            phs = []
            for s in sessions:
                phs.append(self._ph())
                self.params.append(s)
            self.clauses.append(f"session_identifier IN ({','.join(phs)})")

        if chambers:
            preds = [_CHAMBER_PREDICATES[c.lower()] for c in chambers if c.lower() in _CHAMBER_PREDICATES]
            if preds:
                self.clauses.append(f"({' OR '.join(preds)})")

        if bill_types:
            preds = [_TYPE_PREDICATES[b.lower()] for b in bill_types if b.lower() in _TYPE_PREDICATES]
            if preds:
                self.clauses.append(f"({' OR '.join(preds)})")

        if statuses:
            status_conds = []
            for status in statuses:
                keywords = _STATUS_KEYWORDS.get(status.lower(), [status])
                kw_parts = []
                for kw in keywords:
                    kw_parts.append(f"LOWER(latest_action_description) LIKE LOWER({self._ph()})")
                    self.params.append(f"%{kw}%")
                status_conds.append(f"({' OR '.join(kw_parts)})")
            if status_conds:
                self.clauses.append(f"({' OR '.join(status_conds)})")

        return self

    @property
    def where(self) -> str:
        return " AND ".join(self.clauses)


async def fetch_bills_from_db(
    state: str,
    q: Optional[str] = None,
    sessions: Optional[List[str]] = None,
    topic: Optional[str] = None,
    chambers: Optional[List[str]] = None,
    bill_types: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Fetch bills from the Postgres `bills` mart (detailed drill-down)."""
    pool = await get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    f = _Filters(state).add(q=q, sessions=sessions, topic=topic,
                            chambers=chambers, bill_types=bill_types, statuses=statuses)

    count_sql = f"SELECT COUNT(*) FROM bills WHERE {f.where}"

    limit_ph = f"${len(f.params) + 1}"
    offset_ph = f"${len(f.params) + 2}"
    rows_sql = f"""
        SELECT
            b.bill_uid,
            b.identifier,
            b.title,
            b.classification,
            b.session_identifier,
            b.session_name,
            b.latest_action_date,
            b.latest_action_description,
            b.jurisdiction_id,
            j.name AS jurisdiction_name
        FROM bills b
        LEFT JOIN jurisdictions j ON j.jurisdiction_id = b.jurisdiction_id
        WHERE {f.where.replace('state_code', 'b.state_code')}
        ORDER BY b.latest_action_date DESC NULLS LAST, b.identifier DESC
        LIMIT {limit_ph} OFFSET {offset_ph}
    """

    async with pool.acquire() as conn:
        total = await conn.fetchval(count_sql, *f.params)
        rows = await conn.fetch(rows_sql, *f.params, limit, offset)

    bills = [
        {
            "bill_id": r["bill_uid"],
            "bill_number": r["identifier"],
            "title": r["title"],
            "classification": _classification_list(r["classification"]),
            "session": r["session_identifier"],
            "session_name": r["session_name"],
            "first_action_date": None,
            "latest_action_date": str(r["latest_action_date"]) if r["latest_action_date"] else None,
            "latest_action": r["latest_action_description"],
            "jurisdiction_name": r["jurisdiction_name"],
            "abstract": None,
            "source_url": None,
        }
        for r in rows
    ]

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
        "source": "postgres",
    }


async def fetch_sessions_from_db(
    state: str,
    topic: Optional[str] = None,
    chambers: Optional[List[str]] = None,
    bill_types: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    q: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate sessions from the Postgres `bills` mart, filtered by active filters."""
    pool = await get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    f = _Filters(state).add(q=q, topic=topic, chambers=chambers,
                            bill_types=bill_types, statuses=statuses)

    sql = f"""
        SELECT
            session_identifier AS session,
            MAX(session_name) AS session_name,
            MAX(latest_action_date) AS end_date,
            COUNT(*) AS bill_count
        FROM bills
        WHERE {f.where}
        GROUP BY session_identifier
        ORDER BY MAX(latest_action_date) DESC NULLS LAST, session_identifier DESC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *f.params)

    sessions = [
        {
            "session": r["session"],
            "session_name": r["session_name"],
            "start_date": None,
            "end_date": str(r["end_date"]) if r["end_date"] else None,
            "bill_count": r["bill_count"],
        }
        for r in rows
    ]

    return {
        "state": state,
        "sessions": sessions,
        "total_sessions": len(sessions),
        "source": "postgres",
    }


async def fetch_map_data_from_neon(
    topic: Optional[str] = None,
    session: Optional[str] = None
) -> Dict[str, Any]:
    """Fetch map aggregates from the rpt_bill_map_aggregate mart."""
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
                "source": "postgres"
            }

        state_data = {}
        for row in rows:
            state_code = row['state_code']

            sample_bills = _maybe_json(row['sample_bills']) or []

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
            "source": "postgres"
        }

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
    Search legislative bills from the Postgres `bills` mart (detailed drill-down).
    Supports multiple values for sessions, chambers, bill_types, and statuses via comma separation.

    **Examples:**
    - `/api/bills?state=AL&q=dental` - Search Alabama bills for "dental"
    - `/api/bills?state=AL&sessions=2024rs,2023rs` - Get bills from multiple sessions
    - `/api/bills?state=AL&chambers=house,senate` - Get House and Senate bills
    - `/api/bills?state=AL&bill_types=bill,resolution` - Get bills and resolutions
    - `/api/bills?state=AL&statuses=enacted,passed` - Get enacted and passed bills
    """
    try:
        session_list = sessions.split(',') if sessions else None
        chamber_list = chambers.split(',') if chambers else None
        bill_type_list = bill_types.split(',') if bill_types else None
        status_list = statuses.split(',') if statuses else None

        logger.info(f"📊 Bills request: state={state}, q={q}, sessions={session_list}, topic={topic}, chambers={chamber_list}, bill_types={bill_type_list}, statuses={status_list}")

        return await fetch_bills_from_db(
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bills query error for state={state}: {e}")
        error_detail = parse_error(e, context={"state": state, "query": q})
        return JSONResponse(status_code=500, content=error_detail.model_dump())


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
    Get legislative sessions for a state from the Postgres `bills` mart, filtered
    by active search criteria. Supports multiple values via comma separation.

    **Examples:**
    - `/api/bills/sessions?state=MA` - Get all Massachusetts sessions
    - `/api/bills/sessions?state=MA&topic=dental` - Get sessions with dental bills
    - `/api/bills/sessions?state=MA&chambers=house,senate` - Filter by House and Senate
    """
    try:
        chamber_list = chambers.split(',') if chambers else None
        bill_type_list = bill_types.split(',') if bill_types else None
        status_list = statuses.split(',') if statuses else None

        logger.info(f"📊 Sessions request: state={state}, topic={topic}, chambers={chamber_list}, bill_types={bill_type_list}, statuses={status_list}, q={q}")

        result = await fetch_sessions_from_db(
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
        error_detail = parse_error(e, context={"state": state})
        return JSONResponse(status_code=500, content=error_detail.model_dump())


@router.get("/map")
async def get_bill_map_data(
    topic: Optional[str] = Query(None, description="Topic to filter (e.g., dental, health, education)"),
    session: Optional[str] = Query(None, description="Legislative session")
):
    """
    Get aggregated bill data for choropleth map from the rpt_bill_map_aggregate mart.

    Returns pre-computed state-level aggregates for instant visualization.

    **Examples:**
    - `/api/bills/map` - Get national bill map data
    - `/api/bills/map?topic=dental` - Map dental legislation (not yet implemented)
    """
    try:
        if not DATABASE_URL:
            raise HTTPException(status_code=503, detail="Database not configured")

        return await fetch_map_data_from_neon(topic=topic, session=session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Map data query error: {e}")
        error_detail = parse_error(e, context={"topic": topic, "session": session})
        return JSONResponse(status_code=500, content=error_detail.model_dump())


@router.get("/filter-options")
async def get_filter_options(
    state: str = Query(..., description="State abbreviation (e.g., AL, GA)"),
    topic: Optional[str] = Query(None, description="Topic filter"),
    q: Optional[str] = Query(None, description="Search query")
):
    """
    Get available filter options for a state based on actual data in the `bills` mart.
    Returns only bill types, chambers, and statuses that exist for the selected state/topic.
    """
    try:
        pool = await get_pool()
        if pool is None:
            raise HTTPException(status_code=503, detail="Database not configured")

        f = _Filters(state.upper()).add(q=q, topic=topic)
        where = f.where

        # CASE expression for bill type, reused in SELECT + HAVING.
        type_case = (
            "CASE "
            "WHEN identifier LIKE 'HB%' OR identifier LIKE 'SB%' OR identifier LIKE 'AB%' THEN 'bill' "
            "WHEN identifier LIKE 'HR%' OR identifier LIKE 'SR%' OR identifier LIKE 'AR%' THEN 'resolution' "
            "WHEN identifier LIKE 'HJR%' OR identifier LIKE 'SJR%' OR identifier LIKE 'AJR%' THEN 'joint_resolution' "
            "WHEN identifier LIKE 'HCR%' OR identifier LIKE 'SCR%' THEN 'concurrent_resolution' "
            "WHEN identifier LIKE 'HJM%' OR identifier LIKE 'SJM%' THEN 'memorial' "
            "END"
        )
        chamber_case = (
            "CASE "
            "WHEN identifier LIKE 'HB%' OR identifier LIKE 'HR%' OR identifier LIKE 'HJR%' OR "
            "identifier LIKE 'HCR%' OR identifier LIKE 'HJM%' OR identifier LIKE 'H %' THEN 'house' "
            "WHEN identifier LIKE 'SB%' OR identifier LIKE 'SR%' OR identifier LIKE 'SJR%' OR "
            "identifier LIKE 'SCR%' OR identifier LIKE 'SJM%' OR identifier LIKE 'S %' THEN 'senate' "
            "WHEN identifier LIKE '%JR%' OR identifier LIKE '%JM%' THEN 'joint' "
            "END"
        )
        status_case = (
            "CASE "
            "WHEN LOWER(latest_action_description) LIKE '%enact%' THEN 'enacted' "
            "WHEN LOWER(latest_action_description) LIKE '%pass%' THEN 'passed' "
            "WHEN LOWER(latest_action_description) LIKE '%adopt%' THEN 'adopted' "
            "WHEN LOWER(latest_action_description) LIKE '%fail%' THEN 'failed' "
            "WHEN LOWER(latest_action_description) LIKE '%introduc%' THEN 'introduced' "
            "WHEN LOWER(latest_action_description) LIKE '%refer%' THEN 'referred' "
            "WHEN LOWER(latest_action_description) LIKE '%report%' THEN 'reported' "
            "END"
        )

        sql_types = f"""
            SELECT {type_case} AS bill_type, COUNT(*) AS count
            FROM bills WHERE {where}
            GROUP BY bill_type
            HAVING ({type_case}) IS NOT NULL
            ORDER BY count DESC
        """
        sql_chambers = f"""
            SELECT {chamber_case} AS chamber, COUNT(*) AS count
            FROM bills WHERE {where}
            GROUP BY chamber
            HAVING ({chamber_case}) IS NOT NULL
            ORDER BY count DESC
        """
        sql_statuses = f"""
            SELECT {status_case} AS status, COUNT(*) AS count
            FROM bills WHERE {where} AND latest_action_description IS NOT NULL
            GROUP BY status
            HAVING ({status_case}) IS NOT NULL
            ORDER BY count DESC
        """

        async with pool.acquire() as conn:
            type_rows = await conn.fetch(sql_types, *f.params)
            chamber_rows = await conn.fetch(sql_chambers, *f.params)
            status_rows = await conn.fetch(sql_statuses, *f.params)

        type_labels = {
            'bill': 'Bill (HB/SB)',
            'resolution': 'Resolution (HR/SR)',
            'joint_resolution': 'Joint Resolution (HJR/SJR)',
            'concurrent_resolution': 'Concurrent Resolution (HCR/SCR)',
            'memorial': 'Memorial (HJM/SJM)'
        }
        chamber_labels = {'house': 'House', 'senate': 'Senate', 'joint': 'Joint'}
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
                {"value": r["bill_type"], "label": type_labels.get(r["bill_type"], r["bill_type"]), "count": r["count"]}
                for r in type_rows
            ],
            "chambers": [
                {"value": r["chamber"], "label": chamber_labels.get(r["chamber"], r["chamber"]), "count": r["count"]}
                for r in chamber_rows
            ],
            "statuses": [
                {"value": r["status"], "label": status_labels.get(r["status"], r["status"]), "count": r["count"]}
                for r in status_rows
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Filter options query error for state={state}: {e}")
        error_detail = parse_error(e, context={"state": state, "topic": topic, "q": q})
        return JSONResponse(status_code=500, content=error_detail.model_dump())


@router.get("/versions")
async def get_bill_versions(
    bill_id: str = Query(..., description="Bill ID (e.g., ocd-bill/...)")
):
    """
    Get all text versions for a specific bill.

    Bill text versions are not part of the current Postgres marts, so this returns
    an explicit empty result rather than fabricating data.
    """
    return {
        "bill_id": bill_id,
        "total": 0,
        "versions": [],
        "message": "Bill versions data not available"
    }


@router.get("/{bill_id}")
async def get_bill_details(bill_id: str):
    """
    Get detailed information about a specific bill from the Postgres `bills` mart.

    Args:
        bill_id: Bill identifier in format {state}-{bill_number} (e.g., "mo-SB 1548")

    Returns:
        Detailed bill information including sponsors.

    Examples:
        - `/api/bills/ga-HB 123` - Georgia House Bill 123
        - `/api/bills/mo-SB 1548` - Missouri Senate Bill 1548
    """
    try:
        if '-' not in bill_id:
            raise HTTPException(status_code=400, detail="Invalid bill ID format. Expected: STATE-BILLNUMBER")

        parts = bill_id.split('-', 1)
        state = parts[0].upper()
        bill_number = parts[1]

        pool = await get_pool()
        if pool is None:
            raise HTTPException(status_code=503, detail="Database not configured")

        bill_sql = """
            SELECT
                b.bill_uid,
                b.identifier,
                b.title,
                b.classification,
                b.latest_action_description,
                b.latest_action_date,
                b.session_identifier,
                b.session_name,
                b.jurisdiction_id,
                j.name AS jurisdiction_name
            FROM bills b
            LEFT JOIN jurisdictions j ON j.jurisdiction_id = b.jurisdiction_id
            WHERE b.state_code = $1 AND b.identifier = $2
            ORDER BY b.latest_action_date DESC NULLS LAST
            LIMIT 1
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(bill_sql, state, bill_number)

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Bill {bill_number} not found in {state}."
                )

            bill_uid = row["bill_uid"]
            bill_data = {
                "bill_id": bill_uid or bill_id,
                "bill_number": row["identifier"],
                "title": row["title"],
                "classification": _classification_list(row["classification"]),
                "latest_action": row["latest_action_description"],
                "latest_action_date": str(row["latest_action_date"]) if row["latest_action_date"] else None,
                "first_action_date": None,
                "session": row["session_identifier"],
                "session_name": row["session_name"],
                "jurisdiction": row["jurisdiction_name"],
                "state": state,
            }

            sponsor_rows = await conn.fetch(
                """
                SELECT sponsor_name, is_primary, classification
                FROM bill_sponsorship
                WHERE bill_uid = $1
                ORDER BY is_primary DESC NULLS LAST
                """,
                bill_uid,
            )
            bill_data["sponsors"] = [
                {
                    "name": s["sponsor_name"],
                    "primary": bool(s["is_primary"]),
                    "classification": s["classification"],
                }
                for s in sponsor_rows
            ]

            # Per-bill action history is not in the current marts.
            bill_data["actions"] = []
            bill_data["sources"] = []

            return bill_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bill details error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
