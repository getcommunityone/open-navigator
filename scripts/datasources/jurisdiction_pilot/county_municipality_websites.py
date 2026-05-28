"""
Discover and extract municipality website links from county directory pages.

Example: [Shelby County Municipalities](https://www.shelbyal.com/185/Municipalities)
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from scrapers.ballotpedia.ballotpedia_integration import BallotpediaDiscovery
from scripts.datasources.jurisdiction_pilot.http_fetch import BROWSER_USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT_S = 12
_SOURCE_PAGE_KIND = "county_municipalities"

_MUNICIPALITIES_PATH_RE = re.compile(
    r"/\d+/Municipalities(?:/|$|\?)|/Municipalities(?:/|$|\?)",
    re.IGNORECASE,
)
_MUNICIPALITIES_HREF_RE = re.compile(
    r"/\d+/Municipalities|/Municipalities(?:/|$|\?)",
    re.IGNORECASE,
)
_MUNICIPALITIES_HEADING_RE = re.compile(r"\bmunicipalit", re.IGNORECASE)
_MUNICIPALITIES_PROBE_PATHS: tuple[str, ...] = (
    "/Municipalities",
    "/municipalities",
    "/government/municipalities",
)
_GOVERNMENT_HUB_PATHS: tuple[str, ...] = (
    "/Elected-Officials",
    "/Government",
    "/27/Government",
)
_NAV_LABEL_SKIP_RE = re.compile(
    r"^(home|government|departments|how do i|discover|contact us|site map|"
    r"accessibility|disclaimer|copyright|quick links|document center|"
    r"bids|purchasing|pay property|online driver|municipalities?|search)$",
    re.IGNORECASE,
)
_MUNICIPALITY_NAME_RE = re.compile(
    r"^[A-Za-z][A-Za-z .'\-]{1,48}$",
)


def _norm_host(url: str) -> str:
    try:
        return re.sub(r"^www\.", "", (urlparse(url).netloc or "").lower())
    except Exception:
        return ""


def discover_county_municipalities_page_url(
    homepage_url: str,
    *,
    session: requests.Session | None = None,
    html_by_url: dict[str, str] | None = None,
) -> str | None:
    """Find the county's municipalities directory page (CivicPlus ``/NN/Municipalities``)."""
    if not homepage_url:
        return None

    county_host = _norm_host(homepage_url)
    if html_by_url:
        for page_url, html in html_by_url.items():
            if html and _MUNICIPALITIES_PATH_RE.search(page_url):
                if _municipalities_page_has_links(html, page_url, county_website_url=homepage_url):
                    return page_url
            if html:
                found = _municipalities_url_from_html(
                    html, page_url, county_host, county_website_url=homepage_url
                )
                if found:
                    return found

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", BROWSER_USER_AGENT)

    candidates: list[str] = [homepage_url]
    for path in _MUNICIPALITIES_PROBE_PATHS + _GOVERNMENT_HUB_PATHS:
        candidates.append(urljoin(homepage_url, path))

    try:
        resp = sess.get(homepage_url, timeout=_TIMEOUT_S, allow_redirects=True)
        if resp.text:
            host = urlparse(resp.url).netloc
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = (a.get("href") or "").strip()
                if not href or not _MUNICIPALITIES_HREF_RE.search(href):
                    continue
                abs_u = urljoin(resp.url, href)
                if urlparse(abs_u).netloc == host and abs_u not in candidates:
                    candidates.append(abs_u)
    except requests.RequestException:
        pass

    for page_url in candidates:
        if html_by_url and page_url in html_by_url and html_by_url[page_url]:
            found = _municipalities_url_from_html(
                html_by_url[page_url], page_url, county_host, county_website_url=homepage_url
            )
            if found:
                return found
            if _MUNICIPALITIES_PATH_RE.search(page_url) and _municipalities_page_has_links(
                html_by_url[page_url], page_url, county_website_url=homepage_url
            ):
                return page_url
        try:
            resp = sess.get(page_url, timeout=_TIMEOUT_S, allow_redirects=True)
            if not resp.text:
                continue
            if _municipalities_page_has_links(resp.text, resp.url, county_website_url=homepage_url):
                return resp.url
            found = _municipalities_url_from_html(
                resp.text, resp.url, county_host, county_website_url=homepage_url
            )
            if found:
                return found
        except requests.RequestException:
            continue
    return None


def _municipalities_page_has_links(
    html: str,
    page_url: str,
    *,
    county_website_url: str,
) -> bool:
    """True when the page yields at least one municipality outbound link."""
    return bool(
        extract_county_municipality_website_links(
            html,
            page_url,
            county_name="",
            state_code="XX",
            county_website_url=county_website_url,
            max_rows=3,
        )
    )


def _municipalities_url_from_html(
    html: str,
    base_url: str,
    county_host: str,
    *,
    county_website_url: str | None = None,
) -> str | None:
    if not html:
        return None
    county_home = county_website_url or base_url
    host = urlparse(base_url).netloc
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if href and _MUNICIPALITIES_HREF_RE.search(href):
            abs_u = urljoin(base_url, href)
            if urlparse(abs_u).netloc != host:
                continue
            if abs_u.rstrip("/") == base_url.rstrip("/"):
                continue
            if _municipalities_page_has_links(html, abs_u, county_website_url=county_home):
                return abs_u
    if _page_looks_like_municipalities_directory(html, base_url) and _municipalities_page_has_links(
        html, base_url, county_website_url=county_home
    ):
        return base_url
    return None


def _page_looks_like_municipalities_directory(html: str, page_url: str) -> bool:
    if _MUNICIPALITIES_PATH_RE.search(page_url or ""):
        return True
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:200]
    if _MUNICIPALITIES_HEADING_RE.search(title):
        return True
    for h in soup.find_all(["h1", "h2", "h3"]):
        if _MUNICIPALITIES_HEADING_RE.search(h.get_text(" ", strip=True) or ""):
            return True
    return False


def extract_county_municipality_website_links(
    html: str,
    page_url: str,
    *,
    county_name: str,
    state_code: str,
    county_website_url: str | None = None,
    max_rows: int = 200,
) -> list[dict[str, Any]]:
    """
    Parse a county municipalities directory page.

    Returns link-shaped dicts ready for ``bronze.bronze_websites_ballotpedia`` with
    ``raw_row`` containing county, state, municipality name, and web address.
    """
    if not html or max_rows <= 0:
        return []

    if not _page_looks_like_municipalities_directory(html, page_url):
        return []

    county_host = _norm_host(county_website_url or page_url)
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for a in soup.find_all("a", href=True):
        if len(out) >= max_rows:
            break
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        abs_url = urljoin(page_url, href)
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            continue
        target_host = _norm_host(abs_url)
        if not target_host or target_host == county_host:
            continue

        name = re.sub(r"\s+", " ", a.get_text(" ", strip=True) or "").strip()
        if not name or _NAV_LABEL_SKIP_RE.match(name):
            continue
        if not _MUNICIPALITY_NAME_RE.match(name):
            continue
        if any(
            tok in name.lower()
            for tok in ("civicplus", "license renewal", "discover shelby", "driver")
        ):
            continue

        key = (name.lower(), abs_url.lower())
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "source_page_url": page_url,
                "source_page_kind": _SOURCE_PAGE_KIND,
                "target_url": abs_url,
                "target_host": target_host,
                "target_kind": BallotpediaDiscovery.classify_external_host(target_host),
                "anchor_text": name[:512],
                "rel": " ".join(a.get("rel") or []) or None,
                "state_code": (state_code or "").strip().upper()[:2] or None,
                "raw_row": {
                    "county_name": county_name,
                    "state_code": (state_code or "").strip().upper()[:2],
                    "municipality_name": name,
                    "municipality_web_address": abs_url,
                    "page_found": page_url,
                },
            }
        )

    return out


def scrape_county_municipality_websites(
    *,
    county_name: str,
    state_code: str,
    county_website_url: str,
    session: requests.Session,
    html_by_url: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Discover municipalities page, extract links, return ``(rows, page_url)``.
    """
    page_url = discover_county_municipalities_page_url(
        county_website_url,
        session=session,
        html_by_url=html_by_url,
    )
    if not page_url:
        return [], None

    html = (html_by_url or {}).get(page_url)
    if not html:
        try:
            resp = session.get(page_url, timeout=_TIMEOUT_S, allow_redirects=True)
            if not resp.text:
                return [], page_url
            html = resp.text
            page_url = resp.url
        except requests.RequestException as exc:
            logger.debug("municipalities page fetch failed %s: %s", page_url, exc)
            return [], page_url

    rows = extract_county_municipality_website_links(
        html,
        page_url,
        county_name=county_name,
        state_code=state_code,
        county_website_url=county_website_url,
    )
    return rows, page_url
