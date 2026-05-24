"""
Extract election calendar rows, candidacies, and ballot measures from jurisdiction HTML.

Best-effort heuristics for city/county sites — not a substitute for official election files,
but suitable for bronze + c1 promotion when no external API is used.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

ELECTION_LINK_RE = re.compile(
    r"\b(?:election|elections|ballot|ballots|candidate|candidates|voting|vote|voter|"
    r"poll(?:ing)?|sample[- ]ballot|election[- ]results?|runoff|primary|general)\b",
    re.I,
)

ELECTION_HEADING_RE = re.compile(
    r"\b(?:election|ballot|candidate|voting|vote|primary|general|runoff|special)\b",
    re.I,
)

DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
    ),
    re.compile(
        r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b",
    ),
    re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
        re.I,
    ),
)

_MONTH = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

ELECTION_PROBE_PATHS: tuple[str, ...] = (
    "/elections",
    "/elections/",
    "/election-information",
    "/election-info",
    "/vote",
    "/voting",
    "/voter-information",
    "/ballot",
    "/candidates",
    "/election-results",
    "/government/elections",
    "/departments/city-clerk/elections",
    "/departments/city-clerk/election-information",
    "/county-clerk/elections",
)


def _same_site(url: str, base: str) -> bool:
    try:
        return urlparse(url).netloc.lower() == urlparse(base).netloc.lower()
    except Exception:
        return False


def discover_election_page_urls(homepage_url: str, html: str, *, max_urls: int = 12) -> list[str]:
    """Collect same-site links that look election-related."""
    if not homepage_url or not html:
        return []
    out: list[str] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:")):
            continue
        text = a.get_text(" ", strip=True)
        if not ELECTION_LINK_RE.search(href) and not ELECTION_LINK_RE.search(text):
            continue
        abs_url = urljoin(homepage_url, href)
        if not _same_site(abs_url, homepage_url):
            continue
        norm = abs_url.split("#", 1)[0].rstrip("/")
        if norm in seen:
            continue
        seen.add(norm)
        out.append(abs_url)
        if len(out) >= max_urls:
            break
    return out


def candidate_election_urls(homepage_url: str) -> list[str]:
    """Build ordered ``/elections``-style URLs relative to the jurisdiction homepage."""
    if not homepage_url:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for path in ELECTION_PROBE_PATHS:
        url = urljoin(homepage_url, path)
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def probe_election_path_urls(homepage_url: str, session) -> list[str]:
    """HEAD/GET common ``/elections``-style paths on the site host."""
    from scripts.datasources.jurisdiction_pilot.mayor_url_discovery import probe_urls

    return probe_urls(candidate_election_urls(homepage_url), session=session)


def _parse_date_from_text(text: str) -> date | None:
    blob = (text or "").strip()
    if not blob:
        return None
    m = DATE_PATTERNS[0].search(blob)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = DATE_PATTERNS[1].search(blob)
    if m:
        mo, da, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr += 2000
        try:
            return date(yr, mo, da)
        except ValueError:
            pass
    m = DATE_PATTERNS[2].search(blob)
    if m:
        mo = _MONTH.get(m.group(1).lower())
        if mo:
            try:
                return date(int(m.group(3)), mo, int(m.group(2)))
            except ValueError:
                pass
    return None


def _infer_election_type(text: str) -> str:
    low = (text or "").lower()
    for label in ("primary", "general", "runoff", "special", "municipal"):
        if label in low:
            return label
    return "unknown"


def _json_ld_events(soup: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

        def walk(node: Any) -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item)
            elif isinstance(node, dict):
                t = node.get("@type") or ""
                types = t if isinstance(t, list) else [t]
                if any(str(x).lower() == "event" for x in types):
                    name = (node.get("name") or "").strip()
                    start = node.get("startDate") or node.get("startdate") or ""
                    if name and ELECTION_HEADING_RE.search(name):
                        rows.append({
                            "name": name,
                            "election_date": _parse_date_from_text(str(start)) or _parse_date_from_text(name),
                            "election_type": _infer_election_type(name),
                            "source_url": page_url,
                            "extraction_method": "json_ld_event",
                            "raw_snippet": name,
                        })
                for v in node.values():
                    walk(v)

        walk(data)
    return rows


def _heading_blocks(soup: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tag in soup.find_all(re.compile(r"^h[1-3]$", re.I)):
        title = tag.get_text(" ", strip=True)
        if not title or not ELECTION_HEADING_RE.search(title):
            continue
        sibling_text = []
        for sib in tag.find_next_siblings(limit=4):
            if getattr(sib, "name", None) and re.match(r"^h[1-3]$", sib.name, re.I):
                break
            sibling_text.append(sib.get_text(" ", strip=True))
        block = " ".join([title, *sibling_text])
        rows.append({
            "name": title[:500],
            "election_date": _parse_date_from_text(block),
            "election_type": _infer_election_type(title),
            "source_url": page_url,
            "extraction_method": "heading_block",
            "raw_snippet": block[:2000],
        })
    return rows


def _table_candidacies(soup: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        headers = [
            th.get_text(" ", strip=True).lower()
            for th in table.find_all("th")
        ]
        if not headers:
            first = table.find("tr")
            if first:
                headers = [c.get_text(" ", strip=True).lower() for c in first.find_all(["td", "th"])]
        header_blob = " ".join(headers)
        if not re.search(r"candidate|name|office|position|party|seat", header_blob, re.I):
            continue
        name_idx = party_idx = office_idx = -1
        for i, h in enumerate(headers):
            if "name" in h or h == "candidate":
                name_idx = i
            if "party" in h:
                party_idx = i
            if "office" in h or "position" in h or "seat" in h:
                office_idx = i
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            if name_idx >= 0 and name_idx < len(cells):
                person = cells[name_idx]
            else:
                person = cells[0]
            if not person or len(person) < 2 or person.lower() in headers:
                continue
            if not re.search(r"[A-Za-z]{2,}", person):
                continue
            party = cells[party_idx] if 0 <= party_idx < len(cells) else None
            office = cells[office_idx] if 0 <= office_idx < len(cells) else None
            rows.append({
                "person_name": person[:300],
                "party": (party or "")[:120] or None,
                "office": (office or "")[:300] or None,
                "status": "candidate",
                "source_url": page_url,
                "extraction_method": "html_table",
            })
    return rows


def _list_ballot_measures(soup: BeautifulSoup, page_url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)
        if not text or len(text) < 12:
            continue
        if not re.search(r"\b(?:proposition|measure|question|referendum|amendment)\b", text, re.I):
            continue
        if not re.search(r"\b\d+\b", text) and "?" not in text:
            continue
        rows.append({
            "title": text[:500],
            "summary": text[:2000],
            "classification": "referendum",
            "source_url": page_url,
            "extraction_method": "list_item",
        })
    return rows


def extract_election_bundle_from_html(html: str, page_url: str) -> dict[str, Any]:
    """
    Parse one HTML page into elections, candidacies, and ballot-measure candidates.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    elections: list[dict[str, Any]] = []
    elections.extend(_json_ld_events(soup, page_url))
    elections.extend(_heading_blocks(soup, page_url))

    # Page title as weak election row when election-themed
    title = (soup.title.string or "").strip() if soup.title else ""
    if title and ELECTION_HEADING_RE.search(title):
        elections.append({
            "name": title[:500],
            "election_date": _parse_date_from_text(title),
            "election_type": _infer_election_type(title),
            "source_url": page_url,
            "extraction_method": "document_title",
            "raw_snippet": title,
        })

    candidacies = _table_candidacies(soup, page_url)
    measures = _list_ballot_measures(soup, page_url)

    return {
        "page_url": page_url,
        "elections": elections,
        "candidacies": candidacies,
        "ballot_measures": measures,
    }


def merge_election_bundles(bundles: list[dict[str, Any]]) -> dict[str, Any]:
    """Deduplicate merged bundles from multiple pages."""
    elections: list[dict[str, Any]] = []
    candidacies: list[dict[str, Any]] = []
    measures: list[dict[str, Any]] = []
    seen_e: set[tuple[str, str]] = set()
    seen_c: set[tuple[str, str, str]] = set()
    seen_m: set[str] = set()

    for bundle in bundles:
        for e in bundle.get("elections") or []:
            key = ((e.get("name") or "").lower(), str(e.get("election_date") or ""))
            if key in seen_e:
                continue
            seen_e.add(key)
            elections.append(e)
        for c in bundle.get("candidacies") or []:
            key = (
                (c.get("person_name") or "").lower(),
                (c.get("office") or "").lower(),
                c.get("source_url") or "",
            )
            if key in seen_c:
                continue
            seen_c.add(key)
            candidacies.append(c)
        for m in bundle.get("ballot_measures") or []:
            key = (m.get("title") or "").lower()
            if key in seen_m:
                continue
            seen_m.add(key)
            measures.append(m)

    return {
        "elections": elections,
        "candidacies": candidacies,
        "ballot_measures": measures,
        "pages_scraped": [b.get("page_url") for b in bundles if b.get("page_url")],
    }
