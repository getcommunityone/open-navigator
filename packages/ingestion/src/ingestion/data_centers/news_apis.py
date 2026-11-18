"""Optional keyed news and web search APIs for the data center meeting finder (#549).

Each provider reads its key from the environment (the repo ``.env``) and is skipped quietly
when the key is unset; no paid call is ever made, and no key is ever printed or logged
(``redact`` scrubs it from any error text).

  newsapi   NewsAPI.org ``/v2/everything`` (``NEWSAPI_KEY``). The free Developer plan is
            for development and testing, allows 100 requests a day and searches about the
            last month of articles. The key goes in the ``X-Api-Key`` header.
  guardian  The Guardian Open Platform ``/search`` (``GUARDIAN_API_KEY``). The free
            developer key is for non-commercial use, about 1 request a second and 500 a
            day. The key goes in the ``api-key`` parameter (the API has no header form).
  brave     Brave Search API ``/res/v1/web/search`` (``BRAVE_SEARCH_API_KEY``), to find
            announcement pages on city, county and company sites and local news. The key
            goes in the ``X-Subscription-Token`` header. Search result pages of search
            engines are never scraped; only this API is used.

The snippet kept for an item is the provider's own text for it (NewsAPI's description,
the Guardian's trail text, Brave's description), tags removed; for Brave hits the page
itself is then read when robots.txt allows it and its verbatim sentences replace it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

import httpx
from loguru import logger

from ingestion.data_centers.community_events import (
    KIND_TERMS,
    NewsItem,
    PoliteFetcher,
    is_blocked_host,
    strip_html,
)
from ingestion.data_centers.news_feeds import parse_feed_datetime

NEWSAPI_URL = "https://newsapi.org/v2/everything"
GUARDIAN_URL = "https://content.guardianapis.com/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

KEY_ENV = {"newsapi": "NEWSAPI_KEY", "guardian": "GUARDIAN_API_KEY", "brave": "BRAVE_SEARCH_API_KEY"}
# Seconds between calls to one provider (each provider's free-tier rate limit, with margin).
API_INTERVALS = {"newsapi.org": 2.0, "content.guardianapis.com": 1.5, "api.search.brave.com": 1.5}


def api_key(provider: str, env: Optional[dict[str, str]] = None) -> Optional[str]:
    """The provider's key from the environment, or None (unset or blank)."""
    value = (env if env is not None else os.environ).get(KEY_ENV[provider], "")
    return value.strip() or None


def redact(text: str, *secrets: Optional[str]) -> str:
    """``text`` with every secret replaced by ``***`` (for logging an error that may carry a URL)."""
    out = str(text)
    for s in secrets:
        if s:
            out = out.replace(s, "***")
    return out


@dataclass(frozen=True)
class SearchTarget:
    """A tracked company and (optionally) one of its projects and that project's place."""

    company: str
    project: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


def news_queries(targets: Iterable[SearchTarget]) -> list[str]:
    """Boolean news-API queries: one per meeting word, then one per company with the meeting words."""
    kinds = " OR ".join(f'"{k}"' for k in KIND_TERMS)
    queries = [f'"data center" AND "{k}"' for k in KIND_TERMS]
    for company in sorted({t.company for t in targets if t.company}):
        queries.append(f'"{company}" AND "data center" AND ({kinds})')
    return queries


def web_queries(targets: Iterable[SearchTarget]) -> list[str]:
    """Plain web-search queries: per project and per company-with-place, meeting-word first."""
    out: list[str] = []
    for t in targets:
        if t.project:
            out.append(f'"{t.project}" town hall')
        place = " ".join(p for p in (t.city, t.state) if p)
        if place:
            out.append(f'"{t.company}" data center community meeting {place}')
        elif not t.project:
            out.append(f'"{t.company}" data center town hall')
    return list(dict.fromkeys(out))


def _get_json(
    fetcher: PoliteFetcher, url: str, *, params: dict[str, str], headers: dict[str, str], secret: str
) -> Optional[dict[str, Any]]:
    """One API GET (spaced per host, no robots.txt: the provider's terms govern). None on failure."""
    try:
        resp = fetcher.get_api(url, params=params, headers=headers)
    except httpx.HTTPError as err:
        logger.warning("{}: {}", httpx.URL(url).host, redact(err, secret))
        return None
    if resp.status_code != 200:
        logger.warning("{}: HTTP {} {}", httpx.URL(url).host, resp.status_code,
                       redact(resp.text[:160], secret))
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def parse_newsapi(data: dict[str, Any], query: str) -> list[NewsItem]:
    items = []
    for art in data.get("articles") or []:
        url = (art.get("url") or "").strip()
        title = (art.get("title") or "").strip()
        if not url or not title or is_blocked_host(url) or title == "[Removed]":
            continue
        desc = strip_html(art.get("description") or "")
        items.append(NewsItem(
            source="newsapi", query=query, url=url, title=title,
            publisher=((art.get("source") or {}).get("name") or None),
            published_at=parse_feed_datetime(art.get("publishedAt")),
            snippet=desc or title,
            raw={k: art.get(k) for k in ("source", "author", "publishedAt", "description")},
        ))
    return items


def parse_guardian(data: dict[str, Any], query: str) -> list[NewsItem]:
    items = []
    for res in (data.get("response") or {}).get("results") or []:
        url = (res.get("webUrl") or "").strip()
        title = (res.get("webTitle") or "").strip()
        if not url or not title:
            continue
        trail = strip_html((res.get("fields") or {}).get("trailText") or "")
        items.append(NewsItem(
            source="guardian", query=query, url=url, title=title, publisher="The Guardian",
            published_at=parse_feed_datetime(res.get("webPublicationDate")),
            snippet=trail or title,
            raw={k: res.get(k) for k in ("id", "sectionName", "webPublicationDate")},
        ))
    return items


def parse_brave(data: dict[str, Any], query: str) -> list[NewsItem]:
    items = []
    for res in (data.get("web") or {}).get("results") or []:
        url = (res.get("url") or "").strip()
        title = strip_html(res.get("title") or "")
        if not url or not title or is_blocked_host(url):
            continue
        desc = strip_html(res.get("description") or "")
        host = (res.get("meta_url") or {}).get("hostname") or httpx.URL(url).host
        items.append(NewsItem(
            source="brave", query=query, url=url, title=title,
            publisher=((res.get("profile") or {}).get("name") or host or None),
            published_at=parse_feed_datetime(res.get("page_age")),
            snippet=desc or title,
            raw={"page_age": res.get("page_age"), "age": res.get("age"), "hostname": host},
        ))
    return items


def fetch_newsapi(fetcher: PoliteFetcher, key: str, query: str) -> list[NewsItem]:
    data = _get_json(fetcher, NEWSAPI_URL,
                     params={"q": query, "language": "en", "sortBy": "publishedAt", "pageSize": "100"},
                     headers={"X-Api-Key": key}, secret=key)
    return parse_newsapi(data, query) if data else []


def fetch_guardian(fetcher: PoliteFetcher, key: str, query: str) -> list[NewsItem]:
    data = _get_json(fetcher, GUARDIAN_URL,
                     params={"q": query, "page-size": "50", "order-by": "newest", "show-fields": "trailText",
                             "api-key": key},
                     headers={}, secret=key)
    return parse_guardian(data, query) if data else []


def fetch_brave(fetcher: PoliteFetcher, key: str, query: str) -> list[NewsItem]:
    data = _get_json(fetcher, BRAVE_URL, params={"q": query, "count": "20", "country": "us"},
                     headers={"X-Subscription-Token": key, "Accept": "application/json"}, secret=key)
    return parse_brave(data, query) if data else []


FETCHERS: dict[str, Callable[[PoliteFetcher, str, str], list[NewsItem]]] = {
    "newsapi": fetch_newsapi,
    "guardian": fetch_guardian,
    "brave": fetch_brave,
}


def run_provider(
    provider: str,
    fetcher: PoliteFetcher,
    queries: Iterable[str],
    *,
    env: Optional[dict[str, str]] = None,
) -> tuple[list[NewsItem], str]:
    """All items one provider returns for ``queries``, and a one-line report.

    No key -> ([], 'skipped (NEWSAPI_KEY not set)'); the key itself never appears.
    """
    key = api_key(provider, env)
    if not key:
        return [], f"skipped ({KEY_ENV[provider]} not set)"
    items: list[NewsItem] = []
    n = 0
    for q in queries:
        n += 1
        got = FETCHERS[provider](fetcher, key, q)
        logger.info("{} {!r}: {} items", provider, q, len(got))
        items.extend(got)
    return items, f"{len(items)} items from {n} queries"
