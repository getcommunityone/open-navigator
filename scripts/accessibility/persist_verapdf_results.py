#!/usr/bin/env python3
"""
Load veraPDF NDJSON into ``bronze.bronze_jurisdiction_pdf_verapdf``.

Usage:
  .venv/bin/python -m scripts.accessibility.persist_verapdf_results --ensure-ddl \\
      --input data/cache/accessibility/verapdf-<batch>.ndjson
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import psycopg2
    from psycopg2.extras import Json, execute_batch
except ModuleNotFoundError as exc:
    if exc.name != "psycopg2":
        raise
    print("Install psycopg2-binary: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

from scripts.database.target_database_url import resolve_target_database_url

TABLE = "bronze.bronze_jurisdiction_pdf_verapdf"
_DDL = Path(__file__).resolve().parent / "sql" / "bronze_jurisdiction_pdf_verapdf.sql"

INSERT_SQL = f"""
    INSERT INTO {TABLE} (
        scan_key, batch_id, jurisdiction_id, pdf_url, homepage_url,
        website_record_key, website_source, state_code, organization_name,
        profile_flavour, scanned_at, status, is_compliant,
        failed_rules, failed_checks, passed_rules, passed_checks,
        pdf_bytes, scan_duration_ms, error_message, results
    ) VALUES (
        %(scan_key)s, %(batch_id)s, %(jurisdiction_id)s, %(pdf_url)s, %(homepage_url)s,
        %(website_record_key)s, %(website_source)s, %(state_code)s, %(organization_name)s,
        %(profile_flavour)s, %(scanned_at)s, %(status)s, %(is_compliant)s,
        %(failed_rules)s, %(failed_checks)s, %(passed_rules)s, %(passed_checks)s,
        %(pdf_bytes)s, %(scan_duration_ms)s, %(error_message)s, %(results)s
    )
    ON CONFLICT (scan_key) DO UPDATE SET
        status = EXCLUDED.status,
        is_compliant = EXCLUDED.is_compliant,
        failed_rules = EXCLUDED.failed_rules,
        failed_checks = EXCLUDED.failed_checks,
        passed_rules = EXCLUDED.passed_rules,
        passed_checks = EXCLUDED.passed_checks,
        pdf_bytes = EXCLUDED.pdf_bytes,
        scan_duration_ms = EXCLUDED.scan_duration_ms,
        error_message = EXCLUDED.error_message,
        results = EXCLUDED.results,
        scanned_at = EXCLUDED.scanned_at
"""


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(_ROOT / ".env")


def _db_url() -> str:
    _load_dotenv()
    url = (
        os.getenv("OPEN_NAVIGATOR_DATABASE_URL", "").strip()
        or os.getenv("NEON_DATABASE_URL_DEV", "").strip()
        or os.getenv("NEON_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
    )
    return url or resolve_target_database_url()


def ensure_ddl(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_DDL.read_text(encoding="utf-8"))
    conn.commit()


def _scan_key(batch_id: str, jid: str, pdf_url: str, flavour: str) -> str:
    raw = f"{batch_id}|{jid}|{pdf_url}|{flavour}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _iter_ndjson(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def normalize_row(rec: Dict[str, Any]) -> Dict[str, Any]:
    meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else rec
    validation = rec.get("validation") if isinstance(rec.get("validation"), dict) else {}
    batch_id = str(rec.get("batch_id") or "unknown")
    jid = str(rec.get("jurisdiction_id") or meta.get("jurisdiction_id") or "unknown")
    pdf_url = str(rec.get("pdf_url") or meta.get("pdf_url") or "")
    flavour = str(rec.get("profile_flavour") or "ua1")
    err = rec.get("error")
    return {
        "scan_key": _scan_key(batch_id, jid, pdf_url, flavour),
        "batch_id": batch_id,
        "jurisdiction_id": jid,
        "pdf_url": pdf_url,
        "homepage_url": meta.get("homepage_url") or meta.get("url"),
        "website_record_key": meta.get("website_record_key"),
        "website_source": meta.get("website_source"),
        "state_code": meta.get("state_code"),
        "organization_name": meta.get("organization_name"),
        "profile_flavour": flavour,
        "scanned_at": rec.get("scanned_at") or datetime.now(timezone.utc).isoformat(),
        "status": rec.get("status") or "unknown",
        "is_compliant": validation.get("is_compliant"),
        "failed_rules": validation.get("failed_rules"),
        "failed_checks": validation.get("failed_checks"),
        "passed_rules": validation.get("passed_rules"),
        "passed_checks": validation.get("passed_checks"),
        "pdf_bytes": rec.get("pdf_bytes"),
        "scan_duration_ms": rec.get("scan_duration_ms"),
        "error_message": str(err) if err else None,
        "results": Json(
            {
                "validation": validation,
                "verapdf_report": rec.get("verapdf_report"),
                "local_path": rec.get("local_path"),
                "discover_status": meta.get("discover_status"),
            }
        ),
    }


def persist(rows: List[Dict[str, Any]], *, ensure_ddl: bool) -> int:
    rows = [r for r in rows if r.get("pdf_url")]
    if not rows:
        return 0
    conn = psycopg2.connect(_db_url())
    try:
        if ensure_ddl:
            ensure_ddl(conn)
        with conn.cursor() as cur:
            execute_batch(cur, INSERT_SQL, rows, page_size=100)
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--ensure-ddl", action="store_true")
    args = ap.parse_args()
    rows = [normalize_row(r) for r in _iter_ndjson(args.input)]
    n = persist(rows, ensure_ddl=args.ensure_ddl)
    print(f"Upserted {n:,} row(s) into {TABLE}")


if __name__ == "__main__":
    main()
