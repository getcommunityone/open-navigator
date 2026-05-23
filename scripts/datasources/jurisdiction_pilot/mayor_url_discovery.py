"""
Discover candidate mayor / council pages for a jurisdiction *without* a hand-curated
seed list. Used at scale across priority states where curating seeds for hundreds of
jurisdictions isn't feasible.

Two-tier strategy:

1. **Heuristic probe** — generate ``/mayor``, ``/mayors-office``, ``/government/mayor`` …
   candidates relative to the homepage; HEAD each; keep what returns 200.

2. **Homepage anchor crawl** — if the probe finds nothing, fetch the homepage HTML and
   collect anchors whose href OR visible text mentions ``mayor`` / ``council`` /
   ``commissioner``. Returns absolute URLs (deduped, capped).

Used by the generalized runner alongside the hand-curated seeds in
``scripts/discovery/jurisdiction_contact_seed_urls.py`` (those still take priority
where they exist — see ``merged_contact_seed_urls``).
"""

from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENT = "OpenNavigatorJurisdictionPilot/1.0"
_TIMEOUT_S = 12

# Ordered by likelihood. Single-word forms first (matches the largest share of city
# sites), then "office" variants, then nested government paths. The trailing slash
# pairs are intentional — some servers redirect missing-slash → trailing-slash.
_MAYOR_CANDIDATE_PATHS: tuple[str, ...] = (
    "/mayor",
    "/mayor/",
    "/mayors-office",
    "/mayors-office/",
    "/mayors_office",
    "/mayors-office/index.html",
    "/mayor-of-{slug}",
    "/government/mayor",
    "/government/mayors-office",
    "/government/mayor-and-city-council",
    "/government/elected-officials/mayor",
    "/departments/mayor",
    "/departments/mayors-office",
    "/departments/mayorsoffice",
    "/cos/mayor0/",  # Springfield, MA legacy pattern; cheap to keep.
    "/office-of-the-mayor",
    "/about/mayor",
)

_COUNCIL_CANDIDATE_PATHS: tuple[str, ...] = (
    "/city-council",
    "/citycouncil",
    "/council",
    "/government/city-council",
    "/government/council",
    "/departments/city-council",
    "/departments/citycouncil/members",
    "/elected-officials",
    "/commissioners",
    "/county-commission",
    "/board-of-commissioners",
)

# Anchors whose href OR visible text match this pattern are followed by the
# homepage-crawl fallback. Kept tight — broader patterns ("government", "officials")
# pull in too much noise and the council/mayor pages usually surface via these specific
# keywords on the homepage anyway.
_ANCHOR_KEYWORD_RE = re.compile(
    r"\b(?:mayor(?:'?s)?(?:[-_ ]office)?|city[-_ ]?council|town[-_ ]?council|"
    r"county[-_ ]?commission(?:ers?)?|board[-_ ]?of[-_ ]?commissioners|"
    r"elected[-_ ]officials)\b",
    re.IGNORECASE,
)


def _slug_from_homepage(homepage_url: str) -> str:
    host = (urlparse(homepage_url).netloc or "").lower()
    host = re.sub(r"^www\.", "", host)
    # cityofbigtimber.com -> bigtimber. somervillema.gov -> somerville.
    stem = host.split(".")[0]
    stem = re.sub(r"^(cityof|townof|city-of|town-of)", "", stem)
    stem = re.sub(r"(ma|al|ga|in|wa|wi|mt)$", "", stem)
    return stem or host


def candidate_urls(homepage_url: str, *, kind: str = "mayor") -> list[str]:
    """Return ordered candidate URLs for ``mayor`` or ``council`` pages."""
    if not homepage_url:
        return []
    paths = _MAYOR_CANDIDATE_PATHS if kind == "mayor" else _COUNCIL_CANDIDATE_PATHS
    slug = _slug_from_homepage(homepage_url)
    out: list[str] = []
    seen: set[str] = set()
    for p in paths:
        path = p.format(slug=slug) if "{slug}" in p else p
        url = urljoin(homepage_url, path)
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def probe_urls(urls: Iterable[str], *, session: requests.Session | None = None) -> list[str]:
    """
    HEAD each URL; return the ones that responded 200 deduped by *resolved* URL
    (after following redirects). Falls back to GET when HEAD returns 405/501.
    """
    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", _USER_AGENT)
    live: list[str] = []
    seen_resolved: set[str] = set()
    for url in urls:
        try:
            resp = sess.head(url, allow_redirects=True, timeout=_TIMEOUT_S)
            if resp.status_code in (405, 501):
                resp = sess.get(url, allow_redirects=True, timeout=_TIMEOUT_S)
            if resp.status_code != 200:
                continue
            resolved = resp.url
            if resolved in seen_resolved:
                continue
            seen_resolved.add(resolved)
            live.append(resolved)
        except requests.RequestException as exc:
            logger.debug("probe error %s: %s", url, exc)
    return live


def crawl_homepage_anchors(
    homepage_url: str,
    *,
    session: requests.Session | None = None,
    max_results: int = 12,
) -> list[str]:
    """
    Fetch homepage HTML; return absolute URLs of anchors whose href OR visible text
    matches the mayor/council/commission keyword pattern. Empty list if the fetch
    fails or no matching anchors are present.
    """
    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", _USER_AGENT)
    try:
        resp = sess.get(homepage_url, timeout=_TIMEOUT_S, allow_redirects=True)
        if resp.status_code != 200 or not resp.text:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        logger.debug("homepage fetch error %s: %s", homepage_url, exc)
        return []

    found: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        text = a.get_text(" ", strip=True)
        if not href:
            continue
        if not (_ANCHOR_KEYWORD_RE.search(href) or _ANCHOR_KEYWORD_RE.search(text)):
            continue
        abs_url = urljoin(resp.url, href)
        # Stay on the same host as the homepage; off-site links are usually socials.
        if urlparse(abs_url).netloc != urlparse(resp.url).netloc:
            continue
        if abs_url in seen:
            continue
        seen.add(abs_url)
        found.append(abs_url)
        if len(found) >= max_results:
            break
    return found


def discover_seed_urls(homepage_url: str) -> dict[str, list[str]]:
    """
    Combined two-tier discovery. Returns a dict with ``mayor`` and ``council`` lists.
    Each list contains URLs that responded 200 from the heuristic probe; if both come
    back empty, falls back to a single homepage-anchor crawl whose results are split
    into ``mayor`` vs ``council`` by URL/text inspection.
    """
    if not homepage_url:
        return {"mayor": [], "council": []}

    session = requests.Session()
    session.headers["User-Agent"] = _USER_AGENT

    mayor_live = probe_urls(candidate_urls(homepage_url, kind="mayor"), session=session)
    council_live = probe_urls(candidate_urls(homepage_url, kind="council"), session=session)

    if mayor_live or council_live:
        return {"mayor": mayor_live, "council": council_live}

    anchors = crawl_homepage_anchors(homepage_url, session=session)
    mayor_anchors = [u for u in anchors if re.search(r"mayor", u, re.IGNORECASE)]
    council_anchors = [u for u in anchors if u not in mayor_anchors]
    return {"mayor": mayor_anchors, "council": council_anchors}
