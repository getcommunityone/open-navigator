"""
Parse public YouTube channel pages (HTML) for ``UC…`` ids and metadata.

Shared by the jurisdiction pilot scraper and the YouTube events loader.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import unquote

import requests

_CHANNEL_ID_RE = re.compile(r"/channel/((?:UC)[A-Za-z0-9_-]{20,})", re.I)
_HANDLE_RE = re.compile(r"youtube\.com/@([^/?#]+)", re.I)
_UC_ID_CAPTURE = r"((?:UC)[A-Za-z0-9_-]{22})"

_HTML_CHANNEL_ID_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "subscribeEndpoint.channelIds",
        re.compile(
            rf'"subscribeEndpoint"\s*:\s*\{{[^{{}}]*"channelIds"\s*:\s*\[\s*"{_UC_ID_CAPTURE}"',
            re.I,
        ),
    ),
    ("channelId", re.compile(rf'"channelId"\s*:\s*"{_UC_ID_CAPTURE}"', re.I)),
    ("externalId", re.compile(rf'"externalId"\s*:\s*"{_UC_ID_CAPTURE}"', re.I)),
    ("browseId", re.compile(rf'"browseId"\s*:\s*"{_UC_ID_CAPTURE}"', re.I)),
    (
        "channelMetadataRenderer",
        re.compile(
            rf'"channelMetadataRenderer"[^{{}}]*"externalId"\s*:\s*"{_UC_ID_CAPTURE}"',
            re.I | re.DOTALL,
        ),
    ),
    (
        "canonicalUrl",
        re.compile(rf"https?://www\.youtube\.com/channel/{_UC_ID_CAPTURE}", re.I),
    ),
    ("rssFeed", re.compile(rf"feeds/videos\.xml\?channel_id={_UC_ID_CAPTURE}", re.I)),
)

_TITLE_PATTERNS = (
    re.compile(r'"channelMetadataRenderer".*?"title":"([^"]+)"', re.DOTALL),
    re.compile(r'<meta\s+property="og:title"\s+content="([^"]+)"', re.IGNORECASE),
)


def extract_channel_id_from_youtube_html(
    html: str,
    *,
    final_url: str = "",
) -> Optional[str]:
    """Parse ``UC…`` from channel page HTML (no API quota)."""
    if not html:
        for url in (final_url,):
            m = _CHANNEL_ID_RE.search(url or "")
            if m:
                return m.group(1)
        return None
    normalized = html.replace("\\/", "/")
    for url in (final_url,):
        m = _CHANNEL_ID_RE.search(url or "")
        if m:
            return m.group(1)
    counts: Counter[str] = Counter()
    for label, pattern in _HTML_CHANNEL_ID_PATTERNS:
        for match in pattern.finditer(normalized):
            cid = match.group(1)
            if cid.startswith("UC") and len(cid) >= 24:
                counts[cid] += 3 if label == "subscribeEndpoint.channelIds" else 1
    if not counts:
        return None
    cid, _hits = counts.most_common(1)[0]
    return cid


def extract_channel_title_from_youtube_html(html: str) -> str:
    if not html:
        return ""
    normalized = html.replace("\\/", "/")
    for pattern in _TITLE_PATTERNS:
        m = pattern.search(normalized)
        if m:
            title = m.group(1).strip()
            if title and title.lower() not in ("youtube", "home"):
                return title
    return ""


def canonical_channel_url(channel_id: str) -> str:
    cid = (channel_id or "").strip()
    if cid.startswith("UC"):
        return f"https://www.youtube.com/channel/{cid}"
    return ""


def _cookie_header(cookies_file: str | None) -> str | None:
    path = (cookies_file or "").strip()
    if not path or not Path(path).is_file():
        return None
    try:
        from http.cookiejar import MozillaCookieJar

        jar = MozillaCookieJar(path)
        jar.load(ignore_discard=True, ignore_expires=True)
        parts = [
            f"{c.name}={c.value}"
            for c in jar
            if "youtube.com" in (c.domain or "")
        ]
        return "; ".join(parts) if parts else None
    except Exception:
        return None


def fetch_youtube_channel_page(
    channel_url: str,
    *,
    session: requests.Session | None = None,
    cookies_file: str | None = None,
    timeout_s: float = 15,
) -> Tuple[str, str]:
    """Return ``(html, final_url)`` from About tab or channel home."""
    if not channel_url:
        return "", ""
    sess = session or requests.Session()
    sess.headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (compatible; OpenNavigatorJurisdictionPilot/1.0)",
    )
    sess.headers.setdefault("Accept-Language", "en-US,en;q=0.9")
    cookie_header = _cookie_header(cookies_file)
    if cookie_header:
        sess.headers["Cookie"] = cookie_header
    base = channel_url.rstrip("/")
    for page_url in (f"{base}/about", base, f"{base}/videos"):
        try:
            resp = sess.get(page_url, timeout=timeout_s, allow_redirects=True)
            if resp.status_code == 200 and resp.text:
                return resp.text, str(resp.url)
        except requests.RequestException:
            continue
    return "", ""


def resolve_channel_id_from_url(
    channel_url: str,
    *,
    session: requests.Session | None = None,
    cookies_file: str | None = None,
) -> Tuple[Optional[str], str]:
    """
    Resolve ``UC…`` from ``/channel/UC…`` or ``@handle`` URLs.

    Returns ``(channel_id, normalized_url)``.
    """
    url = (channel_url or "").strip()
    if not url:
        return None, url
    m = _CHANNEL_ID_RE.search(url)
    if m:
        cid = m.group(1)
        return cid, canonical_channel_url(cid) or url
    handle_m = _HANDLE_RE.search(url)
    if handle_m:
        handle = handle_m.group(1)
        for suffix in ("/videos", "/about", ""):
            page_url = f"https://www.youtube.com/@{handle}{suffix}"
            html, final_url = fetch_youtube_channel_page(
                page_url, session=session, cookies_file=cookies_file
            )
            cid = extract_channel_id_from_youtube_html(html, final_url=final_url)
            if cid:
                return cid, canonical_channel_url(cid)
    html, final_url = fetch_youtube_channel_page(
        url, session=session, cookies_file=cookies_file
    )
    cid = extract_channel_id_from_youtube_html(html, final_url=final_url)
    if cid:
        return cid, canonical_channel_url(cid)
    return None, url
