#!/usr/bin/env python3
"""
Discover PDF links on jurisdiction homepages from ``intermediate.int_jurisdiction_websites``.

Writes a JSON manifest for ``run_verapdf_scan.py``. Each row is one PDF candidate
(``jurisdiction_id`` may repeat when multiple PDFs are found on the same site).

Usage:
  .venv/bin/python -m scripts.accessibility.export_pdf_urls --state AL --max-pdfs-per-site 3
  .venv/bin/python -m scripts.accessibility.export_pdf_urls --from-manifest data/pdfs.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import httpx
except ModuleNotFoundError:
    print("Install httpx: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

from scripts.accessibility.export_urls import fetch_url_jobs

_DEFAULT_OUT = _ROOT / "data" / "cache" / "accessibility" / "pdf-urls.json"
_PDF_HREF = re.compile(
    r"""href\s*=\s*["']([^"']+\.pdf(?:\?[^"']*)?)["']""",
    re.IGNORECASE,
)
_UA = (
    os.getenv("ACCESSIBILITY_USER_AGENT")
    or "OpenNavigator-PdfDiscovery/1.0 (+https://www.communityone.com)"
)


def _same_origin(base: str, link: str) -> bool:
    b = urlparse(base)
    l = urlparse(link)
    return (b.scheme, b.netloc) == (l.scheme, l.netloc)


def extract_pdf_links(html: str, base_url: str, *, same_origin_only: bool) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for m in _PDF_HREF.finditer(html or ""):
        href = (m.group(1) or "").strip()
        if not href or href.startswith("#"):
            continue
        abs_url = urljoin(base_url, href)
        if same_origin_only and not _same_origin(base_url, abs_url):
            continue
        key = abs_url.split("#")[0]
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


async def _fetch_html(client: httpx.AsyncClient, url: str) -> tuple[str, Optional[int], Optional[str]]:
    try:
        r = await client.get(url, follow_redirects=True)
        return r.text, r.status_code, str(r.url)
    except Exception as exc:
        return "", None, str(exc)


async def discover_pdfs_for_jobs(
    jobs: List[Dict[str, Any]],
    *,
    max_pdfs_per_site: int,
    concurrency: int,
    same_origin_only: bool,
) -> List[Dict[str, Any]]:
    timeout = float(os.getenv("PDF_DISCOVER_TIMEOUT_SEC") or "25")
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": _UA},
        limits=limits,
    ) as client:
        sem = asyncio.Semaphore(concurrency)

        async def one(job: Dict[str, Any]) -> List[Dict[str, Any]]:
            homepage = str(job.get("url") or "").strip()
            if not homepage:
                return []
            async with sem:
                html, status, final_or_err = await _fetch_html(client, homepage)
            if not html:
                return [
                    {
                        **job,
                        "homepage_url": homepage,
                        "pdf_url": None,
                        "discover_status": "homepage_error",
                        "discover_error": final_or_err,
                        "homepage_http_status": status,
                    }
                ]
            final_url = final_or_err if status else homepage
            links = extract_pdf_links(html, final_url or homepage, same_origin_only=same_origin_only)
            links = links[: max(0, max_pdfs_per_site)]
            if not links:
                return [
                    {
                        **job,
                        "homepage_url": final_url or homepage,
                        "pdf_url": None,
                        "discover_status": "no_pdf_found",
                        "homepage_http_status": status,
                    }
                ]
            rows: List[Dict[str, Any]] = []
            for pdf_url in links:
                rows.append(
                    {
                        **job,
                        "homepage_url": final_url or homepage,
                        "pdf_url": pdf_url,
                        "discover_status": "ok",
                        "homepage_http_status": status,
                    }
                )
            return rows

        nested = await asyncio.gather(*[one(j) for j in jobs])
    flat: List[Dict[str, Any]] = []
    for chunk in nested:
        flat.extend(chunk)
    return flat


def load_manifest(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "pdfs" in data:
        return list(data["pdfs"])
    if isinstance(data, list):
        return data
    raise ValueError(f"unsupported manifest shape: {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", help="Filter jurisdictions by state_code")
    ap.add_argument("--limit", type=int, help="Max homepages to crawl")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--batch-id", default="")
    ap.add_argument("--max-pdfs-per-site", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument(
        "--allow-offsite-pdfs",
        action="store_true",
        help="Include PDF links on other domains (default: same-origin only)",
    )
    ap.add_argument(
        "--from-manifest",
        type=Path,
        help="Skip crawl; use existing JSON list of {jurisdiction_id, pdf_url, ...}",
    )
    ap.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = ap.parse_args()

    batch_id = (args.batch_id or "").strip() or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    if args.from_manifest:
        pdfs = load_manifest(args.from_manifest)
        payload = {
            "batch_id": batch_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": "manifest",
            "count": len(pdfs),
            "pdfs": pdfs,
        }
    else:
        jobs = fetch_url_jobs(
            state=args.state,
            limit=args.limit,
            offset=args.offset,
        )
        pdfs = asyncio.run(
            discover_pdfs_for_jobs(
                jobs,
                max_pdfs_per_site=args.max_pdfs_per_site,
                concurrency=args.concurrency,
                same_origin_only=not args.allow_offsite_pdfs,
            )
        )
        payload = {
            "batch_id": batch_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": "int_jurisdiction_websites_homepage_crawl",
            "count": len(pdfs),
            "pdfs": pdfs,
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with_pdf = sum(1 for p in pdfs if p.get("pdf_url"))
    print(f"Wrote {len(pdfs):,} row(s) ({with_pdf:,} with pdf_url) to {args.out} (batch_id={batch_id})")


if __name__ == "__main__":
    main()
