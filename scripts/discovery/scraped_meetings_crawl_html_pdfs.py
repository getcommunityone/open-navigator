"""
Recover meeting PDF download metadata from saved ``_crawl_html/page_*.html`` snapshots.

Used when ``_manifest.json`` ``pdfs`` is empty but PDFs remain on disk (e.g. SuiteOne handler
URLs that slugified to ``YYYY_agenda_agenda_<urlhash>.pdf``).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

from scripts.discovery.meetings_platform_heuristics import classify_document
from scripts.utils.http_url_normalize import normalize_http_url_path_encoding

_HASH8_SUFFIX = re.compile(r"_([a-f0-9]{8})\.pdf$", re.I)
_SUITEONE_HOST = "suiteonemedia.com"


def url_hash8(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8", errors="replace")).hexdigest()[:8]


def hash8_from_pdf_basename(name: str) -> Optional[str]:
    m = _HASH8_SUFFIX.search(name or "")
    return m.group(1).lower() if m else None


def _suiteone_https_bases(urls: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for raw in urls:
        try:
            p = urlparse((raw or "").strip())
        except Exception:
            continue
        host = (p.netloc or "").lower()
        if not host.endswith(_SUITEONE_HOST):
            continue
        base = f"{p.scheme or 'https'}://{host}"
        if base not in seen:
            seen.add(base)
            out.append(base)
    return out


def _row_anchor_and_title(tr) -> Tuple[str, str, str]:
    """Meeting title link text and date cell from a SuiteOne listing ``<tr>``."""
    title_a = tr.select_one("td a[href*='/event/?id=']")
    title = title_a.get_text(" ", strip=True) if title_a else ""
    date_txt = ""
    tds = tr.find_all("td")
    if len(tds) > 1:
        date_txt = tds[1].get_text(" ", strip=True)
    return title, date_txt, title


def _merge_anchor(link_anchor: str, title: str, date_txt: str) -> str:
    anchor = (link_anchor or "").strip()
    if title and title.lower() not in anchor.lower():
        return f"{title} — {date_txt}" if date_txt else title
    if date_txt and date_txt not in anchor:
        return f"{anchor} — {date_txt}".strip(" —") if anchor else date_txt
    return anchor


def extract_meeting_document_pairs_from_crawl_html(
    crawl_html_dir: Path,
    *,
    https_bases: Optional[List[str]] = None,
    seed_urls: Optional[List[str]] = None,
) -> List[Tuple[str, str]]:
    """
    Return deduplicated ``(absolute_url, anchor_text)`` for agenda/minutes handler links.

    SuiteOne rows use the meeting title and date column when link ``title``/``aria-label`` are generic.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ImportError("beautifulsoup4 is required for crawl HTML PDF recovery") from exc

    crawl_html_dir = crawl_html_dir.expanduser().resolve()
    if not crawl_html_dir.is_dir():
        return []

    bases = list(https_bases or [])
    if seed_urls:
        bases.extend(_suiteone_https_bases(seed_urls))
    if not bases:
        bases = ["https://tuscaloosaal.suiteonemedia.com"]

    seen: Set[str] = set()
    out: List[Tuple[str, str]] = []

    for hp in sorted(crawl_html_dir.glob("page_*.html")):
        html = hp.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for tr in soup.select("table tbody tr"):
            title, date_txt, _ = _row_anchor_and_title(tr)
            for a in tr.select("a[href*='GetAgendaFile'], a[href*='GetMinutesFile']"):
                href = (a.get("href") or "").strip()
                if not href:
                    continue
                link_anchor = (a.get("aria-label") or a.get("title") or "").strip()
                anchor = _merge_anchor(link_anchor, title, date_txt)
                for base in bases:
                    url = normalize_http_url_path_encoding(urljoin(base.rstrip("/") + "/", href))
                    if url in seen:
                        break
                    seen.add(url)
                    out.append((url, anchor[:500]))
                    break

        # Generic PDF anchors (non-SuiteOne pages in the same crawl bundle).
        page_base = None
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or (
                "GetAgendaFile" not in href
                and "GetMinutesFile" not in href
                and not href.lower().endswith(".pdf")
            ):
                continue
            anchor = (a.get_text(" ", strip=True) or a.get("title") or "")[:500]
            for base in bases:
                url = normalize_http_url_path_encoding(urljoin(base.rstrip("/") + "/", href))
                if url in seen:
                    break
                if href.lower().endswith(".pdf") or "GetAgenda" in href or "GetMinutes" in href:
                    seen.add(url)
                    out.append((url, anchor))
                break

    return out


def build_pdf_rows_from_disk_and_crawl_html(
    jurisdiction_dir: Path,
    *,
    calendar_year_dirs: Optional[List[str]] = None,
    seed_urls: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Map on-disk PDFs to manifest-shaped rows using URL hash suffixes and crawl HTML metadata.
    """
    jurisdiction_dir = jurisdiction_dir.expanduser().resolve()
    crawl_html = jurisdiction_dir / "_crawl_html"
    seed = list(seed_urls or [])
    manifest_path = jurisdiction_dir / "_manifest.json"
    if manifest_path.is_file():
        try:
            import json

            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            for u in data.get("pages_fetched") or []:
                if isinstance(u, str):
                    seed.append(u)
        except (OSError, json.JSONDecodeError):
            pass

    bases = _suiteone_https_bases(seed)
    pairs = extract_meeting_document_pairs_from_crawl_html(
        crawl_html, https_bases=bases, seed_urls=seed
    )
    by_h8: Dict[str, Tuple[str, str]] = {}
    for url, anchor in pairs:
        by_h8[url_hash8(url)] = (url, anchor)

    if calendar_year_dirs:
        scan_roots = [
            jurisdiction_dir / y.strip()
            for y in calendar_year_dirs
            if y.strip().isdigit() and len(y.strip()) == 4
        ]
    else:
        scan_roots = [p for p in jurisdiction_dir.iterdir() if p.is_dir() and p.name.isdigit() and len(p.name) == 4]

    rows: List[Dict[str, Any]] = []
    seen_urls: Set[str] = set()
    for year_dir in scan_roots:
        if not year_dir.is_dir():
            continue
        folder_year = year_dir.name
        for pdf in sorted(year_dir.glob("*.pdf")):
            h8 = hash8_from_pdf_basename(pdf.name)
            if not h8 or h8 not in by_h8:
                continue
            url, anchor = by_h8[h8]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            doc_type = classify_document(url, anchor)
            try:
                nbytes = pdf.stat().st_size
            except OSError:
                nbytes = 0
            rows.append(
                {
                    "url": url,
                    "path": str(pdf.resolve()),
                    "year": folder_year,
                    "bytes": nbytes,
                    "doc_type": doc_type,
                    "anchor_text": anchor,
                    "storage_suffix": ".pdf",
                    "recovered_from": "crawl_html",
                }
            )
    return rows
