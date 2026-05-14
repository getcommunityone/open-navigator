#!/usr/bin/env python3
"""
Load ``unified_events.jsonl`` (from ``build_dot_unified_events.py``) into
``bronze.bronze_dot_public_events``.

Requires migration ``021_create_bronze_dot_public_events.sql`` applied.

Usage::

  .venv/bin/python scripts/datasources/dot/load_dot_unified_events_to_postgres.py \\
    --jsonl data/cache/dot_public_involvement/unified_events.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import psycopg2
    from psycopg2.extras import Json, execute_batch
except ModuleNotFoundError as exc:  # pragma: no cover
    if exc.name != "psycopg2":
        raise
    psycopg2 = None  # type: ignore[misc,assignment]

from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url

DEFAULT_JSONL = REPO_ROOT / "data" / "cache" / "dot_public_involvement" / "unified_events.jsonl"


def _parse_date_iso(s: str | None) -> date | None:
    if not s or not str(s).strip():
        return None
    raw = str(s).strip()
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parse_scraped_at(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = (raw or "").strip()
    if not s:
        return datetime.now(timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def main() -> int:
    if psycopg2 is None:
        logger.error("psycopg2 is required")
        return 1

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    args = ap.parse_args()
    path: Path = args.jsonl
    if not path.is_file():
        logger.error("JSONL not found: {}", path)
        return 1

    rows: list[tuple[Any, ...]] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.error("Line {}: {}", line_no, exc)
                return 1
            fp = (obj.get("event_fingerprint") or "").strip()
            if not fp:
                logger.error("Line {}: missing event_fingerprint", line_no)
                return 1
            state = (obj.get("state_usps") or "").strip().upper()
            if len(state) != 2:
                logger.error("Line {}: bad state_usps", line_no)
                return 1
            meeting_date = _parse_date_iso(obj.get("meeting_date"))
            scraped_at = _parse_scraped_at(obj.get("scraped_at"))
            rows.append(
                (
                    state,
                    fp,
                    (obj.get("adapter") or "").strip(),
                    (obj.get("title") or "").strip(),
                    obj.get("summary_text"),
                    (obj.get("list_page_url") or "").strip(),
                    (obj.get("detail_url") or "").strip() or None,
                    meeting_date,
                    obj.get("meeting_date_raw"),
                    Json(obj.get("collateral") or []),
                    Json(obj),
                    scraped_at,
                )
            )

    db_url = resolve_database_url()
    sql = """
        INSERT INTO bronze.bronze_dot_public_events (
            state_usps, event_fingerprint, adapter, title, summary_text,
            list_page_url, detail_url, meeting_date, meeting_date_raw,
            collateral, raw_record, scraped_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (event_fingerprint) DO UPDATE SET
            adapter = EXCLUDED.adapter,
            title = EXCLUDED.title,
            summary_text = EXCLUDED.summary_text,
            list_page_url = EXCLUDED.list_page_url,
            detail_url = EXCLUDED.detail_url,
            meeting_date = EXCLUDED.meeting_date,
            meeting_date_raw = EXCLUDED.meeting_date_raw,
            collateral = EXCLUDED.collateral,
            raw_record = EXCLUDED.raw_record,
            scraped_at = EXCLUDED.scraped_at
    """
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            execute_batch(cur, sql, rows, page_size=500)
        conn.commit()
    finally:
        conn.close()

    logger.info("Upserted {} rows into bronze.bronze_dot_public_events", len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
