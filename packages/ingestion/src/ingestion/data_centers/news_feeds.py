"""Local news RSS/Atom feeds for the data center meeting finder (#549).

The feeds are listed in the dbt seed ``dbt_project/seeds/local_news_feeds.csv`` (one row
per feed: outlet, state, feed URL, and the date and result of its robots.txt check). The
loader (``python -m ingestion.data_centers.community_events --source rss``) reads every
enabled feed whose robots check allowed it, checks robots.txt again live before the first
request to each host, and keeps the items whose title or summary says "data center" or
names a tracked company or project. For each kept item the article page is read (when
robots.txt allows it, at most ``max_pages`` per feed) and only whole sentences that say a
meeting word, "data center", a tracked name or a project's place are kept, verbatim.

A feed URL may hold a ``{term}`` placeholder: an outlet's own topic feed
(``https://abc3340.com/topic/{term}.rss``). It is expanded once per tracked company name
and project place, URL-encoded, so a company's coverage is read without a search engine.

Refresh the seed's robots columns with::

    python -m ingestion.data_centers.news_feeds --check-robots
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote, urljoin
from xml.etree import ElementTree

import httpx
from loguru import logger

from ingestion.data_centers.community_events import (
    NewsItem,
    PoliteFetcher,
    is_blocked_host,
    main_content,
    matched_kinds,
    parse_rss_datetime,
    says_data_center,
    strip_html,
    verbatim_passages,
)

SEED_NAME = "local_news_feeds.csv"
SEED_COLUMNS = ("feed_id", "outlet", "state_code", "feed_url", "robots_checked_on", "robots_allowed",
                "enabled", "note")
TERM_PLACEHOLDER = "{term}"


def default_seed_path() -> Path:
    """``dbt_project/seeds/local_news_feeds.csv`` of the repository this module lives in."""
    from core_lib.paths import repo_root

    return repo_root(__file__) / "dbt_project" / "seeds" / SEED_NAME


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("true", "t", "1", "yes", "y")


@dataclass(frozen=True)
class LocalNewsFeed:
    feed_id: str
    outlet: str
    state_code: str
    feed_url: str
    robots_checked_on: Optional[date] = None
    robots_allowed: bool = False
    enabled: bool = True
    note: str = ""

    @property
    def is_template(self) -> bool:
        return TERM_PLACEHOLDER in self.feed_url

    @property
    def usable(self) -> bool:
        return bool(self.feed_url) and self.enabled and self.robots_allowed

    def csv_row(self) -> dict[str, str]:
        return {
            "feed_id": self.feed_id,
            "outlet": self.outlet,
            "state_code": self.state_code,
            "feed_url": self.feed_url,
            "robots_checked_on": self.robots_checked_on.isoformat() if self.robots_checked_on else "",
            "robots_allowed": "true" if self.robots_allowed else "false",
            "enabled": "true" if self.enabled else "false",
            "note": self.note,
        }


def read_feed_seed(path: Path | None = None) -> list[LocalNewsFeed]:
    path = path or default_seed_path()
    feeds = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            checked = (row.get("robots_checked_on") or "").strip()
            feeds.append(
                LocalNewsFeed(
                    feed_id=row["feed_id"].strip(),
                    outlet=row["outlet"].strip(),
                    state_code=row["state_code"].strip().upper(),
                    feed_url=(row.get("feed_url") or "").strip(),
                    robots_checked_on=date.fromisoformat(checked) if checked else None,
                    robots_allowed=_truthy(row.get("robots_allowed")),
                    enabled=_truthy(row.get("enabled") or "true"),
                    note=(row.get("note") or "").strip(),
                )
            )
    return feeds


def write_feed_seed(feeds: Iterable[LocalNewsFeed], path: Path | None = None) -> None:
    path = path or default_seed_path()
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SEED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for feed in feeds:
            writer.writerow(feed.csv_row())


def expand_feed_url(feed_url: str, terms: Iterable[str]) -> list[str]:
    """``feed_url`` itself, or one URL per term when it holds ``{term}`` (sorted, unique)."""
    if TERM_PLACEHOLDER not in feed_url:
        return [feed_url]
    clean = sorted({t.strip() for t in terms if t and len(t.strip()) >= 3})
    return [feed_url.replace(TERM_PLACEHOLDER, quote(t, safe="")) for t in clean]


def robots_probe_url(feed: LocalNewsFeed) -> str:
    """The URL whose robots.txt verdict stands for the feed (a template gets 'data center')."""
    return feed.feed_url.replace(TERM_PLACEHOLDER, quote("data center", safe=""))


# --- feed parsing ------------------------------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child_text(el: ElementTree.Element, *names: str) -> str:
    for child in el:
        if _local(child.tag) in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def parse_feed(body: str | bytes) -> list[dict[str, Any]]:
    """Items of an RSS 2.0, RSS 1.0 (RDF) or Atom feed as dicts: title, link, published,
    summary (raw HTML/text, verbatim from the feed)."""
    root = ElementTree.fromstring(body)
    out: list[dict[str, Any]] = []
    for el in root.iter():
        name = _local(el.tag)
        if name not in ("item", "entry"):
            continue
        link = ""
        for child in el:
            if _local(child.tag) != "link":
                continue
            href = child.get("href")
            if href and child.get("rel", "alternate") == "alternate":
                link = href.strip()
                break
            if (child.text or "").strip():
                link = child.text.strip()
                break
        if not link:
            guid = _child_text(el, "guid", "id")
            link = guid if guid.startswith("http") else ""
        out.append(
            {
                "title": strip_html(_child_text(el, "title")),
                "link": link,
                "published": _child_text(el, "pubDate", "published", "updated", "date"),
                "summary": _child_text(el, "description", "summary", "encoded", "content"),
            }
        )
    return out


def parse_feed_datetime(value: str | None) -> Optional[datetime]:
    """RFC 822 (RSS) or ISO 8601 (Atom, dc:date) as an aware datetime."""
    if not value:
        return None
    dt = parse_rss_datetime(value)
    if dt is not None:
        return dt
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def names_any(text: str, names: Iterable[str]) -> list[str]:
    """The tracked names ``text`` says, as whole words (case-sensitive: "Meta" not "metal")."""
    return [n for n in names if n and re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", text or "")]


def is_relevant(title: str, summary: str, names: Iterable[str]) -> bool:
    head = f"{title} {strip_html(summary)}"
    return says_data_center(head) or bool(names_any(head, names))


DATA_CENTER_TERMS = ("data center", "data centers", "data centre", "datacenter")


def article_passages(
    fetcher: PoliteFetcher, url: str, terms: Iterable[str]
) -> tuple[list[str], int]:
    """Verbatim sentences of an article page that say a meeting word or a term (robots-checked).

    Returns (passages, page_chars); ([], 0) when the page can't or mustn't be read.
    """
    if is_blocked_host(url) or not fetcher.allowed(url):
        return [], 0
    try:
        page = fetcher.get(url)
    except (PermissionError, httpx.HTTPError) as err:
        logger.warning("{}: article skipped ({})", url, err)
        return [], 0
    if page.status_code != 200 or "html" not in page.headers.get("content-type", "html"):
        return [], 0
    text = strip_html(main_content(page.text))
    return verbatim_passages(text, [*terms, *DATA_CENTER_TERMS], limit=6), len(text)


@dataclass(frozen=True)
class TrackedNames:
    """Names a local item must say to be kept, and the terms whose sentences are quoted."""

    companies: tuple[str, ...] = ()
    projects: tuple[str, ...] = ()
    places: tuple[str, ...] = ()

    @property
    def relevance_names(self) -> tuple[str, ...]:
        # project names only: a company name alone ("Google", "Meta") is in too much news
        return tuple(n for n in self.projects if n)

    @property
    def passage_terms(self) -> tuple[str, ...]:
        return tuple(n for n in (*self.companies, *self.projects, *self.places) if n)

    @property
    def topic_terms(self) -> tuple[str, ...]:
        return tuple(n for n in (*self.companies, *self.places) if n)


def fetch_local_feed(
    fetcher: PoliteFetcher,
    feed: LocalNewsFeed,
    names: TrackedNames,
    *,
    max_pages: int = 10,
    seen_urls: Optional[set[str]] = None,
) -> tuple[list[NewsItem], int]:
    """Items of one seed feed (all expansions of a template) that concern data centers.

    Returns (items, entries_read). ``seen_urls`` is shared across feeds so an article that
    is in several of an outlet's feeds is read once.
    """
    seen = seen_urls if seen_urls is not None else set()
    items: list[NewsItem] = []
    entries = 0
    pages = 0
    for url in expand_feed_url(feed.feed_url, names.topic_terms):
        try:
            resp = fetcher.get(url)
        except PermissionError as err:
            logger.warning("{}: {}", feed.feed_id, err)
            continue
        if resp.status_code != 200:
            logger.warning("{}: HTTP {} on {}", feed.feed_id, resp.status_code, url)
            continue
        try:
            parsed = parse_feed(resp.content)
        except ElementTree.ParseError as err:
            logger.warning("{}: not a feed ({}) at {}", feed.feed_id, err, url)
            continue
        entries += len(parsed)
        for it in parsed:
            title = it["title"]
            link = urljoin(url, it["link"]) if it["link"] else ""
            if not link or not title or is_blocked_host(link) or link in seen:
                continue
            if not is_relevant(title, it["summary"], names.relevance_names):
                continue
            seen.add(link)
            summary_text = strip_html(it["summary"])
            passages = verbatim_passages(summary_text, [*names.passage_terms, *DATA_CENTER_TERMS])
            page_chars = 0
            if pages < max_pages:
                pages += 1
                got, page_chars = article_passages(fetcher, link, names.passage_terms)
                passages = got or passages
            snippet = " … ".join(passages) or summary_text[:600] or title
            items.append(
                NewsItem(
                    source="rss",
                    query=url,
                    url=link,
                    title=title,
                    publisher=feed.outlet,
                    published_at=parse_feed_datetime(it["published"]),
                    snippet=snippet,
                    raw={"feed_id": feed.feed_id, "state_code": feed.state_code, "feed_url": url,
                         "published": it["published"], "page_chars": page_chars,
                         "kinds": matched_kinds(f"{title} {snippet}")},
                )
            )
    return items, entries


def check_robots(fetcher: PoliteFetcher, feeds: Iterable[LocalNewsFeed], today: date) -> list[LocalNewsFeed]:
    """Each feed with ``robots_checked_on`` = today and ``robots_allowed`` from a live check."""
    out = []
    for feed in feeds:
        if not feed.feed_url:
            out.append(feed)
            continue
        allowed = fetcher.allowed(robots_probe_url(feed))
        out.append(replace(feed, robots_checked_on=today, robots_allowed=allowed))
        logger.info("{}: robots {}", feed.feed_id, "allows" if allowed else "DISALLOWS")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the local news feed seed against robots.txt.")
    parser.add_argument("--check-robots", action="store_true", help="Re-check robots.txt and rewrite the seed.")
    parser.add_argument("--seed", type=Path, default=None, help=f"Seed CSV (default dbt_project/seeds/{SEED_NAME}).")
    args = parser.parse_args(argv)
    feeds = read_feed_seed(args.seed)
    if not args.check_robots:
        for f in feeds:
            logger.info("{} | {} | {} | robots {} on {} | {}", f.feed_id, f.state_code, f.feed_url or "-",
                        f.robots_allowed, f.robots_checked_on, "enabled" if f.enabled else "disabled")
        return 0
    checked = check_robots(PoliteFetcher(min_interval=3.0), feeds, date.today())
    write_feed_seed(checked, args.seed)
    logger.success("{} feeds checked, {} allowed", sum(1 for f in checked if f.feed_url),
                   sum(1 for f in checked if f.feed_url and f.robots_allowed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
