"""Find company-hosted data center community meetings in news and company announcements (#532, #549).

    python -m ingestion.data_centers.community_events               # fetch + land in bronze
    python -m ingestion.data_centers.community_events --dry-run     # fetch, print, don't write
    python -m ingestion.data_centers.community_events --source rss
    python -m ingestion.data_centers.community_events --source newsapi,guardian,brave
    python -m ingestion.data_centers.community_events --dsn URL     # write somewhere else

Developers hold their own town halls, open houses and information sessions about a data
center project. Local news announces and covers them, and some companies post them in
their press releases. This loader reads free sources and lands every item it finds
in ``bronze.bronze_data_center_news_item`` with its URL, title, publisher, published date
and a verbatim snippet. dbt (``stg_data_center_news_item`` ->
``data_center_community_event``) decides which items describe an event; nothing here
guesses a date, a place or a host.

Sources (no paid calls, no LLM):
  gdelt         the GDELT DOC 2.0 API (article list, last 3 months). GDELT asks for at most
                one request every 5 seconds; this loader waits 6 and backs off on HTTP 429.
                The snippet is the article's headline, which is all GDELT returns. Opt-in
                (``--source gdelt``): it answered only 429 for hours (#542).
  google_news   Google News RSS search. Read only when news.google.com/robots.txt allows the
                feed path for our User-Agent; today it disallows /rss, so this source is
                skipped and the run says so.
  company_feed  the press-release RSS feeds in ``public.mdm_organization_data_center``
                (press_feed_url). An item that names a meeting word, "data center" or one of
                the company's projects gets its release page read, and the sentences that
                say a meeting word or a project name are kept verbatim.
  rss           local news RSS/Atom feeds from the seed ``local_news_feeds.csv`` (#549), only
                those whose robots.txt check allowed them; see ``news_feeds``.
  newsapi, guardian, brave
                optional keyed APIs (``NEWSAPI_KEY``, ``GUARDIAN_API_KEY``,
                ``BRAVE_SEARCH_API_KEY``), skipped quietly when the key is unset; see
                ``news_apis``. Keys are never printed.

YouTube videos found by the YouTube Data API land in the same table from
``python -m ingestion.data_centers.video_search`` (source ``youtube_search``).

Every host's robots.txt is checked before the first request to it. The User-Agent names
this project and its repository and carries no personal details. Requests to the same host
are spaced by at least ``--min-interval`` seconds (GDELT: 6).

Terms of service: americansentiment.com and prophecygov.com forbid competitors' use and
are never fetched; an item linking to them is dropped.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Iterable, Optional
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx
from loguru import logger

USER_AGENT = (
    "open-navigator-civic-data/0.1 (data center community meeting finder; "
    "+https://github.com/getcommunityone/open-navigator)"
)
TABLE = "bronze.bronze_data_center_news_item"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
SOURCES = ("gdelt", "google_news", "company_feed", "rss", "newsapi", "guardian", "brave")
# GDELT is opt-in (it answered only HTTP 429 for hours, #542); keyed providers skip quietly
# when their key is unset.
DEFAULT_SOURCES = ("google_news", "company_feed", "rss", "newsapi", "guardian", "brave")

# The meeting words the issue names, matched case-insensitively as whole phrases.
KIND_TERMS: dict[str, str] = {
    "town hall": "town_hall",
    "community meeting": "community_meeting",
    "open house": "open_house",
    "information session": "information_session",
    "public meeting": "public_meeting",
}
DATA_CENTER_RE = re.compile(r"\bdata\s?cent(?:er|re)s?\b|\bdatacenters?\b|\bhyperscale", re.I)
# "town hall" also matches the one-word "townhall" (video titles use both)
KIND_RE = re.compile(
    r"\b(" + "|".join(re.escape(k).replace("town\\ hall", "town ?hall") for k in KIND_TERMS) + r")s?\b", re.I
)

# Sites whose terms forbid use by competitors, scraping or bulk copying: never fetched, items
# linking there dropped. Evidence (terms quoted, 25 Nov 2026):
# web_docs/docs/development/data-center-source-review.md (#956, #958).
BLOCKED_HOSTS = (
    "americansentiment.com",
    "prophecygov.com",
    "govmeet.us",  # no automated wholesale copying or redistribution without written agreement
    "dcmap.us",  # no bulk copying or scraping, no competing directory
    "cleanview.co",  # internal use only, no redistribution or competing dataset
    "geolocity.com",  # no bulk copying, republishing as a dataset, or scraping
    "zoninglabs.com",  # no scraping, redistribution or commercial use without permission
    "datacentermap.com",  # internal use only, never redistributed
)


# --- pure helpers (unit-tested) ----------------------------------------------------------


def is_blocked_host(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return any(host == h or host.endswith("." + h) for h in BLOCKED_HOSTS)


def matched_kinds(text: str) -> list[str]:
    """The meeting kinds a text names, e.g. ['town_hall'] (sorted, unique)."""
    return sorted({KIND_TERMS[re.sub(r"^townhall$", "town hall", m.group(1).lower())]
                   for m in KIND_RE.finditer(text or "")})


def says_data_center(text: str) -> bool:
    return bool(DATA_CENTER_RE.search(text or ""))


def news_item_id(source: str, url: str) -> str:
    return hashlib.md5(f"{source}|{url}".encode()).hexdigest()


def strip_html(fragment: str) -> str:
    """Visible text of an HTML fragment: tags and scripts dropped, entities decoded, spaces collapsed."""
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", fragment or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def main_content(page_html: str) -> str:
    """The page's ``<article>`` (else ``<main>``) element, so navigation and footers stay out
    of the snippet; else the page without its head, nav, header and footer."""
    for tag in ("article", "main"):
        m = re.search(rf"(?is)<{tag}\b[^>]*>(.*?)</{tag}>", page_html or "")
        if m and strip_html(m.group(1)):
            return m.group(1)
    # no article/main: drop the <head> (page title) and the page chrome
    return re.sub(r"(?is)<(head|nav|header|footer)\b.*?</\1>", " ", page_html or "")


# A sentence ends at . ! or ? before a capital letter or quote, but not after a short
# abbreviation ("Oct.", "Inc.", "St.") or a single initial.
_SENTENCE_RE = re.compile(
    r"(?<!\b[A-Z][a-z]\.)(?<!\b[A-Z][a-z]{2}\.)(?<!\b[A-Z]\.)(?<=[.!?])\s+(?=[A-Z\"“])"
)


def verbatim_passages(text: str, terms: Iterable[str], *, limit: int = 4, max_len: int = 600) -> list[str]:
    """Whole sentences of ``text`` that contain a meeting word or one of ``terms``, verbatim.

    Sentences are split on ., ! or ? followed by a capital (not after "Oct.", "Inc."); a
    sentence longer than
    ``max_len`` is cut at a word boundary and marked with an ellipsis.
    """
    wanted = [t for t in terms if t]
    pattern = KIND_RE.pattern
    if wanted:
        pattern += "|" + "|".join(r"\b" + re.escape(t) + r"\b" for t in wanted)
    rx = re.compile(pattern, re.I)
    out: list[str] = []
    for sentence in _SENTENCE_RE.split(text or ""):
        sentence = sentence.strip()
        if not sentence or not rx.search(sentence):
            continue
        if len(sentence) > max_len:
            sentence = sentence[:max_len].rsplit(" ", 1)[0] + " …"
        if sentence not in out:
            out.append(sentence)
        if len(out) >= limit:
            break
    return out


def parse_gdelt_datetime(value: str | None) -> Optional[datetime]:
    """GDELT ``seendate`` (``20261002T141500Z``) as an aware datetime."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_rss_datetime(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError, IndexError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class NewsItem:
    source: str
    query: str
    url: str
    title: str
    publisher: Optional[str]
    published_at: Optional[datetime]
    snippet: Optional[str]
    language: Optional[str] = None
    company_key: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def item_id(self) -> str:
        return news_item_id(self.source, self.url)

    def row(self) -> tuple:
        return (
            self.item_id,
            self.source,
            self.query,
            self.url,
            self.title,
            self.publisher,
            self.published_at,
            self.snippet,
            self.language,
            self.company_key,
            json.dumps(self.raw, ensure_ascii=False, default=str),
        )


def parse_gdelt(body: str, query: str) -> list[NewsItem]:
    """Articles from a GDELT DOC ``mode=artlist&format=json`` response ('{}' = none)."""
    data = json.loads(body or "{}")
    items: list[NewsItem] = []
    for art in data.get("articles") or []:
        url = (art.get("url") or "").strip()
        title = (art.get("title") or "").strip()
        if not url or not title or is_blocked_host(url):
            continue
        items.append(
            NewsItem(
                source="gdelt",
                query=query,
                url=url,
                title=title,
                publisher=(art.get("domain") or None),
                published_at=parse_gdelt_datetime(art.get("seendate")),
                snippet=title,
                language=art.get("language") or None,
                raw=art,
            )
        )
    return items


def parse_rss(body: str | bytes) -> list[dict[str, Any]]:
    """Items of an RSS 2.0 feed as dicts (title, link, pubDate, description, source)."""
    root = ElementTree.fromstring(body)
    out: list[dict[str, Any]] = []
    for item in root.iter("item"):
        source_el = item.find("source")
        out.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "pubDate": (item.findtext("pubDate") or "").strip(),
                "description": item.findtext("description") or "",
                "source": (source_el.text or "").strip() if source_el is not None and source_el.text else None,
            }
        )
    return out


def gdelt_queries(project_names: Iterable[str] = ()) -> list[str]:
    """One query per meeting word ("data center" + word, US sources), plus one per project name."""
    queries = [f'"data center" "{term}" sourcecountry:US' for term in KIND_TERMS]
    for name in sorted({n.strip() for n in project_names if n and len(n.strip()) >= 8}):
        queries.append(f'"{name}"')
    return queries


_CHALLENGE_RE = re.compile(
    r"Just a moment\.\.\.|Checking your browser|cf-chl|challenge-platform|Attention Required!|captcha", re.I
)


def looks_like_bot_challenge(body: str) -> bool:
    """True when a response is a bot-check page (Cloudflare etc.) rather than content."""
    return bool(_CHALLENGE_RE.search((body or "")[:5000]))


# --- polite HTTP -------------------------------------------------------------------------


class PoliteFetcher:
    """GETs with a descriptive User-Agent, robots.txt checks and per-host spacing."""

    def __init__(
        self,
        *,
        min_interval: float = 3.0,
        host_intervals: Optional[dict[str, float]] = None,
        client: Optional[httpx.Client] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self.host_intervals = host_intervals or {}
        self.client = client or httpx.Client(
            timeout=60.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
        self.sleep = sleep
        self._last: dict[str, float] = {}
        self._robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    def _wait(self, host: str) -> None:
        gap = self.host_intervals.get(host, self.min_interval)
        last = self._last.get(host)
        if last is not None:
            delay = gap - (time.monotonic() - last)
            if delay > 0:
                self.sleep(delay)
        self._last[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        """True when the host's robots.txt lets USER_AGENT fetch ``url`` (no robots.txt = allowed)."""
        if is_blocked_host(url):
            return False
        parts = urlsplit(url)
        host = parts.hostname or ""
        if host not in self._robots:
            robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
            parser: Optional[urllib.robotparser.RobotFileParser] = urllib.robotparser.RobotFileParser()
            try:
                self._wait(host)
                resp = self.client.get(robots_url)
                ctype = resp.headers.get("content-type", "")
                if resp.status_code in (401, 403) or resp.status_code >= 500:
                    # RFC 9309: unauthorized or a server error means "don't crawl"
                    parser.disallow_all = True  # type: ignore[union-attr]
                elif resp.status_code == 429 or ("html" in ctype and looks_like_bot_challenge(resp.text)):
                    # a rate limit or a bot challenge in place of robots.txt: stay out
                    parser.disallow_all = True  # type: ignore[union-attr]
                elif resp.status_code >= 400 or "html" in ctype:
                    parser = None  # no robots.txt: everything allowed
                else:
                    parser.parse(resp.text.splitlines())  # type: ignore[union-attr]
            except httpx.HTTPError as err:
                logger.warning("robots.txt for {} unreadable ({}); not fetching that host", host, err)
                parser = urllib.robotparser.RobotFileParser()
                parser.disallow_all = True
            self._robots[host] = parser
        parser = self._robots[host]
        return True if parser is None else parser.can_fetch(USER_AGENT, url)

    def get_api(
        self, url: str, *, params: Optional[dict[str, str]] = None, headers: Optional[dict[str, str]] = None
    ) -> httpx.Response:
        """GET a keyed API endpoint: spaced per host, no robots.txt (the provider's terms and
        rate limits govern an API, and its key authorises the call)."""
        host = urlsplit(url).hostname or ""
        self._wait(host)
        return self.client.get(url, params=params, headers=headers or {})

    def get(self, url: str, *, params: Optional[dict[str, str]] = None) -> httpx.Response:
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        host = urlsplit(url).hostname or ""
        self._wait(host)
        resp = self.client.get(url, params=params)
        final = str(resp.url)
        if resp.history and final != url and not self.allowed(final):
            # a redirect may not land somewhere robots.txt (or the ToS block list) forbids
            raise PermissionError(f"redirected to a disallowed URL: {final}")
        return resp


def fetch_gdelt(fetcher: PoliteFetcher, query: str, *, retries: int = 4, backoff: float = 30.0) -> list[NewsItem]:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": "250",
        "timespan": "3months",
        "sort": "datedesc",
    }
    for attempt in range(retries + 1):
        try:
            resp = fetcher.get(GDELT_URL, params=params)
        except httpx.TransportError as err:  # e.g. the server closed a kept-alive connection
            wait = backoff * (2**attempt)
            logger.warning("GDELT {} on {!r} (try {}/{}); waiting {:.0f}s", type(err).__name__, query,
                           attempt + 1, retries + 1, wait)
            fetcher.sleep(wait)
            continue
        body = resp.text.strip()
        if resp.status_code == 200 and body.startswith("{"):
            return parse_gdelt(body, query)
        if resp.status_code == 429 or body.startswith("Please limit requests"):
            wait = backoff * (2**attempt)
            logger.warning("GDELT rate limit on {!r} (try {}/{}); waiting {:.0f}s", query, attempt + 1, retries + 1, wait)
            fetcher.sleep(wait)
            continue
        logger.warning("GDELT {} on {!r}: {}", resp.status_code, query, body[:120])
        return []
    raise RuntimeError(f"GDELT gave no answer after {retries + 1} tries (rate limit or dropped connection): {query!r}")


def fetch_google_news(fetcher: PoliteFetcher, query: str) -> list[NewsItem]:
    url = GOOGLE_NEWS_RSS + "?" + httpx.QueryParams({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}).__str__()
    if not fetcher.allowed(url):
        raise PermissionError("news.google.com robots.txt disallows the RSS search path")
    resp = fetcher.get(url)
    resp.raise_for_status()
    items = []
    for it in parse_rss(resp.content):
        if not it["link"] or not it["title"] or is_blocked_host(it["link"]):
            continue
        items.append(
            NewsItem(
                source="google_news",
                query=query,
                url=it["link"],
                title=it["title"],
                publisher=it["source"],
                published_at=parse_rss_datetime(it["pubDate"]),
                snippet=strip_html(it["description"]) or it["title"],
                raw=it,
            )
        )
    return items


@dataclass(frozen=True)
class CompanyFeed:
    company_key: str
    company_name: str
    press_feed_url: str
    project_names: tuple[str, ...] = ()


def fetch_company_feed(fetcher: PoliteFetcher, feed: CompanyFeed, *, max_pages: int = 20) -> list[NewsItem]:
    resp = fetcher.get(feed.press_feed_url)
    resp.raise_for_status()
    items: list[NewsItem] = []
    pages = 0
    for it in parse_rss(resp.content):
        title, link = it["title"], it["link"]
        if not title or not link or is_blocked_host(link):
            continue
        desc = strip_html(it["description"])
        head = f"{title} {desc}"
        names_project = any(re.search(r"\b" + re.escape(n) + r"\b", head, re.I) for n in feed.project_names)
        if not (matched_kinds(head) or says_data_center(head) or names_project):
            continue
        snippet_parts = verbatim_passages(desc, feed.project_names)
        page_text = ""
        if pages < max_pages and fetcher.allowed(link):
            pages += 1
            try:
                page = fetcher.get(link)
            except (PermissionError, httpx.HTTPError) as err:
                # keep the item with the feed's own text rather than lose the whole feed
                logger.warning("{}: release page skipped ({})", link, err)
            else:
                if page.status_code == 200:
                    page_text = strip_html(main_content(page.text))
                    snippet_parts = verbatim_passages(page_text, feed.project_names) or snippet_parts
        items.append(
            NewsItem(
                source="company_feed",
                query=feed.press_feed_url,
                url=link,
                title=title,
                publisher=feed.company_name,
                published_at=parse_rss_datetime(it["pubDate"]),
                snippet=" … ".join(snippet_parts) or title,
                company_key=feed.company_key,
                raw={**it, "page_chars": len(page_text)},
            )
        )
    return items


# --- warehouse ---------------------------------------------------------------------------

CREATE_SQL = f"""
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS {TABLE} (
        news_item_id   text        PRIMARY KEY,
        source         text        NOT NULL,
        query          text        NOT NULL,
        url            text        NOT NULL,
        title          text        NOT NULL,
        publisher      text,
        published_at   timestamptz,
        snippet        text,
        language       text,
        company_key    text,
        raw            jsonb       NOT NULL,
        first_seen_at  timestamptz NOT NULL DEFAULT now(),
        last_seen_at   timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS ix_bronze_data_center_news_item_published
        ON {TABLE} (published_at DESC);
"""

UPSERT_SQL = f"""
    INSERT INTO {TABLE} (news_item_id, source, query, url, title, publisher, published_at,
                         snippet, language, company_key, raw)
    VALUES %s
    ON CONFLICT (news_item_id) DO UPDATE SET
        last_seen_at = now(),
        title        = EXCLUDED.title,
        snippet      = COALESCE(EXCLUDED.snippet, {TABLE}.snippet),
        published_at = COALESCE({TABLE}.published_at, EXCLUDED.published_at),
        raw          = EXCLUDED.raw
"""

FEEDS_SQL = """
    select c.company_key, c.company_name, c.press_feed_url,
           coalesce(array_agg(distinct p.project_name) filter (where p.project_name is not null), '{}')
    from public.mdm_organization_data_center as c
    left join public.data_center_project_company as pc on pc.master_org_id = c.master_org_id
    left join public.data_center_project as p on p.project_id = pc.project_id and p.project_source = 'curated'
    where c.press_feed_url is not null
    group by 1, 2, 3
    order by 1
"""

PROJECTS_SQL = "select project_name from public.data_center_project where project_source = 'curated'"


def _dsn(explicit: str | None = None) -> str:
    """``--dsn``, else a Postgres ``DATABASE_URL``, else the local warehouse. Neon is never read."""
    if explicit and explicit.strip():
        return explicit.strip()
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url.startswith(("postgresql://", "postgres://")):
        return url
    password = os.environ.get("POSTGRES_PASSWORD") or "password"
    return f"postgresql://postgres:{password}@localhost:5433/open_navigator"


def dedupe(items: Iterable[NewsItem]) -> list[NewsItem]:
    seen: dict[str, NewsItem] = {}
    for item in items:
        seen.setdefault(item.item_id, item)
    return list(seen.values())


TARGETS_SQL = """
    select c.company_name, p.project_name, p.city, p.county, p.state_code
    from public.mdm_organization_data_center as c
    left join public.data_center_project_company as pc on pc.master_org_id = c.master_org_id
    left join public.data_center_project as p on p.project_id = pc.project_id and p.project_source = 'curated'
    order by 1, 2
"""


def tracked_names(rows: Iterable[tuple]) -> Any:
    """``TrackedNames`` and ``SearchTarget``s from TARGETS_SQL rows (company, project, city, county, state)."""
    from ingestion.data_centers.news_apis import SearchTarget
    from ingestion.data_centers.news_feeds import TrackedNames

    rows = list(rows)
    companies = sorted({r[0] for r in rows if r[0]})
    projects = sorted({r[1] for r in rows if r[1]})
    places = sorted({p for r in rows for p in (r[2], r[3]) if p})
    targets = [SearchTarget(r[0], r[1], r[2] or r[3], r[4]) for r in rows if r[0]]
    return TrackedNames(tuple(companies), tuple(projects), tuple(places)), targets


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", "--sources", dest="sources", default=",".join(DEFAULT_SOURCES),
                        help=f"Comma list of {', '.join(SOURCES)} (default: {', '.join(DEFAULT_SOURCES)}).")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report, but don't write.")
    parser.add_argument("--min-interval", type=float, default=3.0, help="Seconds between requests to one host.")
    parser.add_argument("--gdelt-retries", type=int, default=4, help="Backoff tries on GDELT HTTP 429.")
    parser.add_argument("--max-pages", type=int, default=10, help="Article pages read per feed (rss, brave).")
    parser.add_argument("--feeds-seed", default="", help="local_news_feeds.csv (default: the dbt seed).")
    parser.add_argument("--dsn", default="", help="Postgres URL (default: local warehouse).")
    args = parser.parse_args(argv)
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    unknown = set(sources) - set(SOURCES)
    if unknown:
        parser.error(f"unknown source(s): {', '.join(sorted(unknown))}")

    import psycopg2
    from psycopg2.extras import execute_values

    dsn = _dsn(args.dsn)
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(FEEDS_SQL)
        feeds = [CompanyFeed(r[0], r[1], r[2], tuple(r[3])) for r in cur.fetchall()]
        cur.execute(PROJECTS_SQL)
        project_names = [r[0] for r in cur.fetchall()]
        cur.execute(TARGETS_SQL)
        names, targets = tracked_names(cur.fetchall())

    from ingestion.data_centers import news_apis, news_feeds

    fetcher = PoliteFetcher(min_interval=args.min_interval,
                            host_intervals={"api.gdeltproject.org": 6.0, **news_apis.API_INTERVALS})
    found: list[NewsItem] = []
    report: dict[str, str] = {}

    if "gdelt" in sources:
        n0 = len(found)
        failures = 0
        for query in gdelt_queries(project_names):
            try:
                got = fetch_gdelt(fetcher, query, retries=args.gdelt_retries)
            except (RuntimeError, PermissionError, httpx.HTTPError) as err:
                failures += 1
                logger.error("GDELT: {}", err)
                continue
            logger.info("GDELT {!r}: {} articles", query, len(got))
            found.extend(got)
        report["gdelt"] = f"{len(found) - n0} items" + (f", {failures} queries failed" if failures else "")

    if "google_news" in sources:
        n0 = len(found)
        try:
            for term in KIND_TERMS:
                found.extend(fetch_google_news(fetcher, f'"data center" "{term}"'))
            report["google_news"] = f"{len(found) - n0} items"
        except PermissionError as err:
            logger.warning("Google News skipped: {}", err)
            report["google_news"] = f"skipped ({err})"

    if "company_feed" in sources:
        n0 = len(found)
        for feed in feeds:
            try:
                got = fetch_company_feed(fetcher, feed)
            except (PermissionError, httpx.HTTPError, ElementTree.ParseError) as err:
                logger.warning("{} feed skipped: {}", feed.company_name, err)
                continue
            logger.info("{} feed: {} items", feed.company_name, len(got))
            found.extend(got)
        report["company_feed"] = f"{len(found) - n0} items from {len(feeds)} feeds"

    if "rss" in sources:
        from pathlib import Path

        seed = news_feeds.read_feed_seed(Path(args.feeds_seed) if args.feeds_seed else None)
        listed = [f for f in seed if f.feed_url]
        usable = [f for f in listed if f.usable]
        n0, entries, read = len(found), 0, 0
        seen: set[str] = set()
        for feed in usable:
            if not fetcher.allowed(news_feeds.robots_probe_url(feed)):
                logger.warning("{}: robots.txt now disallows the feed; skipped (re-run --check-robots)",
                               feed.feed_id)
                continue
            try:
                got, n = news_feeds.fetch_local_feed(fetcher, feed, names, max_pages=args.max_pages,
                                                     seen_urls=seen)
            except httpx.HTTPError as err:
                logger.warning("{}: feed skipped ({})", feed.feed_id, err)
                continue
            read += 1
            entries += n
            logger.info("{}: {} entries, {} about data centers", feed.feed_id, n, len(got))
            found.extend(got)
        report["rss"] = (f"{len(found) - n0} items about data centers from {entries} entries; "
                         f"{len(listed)} feeds in seed, {sum(1 for f in listed if f.robots_allowed)} robots-allowed, "
                         f"{len(usable)} enabled, {read} read")

    for provider in ("newsapi", "guardian", "brave"):
        if provider not in sources:
            continue
        queries = news_apis.web_queries(targets) if provider == "brave" else news_apis.news_queries(targets)
        got, line = news_apis.run_provider(provider, fetcher, queries)
        if provider == "brave":
            pages = 0
            for item in got:
                if pages >= args.max_pages * 3:
                    break
                pages += 1
                passages, chars = news_feeds.article_passages(fetcher, item.url, names.passage_terms)
                if passages:
                    item.snippet = " … ".join(passages)
                    item.raw["page_chars"] = chars
        found.extend(got)
        report[provider] = line

    items = dedupe(found)
    with_kind = sum(1 for i in items if matched_kinds(f"{i.title} {i.snippet or ''}"))
    for source, line in report.items():
        logger.info("{}: {}", source, line)
    logger.info("{} unique items, {} naming a meeting word", len(items), with_kind)

    if args.dry_run:
        for i in items:
            logger.info("[{}] {} | {} | {}", i.source, i.published_at, i.publisher, i.title)
        logger.success("Dry run: nothing written")
        return 0

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(CREATE_SQL)
        if items:
            execute_values(cur, UPSERT_SQL, [i.row() for i in items], page_size=200)
        conn.commit()
    logger.success("{}: {} items landed", TABLE, len(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
