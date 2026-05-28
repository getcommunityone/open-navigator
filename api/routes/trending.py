"""
Trending causes/topics API endpoints.

Reads from the bronze ingestion tables landed by:
  - ingestion.everyorg.causes  -> bronze.bronze_everyorg_causes
  - ingestion.ntee.codes       -> bronze.bronze_ntee_codes

Falls back to the legacy public.cause_ntee table if the bronze migration has
not been run yet (during the Stage-2 transition).
"""
import os
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

import psycopg2
from fastapi import APIRouter, Query
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/trending", tags=["trending"])

LOCAL_DB_URL = os.getenv(
    "NEON_DATABASE_URL_DEV",
    "postgresql://postgres:password@localhost:5433/open_navigator",
)


@contextmanager
def _cursor():
    conn = psycopg2.connect(LOCAL_DB_URL)
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
    name: str
    icon: str
    category: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    popularity_rank: Optional[int] = None


class TrendingResponse(BaseModel):
    """Response with trending causes"""
    causes: List[CauseItem]
    total: int


def get_everyorg_causes(limit: int = 20) -> List[CauseItem]:
    """Load EveryOrg causes from bronze.bronze_everyorg_causes."""
    try:
        with _cursor() as cur:
            cur.execute(
                """
                SELECT cause_id, cause_name, description, icon, category, popularity_rank
                FROM bronze.bronze_everyorg_causes
                ORDER BY popularity_rank NULLS LAST, cause_name
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    except Exception as exc:
        logger.warning(f"EveryOrg causes query failed (table empty or missing?): {exc}")
        return []

    return [
        CauseItem(
            name=name,
            icon=icon or '📌',
            category=category or 'general',
            description=description or '',
            image_url=f"/images/causes/everyorg_{cause_id}_square.png",
            popularity_rank=popularity_rank,
        )
        for (cause_id, name, description, icon, category, popularity_rank) in rows
    ]


def get_ntee_causes(limit: int = 20, level: Optional[int] = None) -> List[CauseItem]:
    """Load NTEE code causes from bronze.bronze_ntee_codes (or legacy public.cause_ntee).

    Args:
        limit: max rows to return.
        level: 1 = major groups (single-letter codes), 2 = divisions (3-char codes).
    """
    # `level` maps directly to code length: A = level 1, A20 = level 2.
    bronze_where = ["cause_type = 'ntee'"]
    legacy_where: list[str] = []  # legacy public.cause_ntee has no cause_type col
    params: list = []
    if level == 1:
        bronze_where.append("length(code) = 1")
        legacy_where.append("length(code) = 1")
    elif level == 2:
        bronze_where.append("length(code) = 3")
        legacy_where.append("length(code) = 3")

    bronze_sql = f"""
        SELECT code, name, description, category
        FROM bronze.bronze_ntee_codes
        WHERE {' AND '.join(bronze_where)}
        ORDER BY length(code), code
        LIMIT %s
    """
    # Legacy table has no `name` column — use description as the display name.
    legacy_sql = f"""
        SELECT code, description AS name, description, category
        FROM public.cause_ntee
        {('WHERE ' + ' AND '.join(legacy_where)) if legacy_where else ''}
        ORDER BY length(code), code
        LIMIT %s
    """
    params.append(limit)

    rows = _query_with_legacy_fallback(
        primary_sql=bronze_sql,
        legacy_sql=legacy_sql,
        params=params,
    )
    if rows is None:
        return []

    out: List[CauseItem] = []
    for code, name, description, category in rows:
        icon = _NTEE_ICON_MAP.get((code or 'Z')[0], '📌')
        out.append(CauseItem(
            name=name or code,
            icon=icon,
            category=category or 'ntee',
            description=description or f"NTEE Code {code}",
            image_url=f"/images/causes/ntee_{code}_square.png",
            popularity_rank=None,
        ))
    return out


def _query_with_legacy_fallback(primary_sql: str, legacy_sql: str, params):
    """Try the bronze table first; fall back to the legacy public.cause_ntee.

    Returns None if both fail (so the caller can render an empty response
    instead of 500ing).
    """
    try:
        with _cursor() as cur:
            cur.execute(primary_sql, params)
            return cur.fetchall()
    except psycopg2.errors.UndefinedTable:
        logger.info("bronze.bronze_ntee_codes not found, falling back to public.cause_ntee")
    except Exception as exc:
        logger.warning(f"Primary trending query failed: {exc}")
        return None

    try:
        with _cursor() as cur:
            cur.execute(legacy_sql, params)
            return cur.fetchall()
    except Exception as exc:
        logger.warning(f"Legacy trending query failed: {exc}")
        return None


@router.get("", response_model=TrendingResponse)
async def get_trending_causes(
    source: str = Query("everyorg", description="Source: 'everyorg', 'ntee', or 'mixed'"),
    limit: int = Query(12, ge=1, le=100, description="Max number of causes to return"),
    level: Optional[int] = Query(None, description="NTEE level filter (1 or 2)")
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
    if source == "ntee":
        causes = get_ntee_causes(limit=limit, level=level)
    elif source == "mixed":
        half = limit // 2
        everyorg = get_everyorg_causes(limit=half)
        ntee = get_ntee_causes(limit=half, level=1)
        causes = []
        for i in range(max(len(everyorg), len(ntee))):
            if i < len(everyorg):
                causes.append(everyorg[i])
            if i < len(ntee):
                causes.append(ntee[i])
    else:
        causes = get_everyorg_causes(limit=limit)

    return TrendingResponse(causes=causes, total=len(causes))


@router.get("/stats")
async def get_trending_stats():
    """Get stats about available causes."""
    everyorg_count = 0
    ntee_count = 0

    try:
        with _cursor() as cur:
            cur.execute("SELECT count(*) FROM bronze.bronze_everyorg_causes")
            everyorg_count = cur.fetchone()[0]
    except Exception as exc:
        logger.warning(f"EveryOrg count failed: {exc}")

    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM bronze.bronze_ntee_codes WHERE cause_type = 'ntee'"
            )
            ntee_count = cur.fetchone()[0]
    except psycopg2.errors.UndefinedTable:
        # Stage-2 transition: bronze table not yet created, fall back. Legacy
        # public.cause_ntee has no cause_type column — all rows are NTEE.
        try:
            with _cursor() as cur:
                cur.execute("SELECT count(*) FROM public.cause_ntee")
                ntee_count = cur.fetchone()[0]
        except Exception as exc:
            logger.warning(f"NTEE legacy count failed: {exc}")
    except Exception as exc:
        logger.warning(f"NTEE count failed: {exc}")

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
