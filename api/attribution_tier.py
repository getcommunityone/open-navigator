"""Read ``meeting_passage_speaker`` when the served copy may predate ``attribution_tier`` (#1389).

The API hides a speaker whose attribution is low (``attribution_tier <> 'low'``). A serving database published before
the column existed (an older Neon copy, a deploy that reached production before the republish) has no such column, and
the query would fail with a 500. These helpers retry that one query without the filter, treat every row as not low,
and log a warning, so a deploy-order mistake costs nothing but a log line.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from loguru import logger

TIER_FILTER = "AND s.attribution_tier <> 'low'"
"""The clause every reader of meeting_passage_speaker carries, alias ``s``; ``without_tier_filter`` removes it."""


def without_tier_filter(sql: str) -> str:
    """``sql`` with the attribution-tier clause removed (the older served schema)."""
    return sql.replace(TIER_FILTER, "")


def _missing_tier(exc: BaseException) -> bool:
    return isinstance(exc, asyncpg.exceptions.UndefinedColumnError) and "attribution_tier" in str(exc)


async def _retry(conn: Any, method: str, sql: str, args: tuple[Any, ...], what: str) -> Any:
    try:
        return await getattr(conn, method)(sql, *args)
    except asyncpg.exceptions.UndefinedColumnError as exc:
        if not _missing_tier(exc) or TIER_FILTER not in sql:
            raise
        logger.warning(
            "{}: attribution_tier missing from the served schema ({}); treating every speaker as not low. "
            "Republish meeting_passage_speaker.",
            what,
            exc,
        )
        return await getattr(conn, method)(without_tier_filter(sql), *args)


async def fetch_tier_aware(conn: Any, sql: str, *args: Any, what: str = "speaker query") -> list[Any]:
    """``conn.fetch`` that survives a served schema without ``attribution_tier``."""
    return await _retry(conn, "fetch", sql, args, what)


async def fetchrow_tier_aware(conn: Any, sql: str, *args: Any, what: str = "speaker query") -> Any:
    """``conn.fetchrow`` that survives a served schema without ``attribution_tier``."""
    return await _retry(conn, "fetchrow", sql, args, what)
