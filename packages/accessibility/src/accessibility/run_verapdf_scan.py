#!/usr/bin/env python3
"""
Download PDFs and validate with veraPDF (PDF/UA, PDF/A) — CLI or Docker.

Reads ``export_pdf_urls.py`` manifest; writes NDJSON for ``persist_verapdf_results``.

Usage:
  .venv/bin/python -m accessibility.run_verapdf_scan \\
      --manifest data/cache/accessibility/pdf-urls.json
  VERAPDF_FLAVOURS=ua1,ua2 VERAPDF_WORKERS=4 \\
      .venv/bin/python -m accessibility.run_verapdf_scan --manifest ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import httpx
except ModuleNotFoundError:
    print("Install httpx: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

from accessibility.verapdf_cli import run_verapdf, summarize_validation_report

_UA = (
    os.getenv("ACCESSIBILITY_USER_AGENT")
    or "OpenNavigator-veraPDF/1.0 (+https://www.communityone.com)"
)
_MAX_BYTES = int(os.getenv("VERAPDF_MAX_BYTES") or str(15 * 1024 * 1024))


def _safe_filename(url: str) -> str:
    tail = re.sub(r"[^\w.\-]+", "_", url.split("?")[0].split("/")[-1])[:80]
    if not tail.lower().endswith(".pdf"):
        tail = f"{tail}.pdf"
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return f"{h}_{tail}"


def _flavours() -> List[str]:
    raw = (os.getenv("VERAPDF_FLAVOURS") or os.getenv("VERAPDF_FLAVOUR") or "ua1").strip()
    return [f.strip() for f in raw.split(",") if f.strip()]


def download_pdf(url: str, dest: Path) -> tuple[Optional[Path], Optional[str], int]:
    try:
        with httpx.Client(
            timeout=float(os.getenv("VERAPDF_DOWNLOAD_TIMEOUT_SEC") or "60"),
            headers={"User-Agent": _UA},
            follow_redirects=True,
        ) as client:
            with client.stream("GET", url) as r:
                if r.status_code >= 400:
                    return None, f"http_{r.status_code}", 0
                ctype = (r.headers.get("content-type") or "").lower()
                data = bytearray()
                for chunk in r.iter_bytes():
                    data.extend(chunk)
                    if len(data) > _MAX_BYTES:
                        return None, "pdf_too_large", len(data)
                if "pdf" not in ctype and not url.lower().split("?")[0].endswith(".pdf"):
                    if not data.startswith(b"%PDF"):
                        return None, "not_pdf_content", len(data)
                dest.write_bytes(data)
                return dest, None, len(data)
    except Exception as exc:
        return None, str(exc), 0


def scan_one(
    row: Dict[str, Any],
    *,
    batch_id: str,
    pdf_dir: Path,
    flavour: str,
) -> Dict[str, Any]:
    pdf_url = str(row.get("pdf_url") or "").strip()
    jid = str(row.get("jurisdiction_id") or "unknown")
    started = datetime.now(timezone.utc)
    t0 = started.timestamp()

    if not pdf_url:
        return {
            "batch_id": batch_id,
            "jurisdiction_id": jid,
            "pdf_url": pdf_url,
            "meta": row,
            "profile_flavour": flavour,
            "status": "skipped",
            "error": row.get("discover_status") or "no_pdf_url",
            "scanned_at": started.isoformat(),
        }

    dest = pdf_dir / _safe_filename(pdf_url)
    local, dl_err, nbytes = download_pdf(pdf_url, dest)
    if not local:
        return {
            "batch_id": batch_id,
            "jurisdiction_id": jid,
            "pdf_url": pdf_url,
            "meta": row,
            "profile_flavour": flavour,
            "status": "download_failed",
            "error": dl_err,
            "pdf_bytes": nbytes or None,
            "scanned_at": started.isoformat(),
            "scan_duration_ms": int((datetime.now(timezone.utc).timestamp() - t0) * 1000),
        }

    vr, vp_err = run_verapdf(local, flavour)
    summary = summarize_validation_report(vr) if vr else {}
    status = "ok" if not vp_err else "validation_error"
    return {
        "batch_id": batch_id,
        "jurisdiction_id": jid,
        "pdf_url": pdf_url,
        "meta": row,
        "profile_flavour": flavour,
        "status": status,
        "error": vp_err,
        "pdf_bytes": nbytes,
        "local_path": str(local),
        "scanned_at": started.isoformat(),
        "scan_duration_ms": int((datetime.now(timezone.utc).timestamp() - t0) * 1000),
        "validation": summary,
        "verapdf_report": vr,
    }


def load_manifest(path: Path) -> tuple[str, List[Dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    batch_id = str(data.get("batch_id") or "")
    pdfs = data.get("pdfs") if isinstance(data, dict) else data
    if not isinstance(pdfs, list):
        raise ValueError("manifest must contain a pdfs array")
    return batch_id, pdfs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--flavour", default="", help="Override VERAPDF_FLAVOUR(S)")
    args = ap.parse_args()

    batch_id, rows = load_manifest(args.manifest)
    batch_id = batch_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.offset:
        rows = rows[args.offset :]
    if args.limit:
        rows = rows[: args.limit]

    flavours = [args.flavour] if args.flavour else _flavours()
    workers = args.workers or int(os.getenv("VERAPDF_WORKERS") or "4")
    cache = _ROOT / "data" / "cache" / "accessibility" / f"verapdf-{batch_id}"
    pdf_dir = cache / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    out_path = args.out or (cache / f"verapdf-{batch_id}.ndjson")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tasks: List[tuple[Dict[str, Any], str]] = []
    for row in rows:
        for flavour in flavours:
            tasks.append((row, flavour))

    print(
        f"veraPDF: {len(rows)} manifest row(s) × {len(flavours)} flavour(s) = {len(tasks)} job(s), "
        f"workers={workers}"
    )

    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(scan_one, row, batch_id=batch_id, pdf_dir=pdf_dir, flavour=flavour): (
                row,
                flavour,
            )
            for row, flavour in tasks
        }
        with out_path.open("w", encoding="utf-8") as out_fh:
            for fut in as_completed(futures):
                rec = fut.result()
                out_fh.write(json.dumps(rec, default=str) + "\n")
                done += 1
                if done % 25 == 0:
                    print(f"  completed {done}/{len(tasks)}")

    print(f"Wrote NDJSON to {out_path}")
    print(
        f"Persist: .venv/bin/python -m accessibility.persist_verapdf_results "
        f"--input {out_path} --ensure-ddl"
    )


if __name__ == "__main__":
    main()
