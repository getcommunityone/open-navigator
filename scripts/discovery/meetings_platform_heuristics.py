"""
Heuristics inspired by civic meeting scrapers (e.g. City-Bureau city-scrapers_): detect common
vendor stacks and extract document / navigation URLs — **without** Scrapy.

.. _city-scrapers: https://github.com/City-Bureau/city-scrapers
"""
from __future__ import annotations

import re
from typing import FrozenSet, List, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Hosts where PDFs / meeting UI often live off the jurisdiction’s marketing domain.
_OFFSITE_SUFFIXES: Tuple[str, ...] = (
    "legistar.com",
    "legistar1.granicus.com",
    "legistarcloud.com",
    "granicus.com",
    "granicusideas.com",
    "civicclerk.com",
    "civicweb.net",
    "revize.com",
    "civicplus.com",
    "streamlinevillage.com",
    "boarddocs.com",
    "municodemeetings.com",
)

# Offsite HTML we may follow (narrow path hints to avoid crawling the whole vendor CDN).
_VENDOR_PATH_SNIPPETS: Tuple[str, ...] = (
    "viewmeeting",
    "viewpublisher",
    "mediaplayer",
    "calendar.aspx",
    "meetingdetail",
    "view.ashx",
    "legistar",
    "granicus",
    "events.aspx",
    "event.aspx",
    "commission",
    "cityclerk",
)

_STACK_PATTERNS: Tuple[Tuple[str, re.Pattern], ...] = (
    ("legistar", re.compile(r"legistar\.(com|net)|/legistar/|view\.ashx", re.I)),
    ("granicus", re.compile(r"granicus\.com|granicusideas\.com|viewmeeting\.aspx|viewpublisher", re.I)),
    ("civicclerk", re.compile(r"civicclerk\.com", re.I)),
    ("civicweb", re.compile(r"civicweb\.net", re.I)),
    ("revize", re.compile(r"revize\.com", re.I)),
    ("wordpress", re.compile(r"/wp-content/|/wp-json/|wordpress|xmlrpc\.php", re.I)),
    ("boarddocs", re.compile(r"boarddocs\.com", re.I)),
)

_DOC_TYPE_RULES: Tuple[Tuple[str, re.Pattern], ...] = (
    ("minutes", re.compile(r"minute|approved\s*minute", re.I)),
    ("agenda", re.compile(r"agenda|packet", re.I)),
    ("transcript", re.compile(r"transcript|caption|verbatim", re.I)),
    ("video", re.compile(r"video|webcast|recording|youtube|vimeo", re.I)),
)


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _host_matches_suffix(host: str, suffix: str) -> bool:
    h = host.rstrip(".").lower()
    s = suffix.lower().lstrip(".")
    return h == s or h.endswith("." + s)


def is_trusted_offsite(url: str) -> bool:
    h = _host(url)
    if not h:
        return False
    return any(_host_matches_suffix(h, s) for s in _OFFSITE_SUFFIXES)


def is_same_site(url: str, homepage: str) -> bool:
    try:
        a, b = urlparse(url).netloc.lower(), urlparse(homepage).netloc.lower()
        return bool(a and a == b)
    except Exception:
        return False


def _path_query_lower(url: str) -> str:
    try:
        p = urlparse(url)
        return f"{p.path.lower()}?{p.query.lower()}"
    except Exception:
        return (url or "").lower()


def is_vendor_meeting_page_url(url: str) -> bool:
    if not is_trusted_offsite(url):
        return False
    pq = _path_query_lower(url)
    return any(snippet in pq for snippet in _VENDOR_PATH_SNIPPETS)


PDF_EXT = re.compile(r"\.pdf(\?|#|$)", re.I)


def classify_document(url: str, anchor_text: str = "") -> str:
    blob = f"{url} {anchor_text}".lower()
    for name, pat in _DOC_TYPE_RULES:
        if pat.search(blob):
            return name
    return "unknown"


def detect_meeting_stacks(html: str, page_url: str) -> List[str]:
    """Return ordered unique stack ids (strong signals first)."""
    blob = f"{html[:120_000]} {page_url}".lower()
    found: List[str] = []
    seen: Set[str] = set()
    for name, pat in _STACK_PATTERNS:
        if pat.search(blob) and name not in seen:
            seen.add(name)
            found.append(name)
    return found


def merge_stack_hints(existing: Sequence[str], page_hints: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for seq in (existing, page_hints):
        for h in seq:
            if h not in seen:
                seen.add(h)
                out.append(h)
    return out


def extract_meeting_urls(
    html: str,
    page_url: str,
    homepage: str,
    *,
    generic_hint: re.Pattern,
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Return ``(nav_urls, pdf_pairs)`` to crawl or download.

    ``pdf_pairs`` are ``(absolute_url, anchor_text)`` for :pyfunc:`classify_document`.

    - Same-site links matching ``generic_hint`` on URL or anchor text, or PDFs.
    - Trusted offsite PDFs (Legistar / Granicus / …).
    - Trusted offsite vendor meeting pages (narrow path heuristics).
    """
    soup = BeautifulSoup(html or "", "html.parser")
    nav: List[str] = []
    pdfs: List[Tuple[str, str]] = []
    seen_nav: Set[str] = set()
    seen_pdf: Set[str] = set()

    def add_nav(u: str) -> None:
        if u not in seen_nav:
            seen_nav.add(u)
            nav.append(u)

    def add_pdf(u: str, anchor: str) -> None:
        if u not in seen_pdf:
            seen_pdf.add(u)
            pdfs.append((u, anchor))

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        full = urljoin(page_url, href)
        text = (a.get_text() or "").strip()
        text_l = text.lower()
        if PDF_EXT.search(full):
            if is_same_site(full, homepage) or is_trusted_offsite(full):
                add_pdf(full, text)
            continue
        if is_same_site(full, homepage):
            if generic_hint.search(full) or generic_hint.search(text_l):
                add_nav(full)
        elif is_vendor_meeting_page_url(full):
            add_nav(full)

    # iframes (embedded Legistar / Granicus calendars)
    for tag in soup.find_all(["iframe", "frame"], src=True):
        src = (tag.get("src") or "").strip()
        if not src:
            continue
        full = urljoin(page_url, src)
        if is_same_site(full, homepage) or is_vendor_meeting_page_url(full):
            add_nav(full)

    return nav, pdfs


def all_pdf_urls_from_page(
    html: str,
    page_url: str,
    homepage: str,
    generic_hint: re.Pattern,
) -> FrozenSet[str]:
    _, pairs = extract_meeting_urls(html, page_url, homepage, generic_hint=generic_hint)
    return frozenset(u for u, _ in pairs)
