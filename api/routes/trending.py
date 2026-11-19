"""
Trending causes/topics API endpoints.

Reads from the bronze ingestion tables landed by:
  - ingestion.everyorg.causes  -> bronze.bronze_everyorg_causes
  - ingestion.ntee.codes       -> bronze.bronze_ntee_codes

Falls back to the public.tag mart if the bronze migration has
not been run yet (during the Stage-2 transition).
"""
import asyncio
import os
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from fastapi import APIRouter, Query
from loguru import logger
from pydantic import BaseModel

from api.routes.search_postgres import normalize_state_input

router = APIRouter(prefix="/api/trending", tags=["trending"])

_DEFAULT_LOCAL_DB_URL = "postgresql://postgres:password@localhost:5433/open_navigator"
_DB_ENV_PRIORITY = (
    "NEON_DATABASE_URL_DEV",
    "NEON_DATABASE_URL",
    "OPEN_NAVIGATOR_DATABASE_URL",
    "DATABASE_URL",
)


def resolve_db_url() -> str:
    """Resolve database URL across dev, Neon production, and standard env vars."""
    for env_key in _DB_ENV_PRIORITY:
        raw = (os.getenv(env_key) or "").strip()
        if raw:
            if raw.startswith("postgres://"):
                return raw.replace("postgres://", "postgresql://", 1)
            return raw
    return _DEFAULT_LOCAL_DB_URL


LOCAL_DB_URL = resolve_db_url()
_INITIAL_LOCAL_DB_URL = LOCAL_DB_URL

# Bounded in-memory TTL cache and per-key inflight lock map to prevent
# event-loop blocking and duplicate concurrent Postgres connections.
_CACHE_TTL_S: float = 300.0
_MAX_CACHE_ENTRIES: int = 128
_trending_cache: Dict[str, Tuple[float, Any]] = {}
_inflight_locks: Dict[str, asyncio.Lock] = {}
_inflight_users: Dict[str, int] = {}


def clear_trending_cache() -> None:
    """Clear in-memory trending cache and inflight locks."""
    _trending_cache.clear()
    _inflight_locks.clear()
    _inflight_users.clear()


@asynccontextmanager
async def _inflight(cache_key: str):
    """Hold the per-key lock that dedupes concurrent cache fills, and drop it once the last user is done.

    ``?city=`` is free text, so keeping every key's lock for the life of the process would grow the map without
    bound (#447). The lock is removed when its last waiter leaves, and only if the map still holds *this* lock,
    so one request can never remove a lock another request just created.
    """
    lock = _inflight_locks.setdefault(cache_key, asyncio.Lock())
    _inflight_users[cache_key] = _inflight_users.get(cache_key, 0) + 1
    try:
        async with lock:
            yield
    finally:
        left = _inflight_users.get(cache_key, 1) - 1
        if left > 0:
            _inflight_users[cache_key] = left
        else:
            _inflight_users.pop(cache_key, None)
            if _inflight_locks.get(cache_key) is lock:
                del _inflight_locks[cache_key]


def _get_cached(key: str) -> Optional[Any]:
    if _CACHE_TTL_S <= 0:
        return None
    entry = _trending_cache.get(key)
    if entry is None:
        return None
    fetched_at, payload = entry
    if time.monotonic() - fetched_at >= _CACHE_TTL_S:
        _trending_cache.pop(key, None)
        return None
    return payload


def _set_cached(key: str, payload: Any) -> None:
    if _CACHE_TTL_S <= 0:
        return
    now = time.monotonic()
    if len(_trending_cache) >= _MAX_CACHE_ENTRIES and key not in _trending_cache:
        expired = [k for k, (ts, _) in _trending_cache.items() if now - ts >= _CACHE_TTL_S]
        for k in expired:
            _trending_cache.pop(k, None)
        if len(_trending_cache) >= _MAX_CACHE_ENTRIES:
            oldest_key = min(_trending_cache, key=lambda k: _trending_cache[k][0])
            _trending_cache.pop(oldest_key, None)
    _trending_cache[key] = (now, payload)


def _active_db_url() -> str:
    """Return runtime-patched LOCAL_DB_URL if modified, otherwise resolve from env."""
    if LOCAL_DB_URL != _INITIAL_LOCAL_DB_URL:
        if LOCAL_DB_URL.startswith("postgres://"):
            return LOCAL_DB_URL.replace("postgres://", "postgresql://", 1)
        return LOCAL_DB_URL
    return resolve_db_url()


@contextmanager
def _cursor():
    conn = psycopg2.connect(_active_db_url())
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


_NTEE_ICON_MAP = {
    'A': '🎨', 'B': '📚', 'C': '🌍', 'D': '🐾', 'E': '⚕️',
    'F': '🏥', 'G': '🏛️', 'H': '🏥', 'I': '🔬', 'J': '👥',
    'K': '🍽️', 'L': '🏠', 'M': '🛡️', 'N': '🎯', 'O': '⚖️',
    'P': '👶', 'Q': '🌐', 'R': '🏛️', 'S': '🤝', 'T': '💼',
    'U': '🔬', 'V': '⚡', 'W': '📢', 'X': '🏛️', 'Y': '🏛️',
    'Z': '🔤',
}


class CauseItem(BaseModel):
    """A trending cause/topic"""
    # Stable slug (EveryOrg cause id, e.g. 'education') / NTEE code. The frontend
    # passes this as ?cause_id= to scope decisions/meetings to the cause.
    cause_id: Optional[str] = None
    name: str
    icon: str
    category: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    popularity_rank: Optional[int] = None
    # Real count of analyzed meetings whose transcript matches this cause's
    # keyword set (gold.meeting_cause_link). 0 is honest — no fabricated figure.
    meeting_count: int = 0


class TrendingResponse(BaseModel):
    """Response with trending causes"""
    causes: List[CauseItem]
    total: int


class TrendingTopicItem(BaseModel):
    """A trending legislative topic (bill subject)."""
    name: str
    bill_count: int
    recent_bill_count: int
    state_code: Optional[str] = None


class TrendingTopicsResponse(BaseModel):
    """Response with trending legislative topics."""
    topics: List[TrendingTopicItem]
    total: int


# Causes joined to their real meeting count, ordered most-discussed first. The
# count comes from gold.meeting_cause_link (a transcript full-text match per
# cause). NULL meeting_count is coalesced to 0 (honest empty), never fabricated.
_CAUSES_WITH_COUNT_SQL = """
    SELECT c.cause_id, c.cause_name, c.description, c.icon, c.category,
           c.popularity_rank,
           COALESCE(mc.meeting_count, 0) AS meeting_count
    FROM bronze.bronze_everyorg_causes c
    LEFT JOIN (
        SELECT cause_id, COUNT(DISTINCT event_meeting_id) AS meeting_count
        FROM gold.meeting_cause_link
        WHERE (%(state)s IS NULL OR state_code = %(state)s)
          AND (%(city)s  IS NULL OR lower(jurisdiction_name) = lower(%(city)s)
                                 OR lower(city) = lower(%(city)s))
        GROUP BY cause_id
    ) mc ON mc.cause_id = c.cause_id
    -- When a place is in scope, keep only causes actually discussed there so the
    -- pills reflect that place (no global causes with a 0 local count).
    WHERE (%(state)s IS NULL AND %(city)s IS NULL) OR mc.meeting_count > 0
    ORDER BY COALESCE(mc.meeting_count, 0) DESC,
             c.popularity_rank NULLS LAST, c.cause_name
    LIMIT %(limit)s
"""

# Fallback when gold.meeting_cause_link is absent (e.g. a serving DB where the
# linkage mart hasn't been built). Causes still render, just with no count.
_CAUSES_NO_COUNT_SQL = """
    SELECT cause_id, cause_name, description, icon, category, popularity_rank, 0 AS meeting_count
    FROM bronze.bronze_everyorg_causes
    ORDER BY popularity_rank NULLS LAST, cause_name
    LIMIT %(limit)s
"""


def get_everyorg_causes(
    limit: int = 20,
    state: Optional[str] = None,
    city: Optional[str] = None,
) -> List[CauseItem]:
    """Load EveryOrg causes (with real per-cause meeting counts) from the warehouse.

    When ``state``/``city`` are given, the per-cause meeting_count is scoped to
    that place (gold.meeting_cause_link carries state_code/jurisdiction_name/city)
    and only causes actually discussed there are returned — so Browse Causes shows
    a place-specific pill set, mirroring the Topics flow.
    """
    if limit <= 0:
        return []
    norm_state = normalize_state_input(state) if state else None
    norm_city = (city or "").strip() or None
    params = {"state": norm_state, "city": norm_city, "limit": limit}
    rows: list = []
    try:
        with _cursor() as cur:
            try:
                cur.execute(_CAUSES_WITH_COUNT_SQL, params)
                rows = cur.fetchall()
            except psycopg2.Error:
                # Linkage mart missing/unreadable — fall back to the plain list so
                # causes never disappear. Roll back aborted transaction on same conn.
                cur.connection.rollback()
                cur.execute(_CAUSES_NO_COUNT_SQL, {"limit": limit})
                rows = cur.fetchall()
    except Exception as exc:
        logger.warning(f"EveryOrg causes query failed (table empty or missing?): {exc}")
        return []

    return [
        CauseItem(
            cause_id=cause_id,
            name=name,
            icon=icon or '📌',
            category=category or 'general',
            description=description or '',
            image_url=f"/images/causes/everyorg_{cause_id}_square.png",
            popularity_rank=popularity_rank,
            meeting_count=int(meeting_count or 0),
        )
        for (cause_id, name, description, icon, category, popularity_rank, meeting_count) in rows
    ]


def get_ntee_causes(limit: int = 20, level: Optional[int] = None) -> List[CauseItem]:
    """Load NTEE code causes from bronze.bronze_ntee_codes (or the public.tag mart).

    Args:
        limit: max rows to return.
        level: 1 = major groups (single-letter codes), 2 = divisions (3-char codes).
    """
    if limit <= 0:
        return []
    # `level` maps directly to code length: A = level 1, A20 = level 2.
    bronze_where = ["cause_type = 'ntee'"]
    # public.tag filters NTEE rows via vocabulary; code lives in source_code.
    mart_where = ["vocabulary = 'ntee'"]
    params: list = []
    if level == 1:
        bronze_where.append("length(code) = 1")
        mart_where.append("length(source_code) = 1")
    elif level == 2:
        bronze_where.append("length(code) = 3")
        mart_where.append("length(source_code) = 3")

    bronze_sql = f"""
        SELECT code, name, description, category
        FROM bronze.bronze_ntee_codes
        WHERE {' AND '.join(bronze_where)}
        ORDER BY length(code), code
        LIMIT %s
    """
    # Fall back to the public.tag mart (supersedes the legacy cause_ntee table).
    mart_sql = f"""
        SELECT source_code AS code, label AS name, description, category
        FROM public.tag
        WHERE {' AND '.join(mart_where)}
        ORDER BY length(source_code), source_code
        LIMIT %s
    """
    params.append(limit)

    rows = _query_with_legacy_fallback(
        primary_sql=bronze_sql,
        legacy_sql=mart_sql,
        params=params,
    )
    if rows is None:
        return []

    out: List[CauseItem] = []
    for code, name, description, category in rows:
        icon = _NTEE_ICON_MAP.get((code or 'Z')[0], '📌')
        out.append(CauseItem(
            cause_id=code,
            name=name or code,
            icon=icon,
            category=category or 'ntee',
            description=description or f"NTEE Code {code}",
            image_url=f"/images/causes/ntee_{code}_square.png",
            popularity_rank=None,
        ))
    return out


def _query_with_legacy_fallback(primary_sql: str, legacy_sql: str, params):
    """Try the bronze table first; fall back to the public.tag mart on the same connection.

    Returns None if both fail (so the caller can render an empty response
    instead of 500ing).
    """
    try:
        with _cursor() as cur:
            try:
                cur.execute(primary_sql, params)
                return cur.fetchall()
            except psycopg2.errors.UndefinedTable:
                logger.info("bronze.bronze_ntee_codes not found, falling back to public.tag")
                cur.connection.rollback()
                cur.execute(legacy_sql, params)
                return cur.fetchall()
    except Exception as exc:
        logger.warning(f"Trending query with legacy fallback failed: {exc}")
        return None


def _compute_trending_causes_sync(
    norm_source: str,
    limit: int,
    level: Optional[int],
    state: Optional[str],
    city: Optional[str],
) -> List[CauseItem]:
    if norm_source == "ntee":
        return get_ntee_causes(limit=limit, level=level)
    if norm_source == "mixed":
        everyorg_limit = (limit + 1) // 2
        ntee_limit = max(1, limit // 2) if limit > 1 else 0
        everyorg = get_everyorg_causes(limit=everyorg_limit, state=state, city=city)
        ntee = get_ntee_causes(limit=ntee_limit, level=level if level in (1, 2) else 1) if ntee_limit > 0 else []
        causes: List[CauseItem] = []
        for i in range(max(len(everyorg), len(ntee))):
            if i < len(everyorg):
                causes.append(everyorg[i])
            if i < len(ntee):
                causes.append(ntee[i])
        return causes[:limit]
    return get_everyorg_causes(limit=limit, state=state, city=city)


@router.get("", response_model=TrendingResponse)
async def get_trending_causes(
    source: str = Query("everyorg", description="Source: 'everyorg', 'ntee', or 'mixed'"),
    limit: int = Query(12, ge=1, le=100, description="Max number of causes to return"),
    level: Optional[int] = Query(None, description="NTEE level filter (1 or 2)"),
    state: Optional[str] = Query(None, description="2-letter code or full state name; scopes EveryOrg cause meeting counts to that state (omit for national)"),
    city: Optional[str] = Query(None, description="City/jurisdiction name; further scopes EveryOrg cause meeting counts to that place"),
) -> TrendingResponse:
    """
    Get trending causes for homepage.

    Reads from bronze tables landed by ingestion.everyorg.causes and
    ingestion.ntee.codes.

    **Sources:**
    - `everyorg`: Curated popular causes
    - `ntee`: IRS nonprofit categories
    - `mixed`: Interleaved from both
    """
    norm_source = (source or "everyorg").strip().lower()
    norm_state = normalize_state_input(state) if state else None
    norm_city = (city or "").strip().lower() or None
    cache_key = f"causes:{norm_source}:{limit}:{level}:{norm_state}:{norm_city}"

    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    async with _inflight(cache_key):
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached

        causes = await asyncio.to_thread(
            _compute_trending_causes_sync,
            norm_source,
            limit,
            level,
            state,
            city,
        )
        response = TrendingResponse(causes=causes, total=len(causes))
        if causes:
            _set_cached(cache_key, response)
        return response


def _fetch_trending_topics_sync(norm_state: Optional[str], limit: int) -> List[TrendingTopicItem]:
    if norm_state:
        sql = """
            SELECT subject, bill_count, recent_bill_count, state_code
            FROM public.rpt_bill_map_aggregate
            WHERE state_code = %s
              AND subject IS NOT NULL
              AND btrim(subject) <> ''
            ORDER BY recent_bill_count DESC, bill_count DESC
            LIMIT %s
        """
        params: tuple = (norm_state, limit)
    else:
        sql = """
            SELECT subject,
                   sum(bill_count) AS bill_count,
                   sum(recent_bill_count) AS recent_bill_count,
                   NULL AS state_code
            FROM public.rpt_bill_map_aggregate
            WHERE subject IS NOT NULL
              AND btrim(subject) <> ''
            GROUP BY subject
            ORDER BY sum(recent_bill_count) DESC, sum(bill_count) DESC
            LIMIT %s
        """
        params = (limit,)

    try:
        with _cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    except psycopg2.errors.UndefinedTable:
        logger.warning(
            "public.rpt_bill_map_aggregate not found; returning empty trending topics"
        )
        return []
    except Exception as exc:
        logger.warning(f"Trending topics query failed: {exc}")
        return []

    return [
        TrendingTopicItem(
            name=subject,
            bill_count=int(bill_count or 0),
            recent_bill_count=int(recent_bill_count or 0),
            state_code=state_code,
        )
        for (subject, bill_count, recent_bill_count, state_code) in rows
    ]


@router.get("/topics", response_model=TrendingTopicsResponse)
async def get_trending_topics(
    state: Optional[str] = Query(
        None, description="2-letter code or full state name; omit for national"
    ),
    limit: int = Query(12, ge=1, le=50, description="Max number of topics to return"),
) -> TrendingTopicsResponse:
    """
    Get trending legislative topics for the homepage trending pills.

    Reads the modeled ``public.rpt_bill_map_aggregate`` mart. The trending
    signal is ``recent_bill_count`` (bills with recent action).

    - **state** given: per-state subjects filtered by ``state_code``.
    - **state** omitted: subjects aggregated across all jurisdictions.
    """
    norm_state = normalize_state_input(state)
    cache_key = f"topics:{norm_state}:{limit}"

    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    async with _inflight(cache_key):
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached

        topics = await asyncio.to_thread(_fetch_trending_topics_sync, norm_state, limit)
        response = TrendingTopicsResponse(topics=topics, total=len(topics))
        if topics:
            _set_cached(cache_key, response)
        return response


def _fetch_trending_stats_sync() -> Dict[str, int]:
    everyorg_count = 0
    ntee_count = 0

    try:
        with _cursor() as cur:
            try:
                cur.execute("SELECT count(*) FROM bronze.bronze_everyorg_causes")
                row = cur.fetchone()
                everyorg_count = int(row[0] or 0) if row else 0
            except Exception as exc:
                logger.warning(f"EveryOrg count failed: {exc}")
                cur.connection.rollback()

            try:
                cur.execute(
                    "SELECT count(*) FROM bronze.bronze_ntee_codes WHERE cause_type = 'ntee'"
                )
                row = cur.fetchone()
                ntee_count = int(row[0] or 0) if row else 0
            except psycopg2.errors.UndefinedTable:
                cur.connection.rollback()
                try:
                    cur.execute("SELECT count(*) FROM public.tag WHERE vocabulary = 'ntee'")
                    row = cur.fetchone()
                    ntee_count = int(row[0] or 0) if row else 0
                except Exception as exc:
                    logger.warning(f"NTEE tag-mart count failed: {exc}")
                    cur.connection.rollback()
            except Exception as exc:
                logger.warning(f"NTEE count failed: {exc}")
                cur.connection.rollback()
    except Exception as exc:
        logger.warning(f"Trending stats database connection failed: {exc}")

    images_dir = Path("data/media/causes")
    images_count = (
        len(list(images_dir.glob("*_square.png"))) if images_dir.exists() else 0
    )

    return {
        "everyorg_causes": everyorg_count,
        "ntee_causes": ntee_count,
        "total_causes": everyorg_count + ntee_count,
        "generated_images": images_count,
    }


@router.get("/stats")
async def get_trending_stats():
    """Get stats about available causes."""
    cache_key = "stats"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    async with _inflight(cache_key):
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached

        payload = await asyncio.to_thread(_fetch_trending_stats_sync)
        if payload["total_causes"] > 0:
            _set_cached(cache_key, payload)
        return payload
