#!/usr/bin/env python3
"""
Discover public-hearing / meeting / schedule links from cached DOT portal HTML, then
optionally fetch those pages and pull date-like strings (heuristic — not a full parser).

Why this exists
---------------
Many state DOT "public involvement" landing pages (e.g. AL) only **link** to the real
event lists (`pi_schedule.html`, calendars, Granicus, etc.). A single HTML snapshot
therefore often contains **no** embedded event rows. This script:

1. Reads ``data/cache/dot_public_involvement/{USPS}/source.json`` + ``public_involvement.html``
2. Collects same-site ``<a href>`` targets whose URL or anchor text looks event-related
3. With ``--fetch``, GETs each candidate (cap per state) and scans visible text for dates

Usage (repo root)::

  .venv/bin/python packages/scrapers/src/scrapers/dot/extract_dot_event_candidates_from_cache.py --states AL
  .venv/bin/python packages/scrapers/src/scrapers/dot/extract_dot_event_candidates_from_cache.py --states AL --fetch
  .venv/bin/python packages/scrapers/src/scrapers/dot/extract_dot_event_candidates_from_cache.py --all --fetch --max-fetch 10
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE = REPO_ROOT / "data" / "cache" / "dot_public_involvement"

USER_AGENT = (
    "OpenNavigatorDotResearch/1.0 (+https://github.com/getcommunityone/open-navigator-for-engagement; "
    "DOT event candidate extraction)"
)

# Match link URL or visible anchor text (not exhaustive — tune per adapter later)
EVENT_LINK_HINT = re.compile(
    r"(schedule|calendar|meeting|meetings|hearing|hearings|public\s*comment|"
    r"comment\s*period|nepa|workshop|forum|involvement|notice|agenda|minutes|"
    r"virtual\s*hearing|open\s*house)",
    re.I,
)

# Common US date patterns in page text
DATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
        re.I,
    ),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
]


def same_site(a: str, b: str) -> bool:
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()


def looks_like_404_html(html: str) -> bool:
    t = html.lower()
    if "<title>404" in t or "page not found" in t:
        return True
    return False


def discover_links(html: str, base_url: str, max_links: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        text = " ".join(a.stripped_strings)[:300]
        blob = f"{href} {text}"
        if not EVENT_LINK_HINT.search(blob):
            continue
        full = urljoin(base_url, href)
        if urlparse(full).scheme not in ("http", "https"):
            continue
        if not same_site(full, base_url):
            continue
        if full.split("#")[0].rstrip("/") == base_url.split("#")[0].rstrip("/"):
            continue
        if full in seen:
            continue
        seen.add(full)
        out.append({"url": full, "anchor_text": text})
        if len(out) >= max_links:
            break
    return out


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def extract_dates(text: str, limit: int = 80) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pat in DATE_PATTERNS:
        for m in pat.finditer(text):
            s = m.group(0).strip()
            if s not in seen:
                seen.add(s)
                found.append(s)
            if len(found) >= limit:
                return found
    return found


def process_state(
    usps: str,
    state_dir: Path,
    *,
    fetch: bool,
    max_fetch: int,
    timeout: float,
) -> dict[str, Any]:
    meta_path = state_dir / "source.json"
    html_path = state_dir / "public_involvement.html"
    pdf_path = state_dir / "public_involvement.pdf"
    if not meta_path.is_file():
        return {"state_usps": usps, "error": "missing_source_json"}
    if html_path.is_file():
        body_path = html_path
        body_kind = "html"
    elif pdf_path.is_file():
        return {
            "state_usps": usps,
            "error": "portal_is_pdf_only",
            "hint": "Run PDF text extraction separately (pdfplumber/pymupdf); link discovery needs HTML.",
        }
    else:
        return {"state_usps": usps, "error": "missing_public_involvement_html"}

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    base_url = meta.get("source_url") or ""
    html = body_path.read_text(encoding="utf-8", errors="replace")

    out: dict[str, Any] = {
        "state_usps": usps,
        "state_name": meta.get("state_name"),
        "portal_url": base_url,
        "portal_looks_like_404": looks_like_404_html(html),
        "discovered_event_links": discover_links(html, base_url, max_links=40),
        "fetched": [],
    }

    if out["portal_looks_like_404"]:
        out["hint"] = "Seed URL returned a 404-style page — update packages/scrapers/src/scrapers/dot/dot.txt and re-run download_state_dot_public_pages.py"

    if not fetch or not out["discovered_event_links"]:
        return out

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
    with httpx.Client(headers=headers, verify=True, follow_redirects=True) as client:
        for i, link in enumerate(out["discovered_event_links"][:max_fetch]):
            url = link["url"]
            try:
                r = client.get(url, timeout=timeout)
                ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
                entry: dict[str, Any] = {
                    "url": url,
                    "http_status": r.status_code,
                    "content_type": ctype,
                    "bytes": len(r.content),
                }
                if r.status_code == 200 and "html" in ctype:
                    text = visible_text(r.text)
                    entry["dates_found"] = extract_dates(text)
                    entry["text_preview"] = text[:1200]
                elif r.status_code == 200 and ctype == "application/pdf":
                    entry["note"] = "PDF response — use pdfplumber/pymupdf to extract text/dates."
                else:
                    entry["note"] = "non-html or error body skipped for date scan"
                out["fetched"].append(entry)
            except Exception as e:
                out["fetched"].append({"url": url, "error": str(e)})

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover / fetch DOT event-related pages from cache.")
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--states", nargs="*", help="USPS codes, e.g. AL WY")
    ap.add_argument("--all", action="store_true", help="Every subdirectory of cache that looks like a state")
    ap.add_argument("--fetch", action="store_true", help="GET discovered links and scan for dates")
    ap.add_argument("--max-fetch", type=int, default=8, help="Max extra pages to fetch per state")
    ap.add_argument("--timeout", type=float, default=45.0)
    args = ap.parse_args()

    if not args.cache.is_dir():
        logger.error("Cache dir missing: {}", args.cache)
        return 1

    if args.all:
        states = sorted(
            p.name.upper()
            for p in args.cache.iterdir()
            if p.is_dir() and len(p.name) == 2 and p.name.isalpha() and (p / "source.json").is_file()
        )
    elif args.states:
        states = [s.strip().upper() for s in args.states if s.strip()]
    else:
        logger.error("Use --all or --states AL WY ...")
        return 1

    summary: list[dict[str, Any]] = []
    for usps in states:
        d = args.cache / usps
        if not d.is_dir():
            logger.warning("Skip {} — no directory {}", usps, d)
            continue
        rec = process_state(usps, d, fetch=args.fetch, max_fetch=args.max_fetch, timeout=args.timeout)
        summary.append(rec)
        out_json = d / "events_candidates.json"
        out_json.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        logger.info("Wrote {}", out_json)
        n = len(rec.get("discovered_event_links") or [])
        logger.info("{} — {} candidate link(s)", usps, n)
        if rec.get("portal_looks_like_404"):
            logger.warning("{} — portal HTML looks like 404; fix seed URL in dot.txt", usps)

    manifest = args.cache / "_events_discovery_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "states": summary,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Wrote combined summary {}", manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
