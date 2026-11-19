"""Compute and repair ``bronze.bronze_event_youtube_transcript.has_transcript`` (#470).

``has_transcript`` means "this row has caption text" (``raw_text`` and/or
``segments``). Staging already tests the text itself (#554); the flag must
still stay consistent for bronze readers that filter on it.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Optional

from loguru import logger


def compute_has_transcript(
    raw_text: Optional[str],
    segments: Any = None,
) -> bool:
    """True when the row carries usable caption text or timed segments."""
    if (raw_text or "").strip():
        return True
    if segments is None:
        return False
    if isinstance(segments, str):
        s = segments.strip()
        if not s or s in ("null", "[]", "{}"):
            return False
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return bool(s)
        segments = parsed
    if isinstance(segments, (list, tuple)):
        return len(segments) > 0
    if isinstance(segments, dict):
        return bool(segments)
    return False


_BACKFILL_SQL = """
UPDATE bronze.bronze_event_youtube_transcript
SET has_transcript = true,
    last_updated = CURRENT_TIMESTAMP
WHERE coalesce(has_transcript, false) IS NOT TRUE
  AND (
        nullif(trim(raw_text), '') IS NOT NULL
        OR (
            jsonb_typeof(segments) = 'array'
            AND jsonb_array_length(segments) > 0
        )
      )
"""

_COUNT_MISMATCH_SQL = """
SELECT count(*)::bigint
FROM bronze.bronze_event_youtube_transcript
WHERE coalesce(has_transcript, false) IS NOT TRUE
  AND (
        nullif(trim(raw_text), '') IS NOT NULL
        OR (
            jsonb_typeof(segments) = 'array'
            AND jsonb_array_length(segments) > 0
        )
      )
"""


def count_mismatched_rows(conn: Any) -> int:
    cur = conn.cursor()
    try:
        cur.execute(_COUNT_MISMATCH_SQL)
        row = cur.fetchone()
        return int(row[0] or 0)
    finally:
        cur.close()


def backfill_has_transcript(conn: Any, *, dry_run: bool = True) -> int:
    """Set ``has_transcript = true`` where caption text exists but the flag is false.

    Returns the number of rows that need (or received) the fix.
    """
    n = count_mismatched_rows(conn)
    if dry_run or n == 0:
        return n
    cur = conn.cursor()
    try:
        cur.execute(_BACKFILL_SQL)
        updated = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else n
        conn.commit()
        return int(updated)
    finally:
        cur.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill has_transcript=true where caption text exists (#470)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the UPDATE (default is dry-run count only).",
    )
    args = parser.parse_args(argv)

    from core_lib.db import resolve_target_database_url
    import psycopg2

    url = resolve_target_database_url()
    conn = psycopg2.connect(url)
    try:
        n = count_mismatched_rows(conn)
        logger.info("rows with caption text but has_transcript=false: {:,}", n)
        if not args.apply:
            logger.info("Dry run — re-run with --apply to update.")
            return 0
        updated = backfill_has_transcript(conn, dry_run=False)
        logger.success("Updated {:,} rows (has_transcript=true)", updated)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
