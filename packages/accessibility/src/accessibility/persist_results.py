#!/usr/bin/env python3
"""
Load Pa11y-CI or axe-core NDJSON/JSON results into ``bronze.bronze_jurisdiction_website_accessibility``.

Usage:
  .venv/bin/python -m accessibility.persist_results --ensure-ddl
  .venv/bin/python -m accessibility.persist_results \\
      --input data/cache/accessibility/results-axe.ndjson --scanner axe
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

_ROOT = Path(__file__).resolve().parents[4]
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

from accessibility._int_websites import BRONZE_ACCESSIBILITY_TABLE
from core_lib.db import resolve_target_database_url

_DDL_PATH = Path(__file__).resolve().parent / "sql" / "bronze_jurisdiction_website_accessibility.sql"

INSERT_SQL = f"""
    INSERT INTO {BRONZE_ACCESSIBILITY_TABLE} (
        scan_key, batch_id, scanner, jurisdiction_id, website_record_key,
        website_url, website_source, state_code, organization_name,
        scanned_at, status, http_status, final_url, page_title,
        violation_count, pass_count, incomplete_count,
        scan_duration_ms, error_message, results
    ) VALUES (
        %(scan_key)s, %(batch_id)s, %(scanner)s, %(jurisdiction_id)s, %(website_record_key)s,
        %(website_url)s, %(website_source)s, %(state_code)s, %(organization_name)s,
        %(scanned_at)s, %(status)s, %(http_status)s, %(final_url)s, %(page_title)s,
        %(violation_count)s, %(pass_count)s, %(incomplete_count)s,
        %(scan_duration_ms)s, %(error_message)s, %(results)s
    )
    ON CONFLICT (scan_key) DO UPDATE SET
        status = EXCLUDED.status,
        http_status = EXCLUDED.http_status,
        final_url = EXCLUDED.final_url,
        page_title = EXCLUDED.page_title,
        violation_count = EXCLUDED.violation_count,
        pass_count = EXCLUDED.pass_count,
        incomplete_count = EXCLUDED.incomplete_count,
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


def _resolve_database_url() -> str:
    _load_dotenv()
    url = (
        os.getenv("OPEN_NAVIGATOR_DATABASE_URL", "").strip()
        or os.getenv("NEON_DATABASE_URL_DEV", "").strip()
        or os.getenv("NEON_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
    )
    return url or resolve_target_database_url()


def ensure_ddl(conn) -> None:
    ddl = _DDL_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


def _scan_key(batch_id: str, scanner: str, jurisdiction_id: str, url: str) -> str:
    raw = f"{batch_id}|{scanner}|{jurisdiction_id}|{url}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _flatten_pa11y_ci_results_url_map(url_to_items: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Turn Pa11y-CI `--json` `{ "https://…": [ issue | error-ish ] }` into persist-friendly rows."""
    out: List[Dict[str, Any]] = []
    for page_url, raw in url_to_items.items():
        url = str(page_url or "").strip()
        if not url or not isinstance(raw, list):
            continue

        issues: List[Any] = []
        err_msg: Optional[str] = None
        is_error = False
        for item in raw:
            if isinstance(item, dict) and any(
                k in item for k in ("type", "code", "runner", "typeCode", "elements")
            ):
                issues.append(item)
            elif isinstance(item, dict) and "message" in item and len(raw) == 1:
                is_error = True
                err_msg = str(item.get("message") or "")
            elif isinstance(item, str):
                is_error = True
                err_msg = item

        rec: Dict[str, Any] = {"url": url, "issues": issues}
        if is_error and err_msg:
            rec["error"] = err_msg
            rec["isError"] = True
        out.append(rec)
    return out


def _meta_from_record(rec: Dict[str, Any]) -> Dict[str, Optional[str]]:
    meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else rec
    return {
        "jurisdiction_id": str(meta.get("jurisdiction_id") or rec.get("jurisdiction_id") or "").strip(),
        "website_record_key": (meta.get("website_record_key") or rec.get("website_record_key")),
        "website_url": str(meta.get("url") or meta.get("website_url") or rec.get("url") or "").strip(),
        "website_source": meta.get("website_source") or rec.get("website_source"),
        "state_code": meta.get("state_code") or rec.get("state_code"),
        "organization_name": meta.get("organization_name") or rec.get("organization_name"),
    }


def normalize_axe_record(rec: Dict[str, Any], *, batch_id: str, scanner: str) -> Dict[str, Any]:
    meta = _meta_from_record(rec)
    jid = meta["jurisdiction_id"] or "unknown"
    url = meta["website_url"] or rec.get("final_url") or rec.get("url") or ""
    axe = rec.get("axe") if isinstance(rec.get("axe"), dict) else rec
    violations = axe.get("violations") if isinstance(axe.get("violations"), list) else []
    passes = axe.get("passes") if isinstance(axe.get("passes"), list) else []
    incomplete = axe.get("incomplete") if isinstance(axe.get("incomplete"), list) else []
    status = str(rec.get("status") or ("ok" if rec.get("error") is None else "error"))
    scanned_at = rec.get("scanned_at") or datetime.now(timezone.utc).isoformat()
    return {
        "scan_key": _scan_key(batch_id, scanner, jid, url),
        "batch_id": batch_id,
        "scanner": scanner,
        "jurisdiction_id": jid,
        "website_record_key": meta.get("website_record_key"),
        "website_url": url,
        "website_source": meta.get("website_source"),
        "state_code": meta.get("state_code"),
        "organization_name": meta.get("organization_name"),
        "scanned_at": scanned_at,
        "status": status,
        "http_status": rec.get("http_status"),
        "final_url": rec.get("final_url"),
        "page_title": rec.get("page_title"),
        "violation_count": len(violations),
        "pass_count": len(passes),
        "incomplete_count": len(incomplete),
        "scan_duration_ms": rec.get("scan_duration_ms"),
        "error_message": rec.get("error"),
        "results": Json(
            {
                "engine": "axe",
                "violations": violations,
                "passes": passes,
                "incomplete": incomplete,
                "raw_summary": axe.get("testEngine"),
            }
        ),
    }


def normalize_pa11y_record(
    rec: Dict[str, Any],
    *,
    batch_id: str,
    scanner: str,
    meta_by_url: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    url = str(rec.get("url") or "").strip()
    meta = meta_by_url.get(url) or _meta_from_record(rec)
    jid = str(meta.get("jurisdiction_id") or "unknown").strip()
    issues = rec.get("issues") if isinstance(rec.get("issues"), list) else []
    status = "ok" if rec.get("isError") is not True and not rec.get("error") else "error"
    scanned_at = datetime.now(timezone.utc).isoformat()
    return {
        "scan_key": _scan_key(batch_id, scanner, jid, url),
        "batch_id": batch_id,
        "scanner": scanner,
        "jurisdiction_id": jid,
        "website_record_key": meta.get("website_record_key"),
        "website_url": url,
        "website_source": meta.get("website_source"),
        "state_code": meta.get("state_code"),
        "organization_name": meta.get("organization_name"),
        "scanned_at": scanned_at,
        "status": status,
        "http_status": None,
        "final_url": url,
        "page_title": None,
        "violation_count": len(issues),
        "pass_count": 0,
        "incomplete_count": 0,
        "scan_duration_ms": None,
        "error_message": rec.get("error"),
        "results": Json({"engine": "pa11y", "issues": issues}),
    }


def _iter_ndjson(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _load_input(path: Path) -> tuple[str, List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Return (batch_id, records, meta_by_url)."""
    text = path.read_text(encoding="utf-8").strip()
    meta_by_url: Dict[str, Dict[str, Any]] = {}
    batch_id = ""

    if path.suffix == ".ndjson":
        records = list(_iter_ndjson(path))
    else:
        data = json.loads(text)
        if isinstance(data, dict):
            batch_id = str(data.get("batch_id") or "")
            for job in data.get("urls") or []:
                if isinstance(job, dict) and job.get("url"):
                    meta_by_url[str(job["url"])] = job
            if "results" in data:
                r = data["results"]
                # Merged loader output: [{ "url": "...", "issues": [...] }, ...]
                if isinstance(r, list):
                    records = r
                # Raw pa11y-ci --json envelope { total, passes, errors, results: { … } }
                elif isinstance(r, dict):
                    inner = (
                        r.get("results") if isinstance(r.get("results"), dict) else r
                    )
                    records = _flatten_pa11y_ci_results_url_map(inner)
                else:
                    records = []
            elif "urls" in data:
                records = data.get("urls") or []
        elif isinstance(data, list):
            records = data
        else:
            records = [data]

    sidecar = path.with_suffix(".meta.json")
    if sidecar.is_file():
        meta_payload = json.loads(sidecar.read_text(encoding="utf-8"))
        batch_id = batch_id or str(meta_payload.get("batch_id") or "")
        for job in meta_payload.get("urls") or []:
            if isinstance(job, dict) and job.get("url"):
                meta_by_url[str(job["url"])] = job

    return batch_id, records, meta_by_url


def normalize_records(
    records: List[Dict[str, Any]],
    *,
    scanner: str,
    batch_id: str,
    meta_by_url: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if scanner == "axe":
            row = normalize_axe_record(rec, batch_id=batch_id, scanner=scanner)
        else:
            row = normalize_pa11y_record(
                rec, batch_id=batch_id, scanner=scanner, meta_by_url=meta_by_url
            )
        if row["jurisdiction_id"] and row["website_url"]:
            out.append(row)
    return out


def persist_rows(rows: List[Dict[str, Any]], *, run_ddl: bool) -> int:
    if not rows:
        return 0
    conn = psycopg2.connect(_resolve_database_url())
    try:
        if run_ddl:
            ensure_ddl(conn)
        with conn.cursor() as cur:
            execute_batch(cur, INSERT_SQL, rows, page_size=200)
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True, help="NDJSON lines or Pa11y JSON array")
    ap.add_argument("--scanner", choices=("axe", "pa11y"), required=True)
    ap.add_argument("--batch-id", default="", help="Override batch_id from file")
    ap.add_argument("--ensure-ddl", action="store_true", help="Create bronze table if missing")
    args = ap.parse_args()

    batch_id, records, meta_by_url = _load_input(args.input)
    batch_id = (args.batch_id or batch_id or "").strip() or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    rows = normalize_records(records, scanner=args.scanner, batch_id=batch_id, meta_by_url=meta_by_url)
    n = persist_rows(rows, run_ddl=args.ensure_ddl)
    print(f"Upserted {n:,} row(s) into {BRONZE_ACCESSIBILITY_TABLE} (batch_id={batch_id})")


if __name__ == "__main__":
    main()
