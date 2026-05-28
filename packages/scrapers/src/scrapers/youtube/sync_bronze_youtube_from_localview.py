#!/usr/bin/env python3
"""
Sync bronze.bronze_events_youtube from LocalView bronze + optional channel map.

⚠️ DEPRECATION NOTICE:
This in-place UPDATE has been superseded by the dbt model
``int_youtube__events`` (dbt_project/models/intermediate/int_youtube__events.sql),
which derives the same LocalView-enriched geography + channel_id as a SELECT on
``stg_youtube__event`` instead of mutating the bronze landing table. Read enriched
YouTube events from ``intermediate.int_youtube__events`` rather than re-running this
script. Kept for now only as an operational fallback; remove once consumers point
at the model.

After ``bronze.bronze_events_localview`` is refreshed (e.g. ``load_localview_to_postgres.py``),
run this to push matching geography and channel identifiers onto existing YouTube rows
where ``y.video_id = lv.datasource_id`` (LocalView rows use ``datasource = 'localview'``).

Updates (when the join matches and the source side has non-blank values):

1. **From ``bronze.bronze_events_localview``:** ``jurisdiction_name``, ``jurisdiction_type``,
   ``city``, ``state_code``, ``state``, ``meeting_type`` — LocalView values win when present.

2. **From ``intermediate.int_localview_youtube_video_channels``** (if the table exists):
   ``channel_id``, ``channel_url`` (canonical ``https://www.youtube.com/channel/{id}`` when URL empty).

For ``jurisdiction_id`` / richer joins to ``int_jurisdictions``, use dbt +:

  ``packages/scrapers/src/scrapers/youtube/link_youtube_bronze_from_localview_apply.sql``

Examples::

  python packages/scrapers/src/scrapers/youtube/sync_bronze_youtube_from_localview.py --dry-run
  python packages/scrapers/src/scrapers/youtube/sync_bronze_youtube_from_localview.py --states AL,GA
"""

from __future__ import annotations

import argparse
import os

import psycopg2
from dotenv import load_dotenv
from loguru import logger


def _database_url() -> str:
    load_dotenv()
    return (
        (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
        or (os.getenv("NEON_DATABASE_URL_DEV") or "").strip()
        or (os.getenv("NEON_DATABASE_URL") or "").strip()
        or (os.getenv("DATABASE_URL") or "").strip()
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def _mapping_table_exists(cur) -> bool:
    cur.execute(
        """
        SELECT EXISTS(
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'intermediate'
              AND table_name = 'int_localview_youtube_video_channels'
        )
        """
    )
    return bool(cur.fetchone()[0])


def sync_from_localview(conn, *, states: list[str] | None, dry_run: bool) -> tuple[int, int]:
    """Returns (rows_touched_jurisdiction, rows_touched_channel)."""
    cur = conn.cursor()
    state_clause = ""
    params: tuple = ()
    if states:
        state_clause = " AND lv.state_code = ANY(%s)"
        params = (states,)

    sql_lv = f"""
        UPDATE bronze.bronze_events_youtube AS y
        SET
            jurisdiction_name = COALESCE(NULLIF(BTRIM(lv.jurisdiction_name), ''), y.jurisdiction_name),
            jurisdiction_type = COALESCE(NULLIF(BTRIM(lv.jurisdiction_type), ''), y.jurisdiction_type),
            city = COALESCE(NULLIF(BTRIM(lv.city), ''), NULLIF(BTRIM(lv.city_name), ''), y.city),
            state_code = COALESCE(NULLIF(BTRIM(lv.state_code), ''), y.state_code),
            state = COALESCE(NULLIF(BTRIM(lv.state), ''), y.state),
            meeting_type = COALESCE(NULLIF(BTRIM(lv.meeting_type), ''), y.meeting_type),
            last_updated = CURRENT_TIMESTAMP
        FROM bronze.bronze_events_localview AS lv
        WHERE lv.datasource_id = y.video_id
          AND lv.datasource = 'localview'
          {state_clause}
          AND (
              COALESCE(NULLIF(BTRIM(lv.jurisdiction_name), ''), '') <> ''
              OR COALESCE(NULLIF(BTRIM(lv.state_code), ''), '') <> ''
              OR COALESCE(NULLIF(BTRIM(lv.state), ''), '') <> ''
          )
    """
    if dry_run:
        q = """
        SELECT COUNT(*) FROM bronze.bronze_events_youtube y
        INNER JOIN bronze.bronze_events_localview lv
          ON lv.datasource_id = y.video_id AND lv.datasource = 'localview'
        WHERE (
            COALESCE(NULLIF(BTRIM(lv.jurisdiction_name), ''), '') <> ''
            OR COALESCE(NULLIF(BTRIM(lv.state_code), ''), '') <> ''
            OR COALESCE(NULLIF(BTRIM(lv.state), ''), '') <> ''
        )
        """
        if states:
            q += " AND lv.state_code = ANY(%s)"
            cur.execute(q, (states,))
        else:
            cur.execute(q)
        n_lv = int(cur.fetchone()[0])
        logger.info("[dry-run] rows eligible for LocalView jurisdiction sync: {}", n_lv)
        cur.close()
        return n_lv, 0

    cur.execute(sql_lv, params if params else None)
    n_lv = cur.rowcount
    logger.success("LocalView geography sync: {} row(s) updated", n_lv)

    n_map = 0
    if _mapping_table_exists(cur):
        state_clause_y = ""
        params_map: tuple = ()
        if states:
            state_clause_y = " AND y.state_code = ANY(%s)"
            params_map = (states,)
        sql_map = f"""
            UPDATE bronze.bronze_events_youtube AS y
            SET
                channel_id = COALESCE(NULLIF(BTRIM(m.channel_id), ''), y.channel_id),
                channel_url = COALESCE(
                    NULLIF(BTRIM(y.channel_url), ''),
                    'https://www.youtube.com/channel/' || NULLIF(BTRIM(m.channel_id), '')
                ),
                last_updated = CURRENT_TIMESTAMP
            FROM intermediate.int_localview_youtube_video_channels AS m
            WHERE m.video_id = y.video_id
              AND NULLIF(BTRIM(m.channel_id), '') IS NOT NULL
              {state_clause_y}
        """
        cur.execute(sql_map, params_map if params_map else None)
        n_map = cur.rowcount
        logger.success("int_localview_youtube_video_channels sync: {} row(s) updated", n_map)
    else:
        logger.warning(
            "Skipped channel_id sync: intermediate.int_localview_youtube_video_channels "
            "not found (run LocalView load / backfill_localview_youtube_channel_map.py)."
        )

    cur.close()
    return int(n_lv), int(n_map)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--states", type=str, help="Comma-separated state codes (filter on LocalView state_code)")
    p.add_argument("--dry-run", action="store_true", help="Count eligible rows only; no UPDATE")
    args = p.parse_args()

    states = [s.strip().upper() for s in args.states.split(",") if s.strip()] if args.states else None
    url = _database_url()
    logger.info("Database: {}", url.split("@")[-1] if "@" in url else url)

    conn = psycopg2.connect(url)
    try:
        conn.autocommit = False
        n_lv, n_map = sync_from_localview(conn, states=states, dry_run=args.dry_run)
        if not args.dry_run:
            conn.commit()
            logger.info("Committed. jurisdiction pass={}, channel map pass={}", n_lv, n_map)
        return 0
    except Exception as e:
        conn.rollback()
        logger.exception("sync_bronze_youtube_from_localview failed: {}", e)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
