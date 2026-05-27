#!/usr/bin/env python3
"""
Phase-1 downloader: State DOT public involvement / hearings portal pages.

Reads the markdown table in ``dot.txt`` (State | markdown link | hearings note),
maps state names to USPS codes, fetches each primary portal URL, and writes:

  data/cache/dot_public_involvement/{USPS}/public_involvement.html
  data/cache/dot_public_involvement/_manifest.json   (last run summary)

Optional: ``--pdfs`` discovers same-origin ``<a href=*.pdf>`` links on the saved
HTML (cap per state / max bytes) for offline notice packs.

This does not replace per-site adapters (Granicus, ArcGIS Hub, etc.); it is the
seed + snapshot step for a hybrid pipeline (see script docstring / repo docs).

Usage (repo root):

  python scripts/datasources/dot/download_state_dot_public_pages.py --all
  python scripts/datasources/dot/download_state_dot_public_pages.py --states AL TX GA
  python scripts/datasources/dot/download_state_dot_public_pages.py --all --pdfs --max-pdf-mb 6

After a successful download, discover linked schedule/calendar pages and (optionally) pull dates::

  python scripts/datasources/dot/extract_dot_event_candidates_from_cache.py --states AL --fetch
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse, urlencode, urlunparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DOT_MD = Path(__file__).resolve().parent / "dot.txt"
CACHE_ROOT = REPO_ROOT / "data" / "cache" / "dot_public_involvement"

USER_AGENT = (
    "OpenNavigatorDotResearch/1.0 (+https://github.com/getcommunityone/open-navigator-for-engagement; "
    "state DOT public involvement snapshots)"
)

# Full state / DC name → USPS (must match rows in dot.txt first column)
STATE_NAME_TO_USPS: dict[str, str] = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}


def strip_tracking_params(url: str) -> str:
    p = urlparse(url)
    pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    new_query = urlencode(pairs)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


def parse_dot_markdown_table(path: Path) -> list[dict[str, Any]]:
    """Parse ``dot.txt`` pipe table: state name, markdown link cell, hearings column."""
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    link_re = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")
    for line in text.splitlines():
        line = line.rstrip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        state_name = parts[1]
        if state_name == "State" or not state_name:
            continue
        if set(state_name) <= {"-", " "} or state_name.replace("-", "").strip() == "":
            continue
        link_cell = parts[2]
        hearings_note = parts[3] if len(parts) > 3 else ""
        m = link_re.search(link_cell)
        if not m:
            continue
        portal_label, url = m.group(1).strip(), strip_tracking_params(m.group(2).strip())
        usps = STATE_NAME_TO_USPS.get(state_name)
        if not usps:
            logger.warning("No USPS mapping for state name {!r}; skip", state_name)
            continue
        rows.append(
            {
                "state_usps": usps,
                "state_name": state_name,
                "portal_label": portal_label,
                "public_involvement_url": url,
                "hearings_note": hearings_note,
            }
        )
    return rows


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_url(
    client: httpx.Client,
    url: str,
    timeout: float,
) -> tuple[int | None, str | None, bytes]:
    try:
        r = client.get(url, timeout=timeout, follow_redirects=True)
        body = r.content
        ctype = r.headers.get("content-type", "").split(";")[0].strip().lower() or None
        return r.status_code, ctype, body
    except Exception as e:
        logger.error("GET failed {}: {}", url, e)
        return None, None, b""


def same_registrable_domain(a: str, b: str) -> bool:
    """Loose same-host check for PDF harvesting (portal host vs link host)."""
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()


def harvest_pdf_links(html_path: Path, base_url: str, limit: int) -> list[str]:
    raw = html_path.read_bytes()
    soup = BeautifulSoup(raw, "html.parser")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.lower().endswith(".pdf"):
            continue
        full = urljoin(base_url, href)
        if not same_registrable_domain(full, base_url):
            continue
        if full not in out:
            out.append(full)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Download state DOT public involvement portal pages (Phase 1).")
    ap.add_argument("--dot-md", type=Path, default=DEFAULT_DOT_MD, help="Markdown table source (default: dot.txt beside this script)")
    ap.add_argument("--cache", type=Path, default=CACHE_ROOT, help="Output cache directory")
    ap.add_argument("--states", nargs="*", help="USPS codes to fetch (e.g. AL TX). Default: none unless --all")
    ap.add_argument("--all", action="store_true", help="Fetch all states in the table")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--pdfs", action="store_true", help="Also download same-origin .pdf links found in HTML (capped)")
    ap.add_argument("--max-pdfs", type=int, default=12, help="Max PDFs per state when --pdfs")
    ap.add_argument("--max-pdf-mb", type=float, default=8.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dot_md.is_file():
        logger.error("Missing table file: {}", args.dot_md)
        return 1

    registry = parse_dot_markdown_table(args.dot_md)
    if not registry:
        logger.error("No rows parsed from {}", args.dot_md)
        return 1

    want = {r["state_usps"].upper() for r in registry}
    if args.all:
        selected = sorted(want)
    elif args.states:
        selected = [s.strip().upper() for s in args.states if s.strip()]
        bad = [s for s in selected if s not in want]
        if bad:
            logger.error("Unknown USPS codes (not in table): {}", bad)
            return 1
    else:
        logger.error("Specify --all or --states AL GA ...")
        return 1

    rows_by_usps = {r["state_usps"]: r for r in registry}
    args.cache.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, Any]] = []
    max_pdf_bytes = int(args.max_pdf_mb * 1024 * 1024)

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8"}

    if args.dry_run:
        for usps in selected:
            r = rows_by_usps[usps]
            logger.info("[dry-run] {} {} -> {}", usps, r["state_name"], r["public_involvement_url"])
        return 0

    with httpx.Client(headers=headers, verify=True) as client:
        for usps in selected:
            rec = rows_by_usps[usps]
            url = rec["public_involvement_url"]
            out_dir = args.cache / usps
            out_dir.mkdir(parents=True, exist_ok=True)

            status, ctype, body = fetch_url(client, url, args.timeout)
            entry: dict[str, Any] = {
                "state_usps": usps,
                "state_name": rec["state_name"],
                "url": url,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "http_status": status,
                "content_type": ctype,
                "bytes": len(body),
                "sha256": sha256_bytes(body) if body else None,
                "primary_path": None,
                "pdf_paths": [],
                "error": None,
            }

            if status is None or not body:
                entry["error"] = "empty_or_failed"
                manifest_rows.append(entry)
                logger.warning("{} fetch failed", usps)
                continue

            is_pdf = (ctype == "application/pdf") or url.lower().split("?")[0].endswith(".pdf")
            if is_pdf:
                primary = out_dir / "public_involvement.pdf"
                primary.write_bytes(body)
                entry["primary_path"] = str(primary.relative_to(REPO_ROOT))
                logger.info("{} saved PDF {} bytes -> {}", usps, len(body), primary)
            else:
                primary = out_dir / "public_involvement.html"
                primary.write_bytes(body)
                entry["primary_path"] = str(primary.relative_to(REPO_ROOT))
                meta = out_dir / "source.json"
                meta.write_text(
                    json.dumps(
                        {
                            "state_usps": usps,
                            "state_name": rec["state_name"],
                            "portal_label": rec["portal_label"],
                            "source_url": url,
                            "hearings_note": rec["hearings_note"],
                            "http_status": status,
                            "content_type": ctype,
                            "fetched_at": entry["fetched_at"],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                logger.info("{} saved HTML {} bytes -> {}", usps, len(body), primary)

                if args.pdfs and not is_pdf:
                    pdfs = harvest_pdf_links(primary, url, args.max_pdfs)
                    for i, pdf_url in enumerate(pdfs):
                        ps, pct, pdata = fetch_url(client, pdf_url, args.timeout)
                        if ps != 200 or not pdata:
                            logger.warning("{} skip PDF {} status={}", usps, pdf_url, ps)
                            continue
                        if len(pdata) > max_pdf_bytes:
                            logger.warning("{} skip PDF too large {} {}", usps, pdf_url, len(pdata))
                            continue
                        safe = re.sub(r"[^\w.\-]+", "_", urlparse(pdf_url).path.split("/")[-1])[:120] or f"document_{i}.pdf"
                        if not safe.lower().endswith(".pdf"):
                            safe += ".pdf"
                        pdf_path = out_dir / "pdfs" / safe
                        pdf_path.parent.mkdir(parents=True, exist_ok=True)
                        pdf_path.write_bytes(pdata)
                        rel = str(pdf_path.relative_to(REPO_ROOT))
                        entry["pdf_paths"].append({"url": pdf_url, "path": rel, "bytes": len(pdata)})
                        logger.info("{} saved PDF {}", usps, rel)

            manifest_rows.append(entry)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_table": str(args.dot_md.relative_to(REPO_ROOT)),
        "cache_root": str(args.cache.relative_to(REPO_ROOT)),
        "rows": manifest_rows,
    }
    man_path = args.cache / "_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Wrote manifest {}", man_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
