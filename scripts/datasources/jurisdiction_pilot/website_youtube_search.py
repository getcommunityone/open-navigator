"""
Search for YouTube channels on jurisdiction websites using DuckDuckGo Instant Answer API.

DuckDuckGo's free API works better than Google for this use case:
- No JavaScript rendering required
- Not aggressively blocked
- Returns structured results quickly
- Supports site: queries for finding channels linked from the jurisdiction's website
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Sequence
from urllib.parse import urlparse

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)

_USER_AGENT = "OpenNavigatorJurisdictionPilot/1.0"
_TIMEOUT_S = 10
_DUCKDUCKGO_API = "https://api.duckduckgo.com"

# Common paths to try when looking for YouTube links
_COMMON_PATHS = (
    "",  # Homepage
    "/",
    "/about",
    "/media",
    "/government",
    "/meetings",
    "/video",
)


def _extract_domain(website_url: str) -> str:
    """Extract domain from full URL. e.g. https://example.gov -> example.gov"""
    if not website_url:
        return ""
    try:
        parsed = urlparse(website_url)
        domain = parsed.netloc or parsed.path
        # Remove www. prefix
        domain = re.sub(r"^www\.", "", domain).lower()
        return domain.strip()
    except Exception:
        return ""


def _extract_youtube_urls_from_html(html: str) -> list[str]:
    """Extract YouTube channel URLs from HTML."""
    if not html:
        return []

    urls = []
    seen = set()

    if BeautifulSoup:
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Find all links
            for link in soup.find_all("a", href=True):
                href = link.get("href", "").strip()
                if "youtube.com" in href.lower():
                    normalized = _normalize_youtube_url(href)
                    if normalized and normalized not in seen:
                        seen.add(normalized)
                        urls.append(normalized)
        except Exception:
            pass

    # Regex fallback (always run for robustness)
    pattern = re.compile(
        r'(?:href=)?["\']?(https?://(?:www\.)?youtube\.com/(?:@[A-Za-z0-9_-]+|c/[A-Za-z0-9_-]+|channel/[A-Za-z0-9_-]+|user/[A-Za-z0-9_-]+))["\']?',
        re.IGNORECASE
    )
    for match in pattern.finditer(html):
        url = match.group(1).rstrip('/')
        if url not in seen:
            seen.add(url)
            urls.append(url)

    return urls


def _normalize_youtube_url(url: str) -> str | None:
    """Normalize and validate a YouTube URL."""
    if not url:
        return None

    url = url.strip()

    # Extract channel identifier from various YouTube URL formats
    match = re.search(
        r'(?:https?://)?(?:www\.)?youtube\.com/(@[A-Za-z0-9_-]+|c/[A-Za-z0-9_-]+|channel/[A-Za-z0-9_-]+|user/[A-Za-z0-9_-]+)',
        url,
        re.IGNORECASE
    )

    if match:
        identifier = match.group(1)
        return f"https://www.youtube.com/{identifier}"

    return None


def search_duckduckgo_for_youtube(
    website_url: str,
    *,
    session: requests.Session | None = None,
) -> list[str]:
    """
    Search for YouTube links on jurisdiction website using DuckDuckGo.

    Uses site: operator to find YouTube URLs linked from the jurisdiction's domain.
    Returns list of unique YouTube channel URLs.
    """
    domain = _extract_domain(website_url)
    if not domain:
        logger.debug("Could not extract domain from %s", website_url)
        return []

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", _USER_AGENT)
    sess.verify = False  # Skip SSL verification for government websites with cert issues

    # Construct DuckDuckGo search query for YouTube links on this domain
    query = f"site:{domain} youtube"

    params = {
        "q": query,
        "format": "json",
        "no_redirect": 1,
    }

    youtube_urls = []

    try:
        logger.debug("Searching DuckDuckGo for YouTube links: %s", query)
        resp = sess.get(_DUCKDUCKGO_API, params=params, timeout=_TIMEOUT_S)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError):
                logger.debug("Failed to parse DuckDuckGo response as JSON")
                return []

            # Check Related Topics for relevant results
            related = data.get("Related", [])
            for topic in related:
                text = topic.get("Text", "")
                if "youtube.com" in text.lower():
                    # Extract URLs from the text
                    urls = _extract_youtube_urls_from_text(text)
                    youtube_urls.extend(urls)

            if youtube_urls:
                logger.debug("Found %d YouTube URLs on %s via DuckDuckGo", len(youtube_urls), domain)

    except requests.RequestException as exc:
        logger.debug("DuckDuckGo search failed for %s: %s", query, exc)

    return youtube_urls


def _extract_youtube_urls_from_text(text: str) -> list[str]:
    """Extract YouTube URLs from text."""
    urls = []
    pattern = re.compile(
        r'(?:https?://)?(?:www\.)?youtube\.com/(?:@[A-Za-z0-9_-]+|c/[A-Za-z0-9_-]+|channel/[A-Za-z0-9_-]+|user/[A-Za-z0-9_-]+)',
        re.IGNORECASE
    )
    for match in pattern.finditer(text):
        url = match.group(0)
        if not url.startswith("http"):
            url = "https://" + url
        normalized = _normalize_youtube_url(url)
        if normalized:
            urls.append(normalized)
    return urls


def crawl_website_for_youtube(
    website_url: str,
    *,
    session: requests.Session | None = None,
    max_pages: int = 5,
) -> list[str]:
    """
    Crawl jurisdiction website for YouTube channel links.

    Tries common paths and extracts YouTube URLs found in the HTML.
    Returns list of unique YouTube channel URLs.
    """
    if not website_url:
        return []

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", _USER_AGENT)
    sess.verify = False  # Skip SSL verification for government websites with cert issues

    base_url = website_url.rstrip("/")
    all_urls: dict[str, str] = {}  # URL -> URL (for dedup)
    pages_tried = 0

    for path in _COMMON_PATHS:
        if pages_tried >= max_pages:
            break

        url = f"{base_url}{path}"
        pages_tried += 1

        try:
            logger.debug("Crawling %s for YouTube links", url)
            resp = sess.get(url, timeout=_TIMEOUT_S, allow_redirects=True)

            if resp.status_code == 200 and resp.text:
                found = _extract_youtube_urls_from_html(resp.text)
                for yt_url in found:
                    all_urls[yt_url] = yt_url
                if found:
                    logger.debug("  → found %d YouTube URLs", len(found))

        except requests.RequestException as exc:
            logger.debug("Failed to crawl %s: %s", url, exc)

    return list(all_urls.values())


def search_multiple_queries(
    website_url: str,
    queries: Sequence[str] = None,
    *,
    session: requests.Session | None = None,
) -> list[str]:
    """
    Search for YouTube channels on jurisdiction website.

    Priority:
    1. DuckDuckGo site: search (most reliable for finding linked content)
    2. Direct website crawling (fallback)

    Returns deduplicated list of YouTube URLs.
    """
    sess = session or requests.Session()
    sess.verify = False

    all_urls: dict[str, str] = {}

    # Try DuckDuckGo first
    ddg_urls = search_duckduckgo_for_youtube(website_url, session=sess)
    for url in ddg_urls:
        all_urls[url] = url

    # If DuckDuckGo finds nothing, try crawling the website directly
    if not all_urls:
        crawl_urls = crawl_website_for_youtube(website_url, session=sess)
        for url in crawl_urls:
            all_urls[url] = url

    return list(all_urls.values())


