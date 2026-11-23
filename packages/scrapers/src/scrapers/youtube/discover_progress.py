"""Record each jurisdiction a Discover run tries, so the dashboard's Last activity moves during a run (#770).

``channel_checked_at`` on the two scraped-jurisdiction tables is the last time a Discover run tried that
jurisdiction: searched for its YouTube channel or loaded its channel's videos, whatever came of it.
``discovered_at`` keeps its own meaning (when the channel was found) and is never touched here.

A stamp that fails logs a warning and returns; it never stops a run.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

COUNTIES_TABLE = "bronze.bronze_jurisdictions_counties_scraped"
MUNICIPALITIES_TABLE = "bronze.bronze_jurisdictions_municipalities_scraped"
SCRAPED_TABLES = (COUNTIES_TABLE, MUNICIPALITIES_TABLE)

_COLUMN_READY: set[str] = set()


def ensure_channel_checked_column(conn: Any) -> None:
    """Add ``channel_checked_at`` to whichever scraped table lacks it (once per process)."""
    if _COLUMN_READY.issuperset(SCRAPED_TABLES):
        return
    from scrapers.youtube.schema_guard import set_local_lock_timeout

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT table_schema || '.' || table_name
            FROM information_schema.columns
            WHERE table_schema = 'bronze'
              AND table_name IN ('bronze_jurisdictions_counties_scraped',
                                 'bronze_jurisdictions_municipalities_scraped')
              AND column_name = 'channel_checked_at'
            """
        )
        have = {str(r[0]) for r in cur.fetchall()}
        for table in SCRAPED_TABLES:
            if table not in have:
                set_local_lock_timeout(cur)
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS channel_checked_at TIMESTAMPTZ"
                )
        conn.commit()
        _COLUMN_READY.update(SCRAPED_TABLES)
    finally:
        cur.close()


def stamp_channel_checked(conn: Any, *, state_code: str, geoid: str) -> bool:
    """Stamp the county's scraped row; True when a row was updated."""
    st, gid = (state_code or "").strip().upper(), (geoid or "").strip()
    if not st or not gid:
        return False
    try:
        ensure_channel_checked_column(conn)
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
                UPDATE {COUNTIES_TABLE}
                SET channel_checked_at = NOW()
                WHERE usps = %s AND geoid = %s
                """,
                (st, gid),
            )
            updated = cur.rowcount > 0
        finally:
            cur.close()
        conn.commit()
        return updated
    except Exception as exc:  # noqa: BLE001 - progress bookkeeping never stops a run
        _rollback(conn)
        logger.warning("channel_checked_at not stamped state={} geoid={}: {}", st, gid, exc)
        return False


def stamp_channel_checked_for_jurisdiction(conn: Any, jurisdiction_id: str) -> int:
    """Stamp the jurisdiction's scraped row in either table (matched through int_jurisdictions)."""
    jid = (jurisdiction_id or "").strip()
    if not jid:
        return 0
    try:
        ensure_channel_checked_column(conn)
        updated = 0
        cur = conn.cursor()
        try:
            for table in SCRAPED_TABLES:
                cur.execute(
                    f"""
                    UPDATE {table} s
                    SET channel_checked_at = NOW()
                    FROM intermediate.int_jurisdictions j
                    WHERE j.jurisdiction_id = %s
                      AND s.geoid = j.geoid
                      AND s.usps = j.state_code
                    """,
                    (jid,),
                )
                updated += max(int(cur.rowcount or 0), 0)
        finally:
            cur.close()
        conn.commit()
        return updated
    except Exception as exc:  # noqa: BLE001 - progress bookkeeping never stops a run
        _rollback(conn)
        logger.warning("channel_checked_at not stamped jurisdiction={}: {}", jid, exc)
        return 0


def _rollback(conn: Any) -> None:
    try:
        conn.rollback()
    except Exception:  # noqa: BLE001 - the connection may already be gone
        pass
