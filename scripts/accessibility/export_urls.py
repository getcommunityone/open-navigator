#!/usr/bin/env python3
"""
Export canonical jurisdiction homepage URLs from ``intermediate.int_jurisdiction_websites``.

Writes a JSON array for Pa11y-CI / axe batch runners (one URL per ``jurisdiction_id``,
using the same source-priority order as discovery).

Usage:
  .venv/bin/python -m scripts.accessibility.export_urls --state AL
  .venv/bin/python -m scripts.accessibility.export_urls --limit 500 --offset 1000 --batch-id shard-2
  .venv/bin/python -m scripts.accessibility.export_urls --out data/cache/accessibility/urls.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ModuleNotFoundError as exc:
    if exc.name != "psycopg2":
        raise
    print("Install psycopg2-binary: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

from scripts.accessibility._int_websites import (
    INT_JURISDICTION_WEBSITES_TABLE,
    WEBSITE_SOURCE_PRIORITY_ORDER_SQL,
)
from scripts.database.target_database_url import resolve_target_database_url

_DEFAULT_OUT = _ROOT / "data" / "cache" / "accessibility" / "urls.json"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(_ROOT / ".env")


def _resolve_database_url() -> str:
    _load_dotenv()
    url = (
        os.getenv("OPEN_NAVIGATOR_DATABASE_URL", "").strip()
        or os.getenv("NEON_DATABASE_URL_DEV", "").strip()
        or os.getenv("NEON_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
    )
    return url or resolve_target_database_url()


def fetch_url_jobs(
    *,
    state: Optional[str] = None,
    jurisdiction_id_prefix: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    clauses = [
        "jurisdiction_id IS NOT NULL",
        "website_url IS NOT NULL",
        "btrim(website_url) <> ''",
    ]
    params: List[Any] = []
    if state:
        clauses.append("state_code = %s")
        params.append(state.strip().upper()[:2])
    if jurisdiction_id_prefix:
        clauses.append("jurisdiction_id LIKE %s")
        params.append(jurisdiction_id_prefix.strip() + "%")

    where_sql = " AND ".join(clauses)
    sql = f"""
        SELECT DISTINCT ON (jurisdiction_id)
            jurisdiction_id,
            website_record_key,
            trim(website_url) AS url,
            website_source,
            state_code,
            organization_name,
            domain_name
        FROM {INT_JURISDICTION_WEBSITES_TABLE}
        WHERE {where_sql}
        ORDER BY jurisdiction_id,
            ({WEBSITE_SOURCE_PRIORITY_ORDER_SQL}),
            website_record_key
    """
    if limit is not None:
        sql += " LIMIT %s OFFSET %s"
        params.extend([int(limit), int(offset)])

    conn = psycopg2.connect(_resolve_database_url())
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return rows


def build_export_payload(
    jobs: List[Dict[str, Any]],
    *,
    batch_id: str,
) -> Dict[str, Any]:
    return {
        "batch_id": batch_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_table": INT_JURISDICTION_WEBSITES_TABLE,
        "count": len(jobs),
        "urls": jobs,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", help="Filter by state_code (e.g. AL)")
    ap.add_argument(
        "--jurisdiction-id-prefix",
        help="Filter jurisdiction_id LIKE prefix (e.g. county_, municipality_)",
    )
    ap.add_argument("--limit", type=int, help="Max jurisdictions (for sharding / Lambda)")
    ap.add_argument("--offset", type=int, default=0, help="Skip first N jurisdictions")
    ap.add_argument(
        "--batch-id",
        default="",
        help="Batch label (default: UTC timestamp)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help=f"Output JSON path (default: {_DEFAULT_OUT})",
    )
    args = ap.parse_args()

    batch_id = (args.batch_id or "").strip() or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    jobs = fetch_url_jobs(
        state=args.state,
        jurisdiction_id_prefix=args.jurisdiction_id_prefix,
        limit=args.limit,
        offset=args.offset,
    )
    payload = build_export_payload(jobs, batch_id=batch_id)

    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(jobs):,} URL(s) to {out_path} (batch_id={batch_id})")


if __name__ == "__main__":
    main()
