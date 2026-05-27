#!/usr/bin/env python3
"""
Load Lighthouse NDJSON runs into ``bronze.bronze_jurisdiction_website_lighthouse``.

Pairs with axe rows on (``batch_id``, ``jurisdiction_id``, ``website_url``) — use the same ``batch_id``
from ``export_urls`` for both engines. Optional merge view: ``public.v_jurisdiction_audits_axe_lighthouse``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

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

from scripts.accessibility._int_websites import BRONZE_LIGHTHOUSE_TABLE
from scripts.database.target_database_url import resolve_target_database_url

_DDL_PATH = Path(__file__).resolve().parent / "sql" / "bronze_jurisdiction_website_lighthouse.sql"

INSERT_SQL = f"""
    INSERT INTO {BRONZE_LIGHTHOUSE_TABLE} (
        scan_key, batch_id, jurisdiction_id, website_record_key,
        website_url, website_source, state_code, organization_name,
        scanned_at, status, final_url, lighthouse_version,
        score_accessibility, score_performance, score_best_practices,
        scan_duration_ms, error_message, results
    ) VALUES (
        %(scan_key)s, %(batch_id)s, %(jurisdiction_id)s, %(website_record_key)s,
        %(website_url)s, %(website_source)s, %(state_code)s, %(organization_name)s,
        %(scanned_at)s, %(status)s, %(final_url)s, %(lighthouse_version)s,
        %(score_accessibility)s, %(score_performance)s, %(score_best_practices)s,
        %(scan_duration_ms)s, %(error_message)s, %(results)s
    )
    ON CONFLICT (scan_key) DO UPDATE SET
        status = EXCLUDED.status,
        final_url = EXCLUDED.final_url,
        lighthouse_version = EXCLUDED.lighthouse_version,
        score_accessibility = EXCLUDED.score_accessibility,
        score_performance = EXCLUDED.score_performance,
        score_best_practices = EXCLUDED.score_best_practices,
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


def _scan_key(batch_id: str, jurisdiction_id: str, url: str) -> str:
    raw = f"{batch_id}|lighthouse|{jurisdiction_id}|{url}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _meta_from_record(rec: Dict[str, Any]) -> Dict[str, Optional[str]]:
    meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else rec
    return {
        "jurisdiction_id": str(meta.get("jurisdiction_id") or rec.get("jurisdiction_id") or "").strip(),
        "website_record_key": meta.get("website_record_key") or rec.get("website_record_key"),
        "website_url": str(meta.get("url") or meta.get("website_url") or rec.get("url") or "").strip(),
        "website_source": meta.get("website_source") or rec.get("website_source"),
        "state_code": meta.get("state_code") or rec.get("state_code"),
        "organization_name": meta.get("organization_name") or rec.get("organization_name"),
    }


def _score_to_int100(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(round(float(val) * 100))
    except (TypeError, ValueError):
        return None


def normalize_lighthouse_record(rec: Dict[str, Any], *, batch_id: str) -> Dict[str, Any]:
    meta = _meta_from_record(rec)
    jid = meta["jurisdiction_id"] or "unknown"
    url = meta["website_url"] or str(rec.get("final_url") or rec.get("url") or "")
    lhr = rec.get("lhr") if isinstance(rec.get("lhr"), dict) else None
    cats = lhr.get("categories") if isinstance(lhr, dict) else None
    scores = rec.get("scores") if isinstance(rec.get("scores"), dict) else {}

    def _cat(name: str, key: str) -> Optional[int]:
        if name in scores:
            v = scores.get(name)
            if v is not None and isinstance(v, (int, float)):
                return int(round(float(v)))
            if v is not None:
                try:
                    return int(round(float(v)))
                except (TypeError, ValueError):
                    pass
        if isinstance(cats, dict) and isinstance(cats.get(key), dict):
            return _score_to_int100(cats[key].get("score"))
        return None

    acc = _cat("accessibility", "accessibility")
    perf = _cat("performance", "performance")
    bp = _cat("best-practices", "best-practices")

    status = str(rec.get("status") or ("ok" if rec.get("error") is None else "error"))
    scanned_at = rec.get("scanned_at") or datetime.now(timezone.utc).isoformat()
    final_url = rec.get("final_url")
    if isinstance(lhr, dict) and not final_url:
        final_url = lhr.get("finalUrl") or lhr.get("finalDisplayedUrl")

    lv = rec.get("lighthouse_version")
    if not lv and isinstance(lhr, dict):
        lv = lhr.get("lighthouseVersion")

    return {
        "scan_key": _scan_key(batch_id, jid, url),
        "batch_id": batch_id,
        "jurisdiction_id": jid,
        "website_record_key": meta.get("website_record_key"),
        "website_url": url,
        "website_source": meta.get("website_source"),
        "state_code": meta.get("state_code"),
        "organization_name": meta.get("organization_name"),
        "scanned_at": scanned_at,
        "status": status,
        "final_url": final_url,
        "lighthouse_version": str(lv) if lv else None,
        "score_accessibility": acc,
        "score_performance": perf,
        "score_best_practices": bp,
        "scan_duration_ms": rec.get("scan_duration_ms"),
        "error_message": rec.get("error"),
        "results": Json({"engine": "lighthouse", "lhr": lhr, "scores": scores}),
    }


def _iter_ndjson(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _load_input(path: Path) -> tuple[str, List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    meta_by_url: Dict[str, Dict[str, Any]] = {}
    batch_id = ""
    records = list(_iter_ndjson(path))

    for sidecar in (path.parent / "urls.meta.json", path.with_suffix(".meta.json")):
        if not sidecar.is_file():
            continue
        meta_payload = json.loads(sidecar.read_text(encoding="utf-8"))
        batch_id = batch_id or str(meta_payload.get("batch_id") or "")
        for job in meta_payload.get("urls") or []:
            if isinstance(job, dict) and job.get("url"):
                meta_by_url[str(job["url"])] = job

    for rec in records:
        if isinstance(rec, dict) and rec.get("batch_id"):
            batch_id = batch_id or str(rec.get("batch_id") or "").strip()
            break

    for rec in records:
        if not isinstance(rec.get("meta"), dict):
            continue
        m = rec["meta"]
        u = str(m.get("url") or "").strip()
        if u:
            meta_by_url.setdefault(u, m)

    return batch_id, records, meta_by_url


def enrich_meta(rec: Dict[str, Any], meta_by_url: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Attach export manifest meta when the row only has top-level url."""
    if isinstance(rec.get("meta"), dict):
        return rec
    u = str(rec.get("url") or "").strip()
    meta = meta_by_url.get(u)
    if meta:
        out = {**rec, "meta": meta}
        return out
    return rec


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
    ap.add_argument("--input", type=Path, required=True, help="Lighthouse NDJSON (one object per line)")
    ap.add_argument("--batch-id", default="", help="Override batch_id from urls.meta.json sidecar")
    ap.add_argument("--ensure-ddl", action="store_true", help="Apply bronze table + merge view DDL")
    args = ap.parse_args()

    batch_id, records, meta_by_url = _load_input(args.input)
    batch_id = (args.batch_id or batch_id or "").strip() or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    rows = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        rec = enrich_meta(rec, meta_by_url)
        row = normalize_lighthouse_record(rec, batch_id=batch_id)
        if row["jurisdiction_id"] and row["website_url"]:
            rows.append(row)
    n = persist_rows(rows, run_ddl=args.ensure_ddl)
    print(f"Upserted {n:,} row(s) into {BRONZE_LIGHTHOUSE_TABLE} (batch_id={batch_id})")


if __name__ == "__main__":
    main()
