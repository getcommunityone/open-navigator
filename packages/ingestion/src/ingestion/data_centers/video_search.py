"""Search YouTube (Data API v3) for company-hosted data center meetings and their coverage (#549).

    python -m ingestion.data_centers.video_search                  # due searches, land hits
    python -m ingestion.data_centers.video_search --dry-run        # search, print, don't write
    python -m ingestion.data_centers.video_search --query '"Applied Digital" Brookwood town hall'
    python -m ingestion.data_centers.video_search --fetch-captions # captions of confirmed recordings

The same way meetings of governments are found: for every tracked project in
``public.data_center_project`` and every company in ``public.mdm_organization_data_center``
this asks the YouTube Data API ``search.list`` (the client and ``YOUTUBE_API_KEY`` that
channel discovery uses) for queries such as ``"<project>" town hall``,
``"<company>" community meeting <city or county> <state>`` and
``"<company>" data center <city>``, limited to videos published since the project was
announced (else the last 18 months). ``videos.list`` then reads each hit's full
description.

Every hit lands in ``bronze.bronze_data_center_news_item`` (source ``youtube_search``):
video URL, title, channel (publisher), published date, the description verbatim (snippet)
and the query, with the video and channel ids in ``raw``. dbt matches it to a project and
event with the #532 rules (company or project name and place in the title or
description) and labels a local TV news channel's video as coverage, not the meeting.

Quota: ``search.list`` costs 100 of the 10,000 free daily units, ``videos.list`` 1. A run
does at most ``--budget`` searches (default 80) per Pacific-time quota day, counted in
``bronze.bronze_data_center_video_search_log``; a query searched within
``--refresh-days`` is not repeated, so the next run (or the next day) resumes where this one
stopped. HTTP 403 ``quotaExceeded`` stops the run. A ``--dry-run`` writes no hits but still
records its searches in the log, since they spent quota.

VPN: the Data API is googleapis.com, which ``scrapers.youtube.vpn_guard`` does not treat as
YouTube; each call goes through ``require_vpn_for_url`` so the guard decides. Captions are
fetched only with ``--fetch-captions``, through the existing caption client
(``scrapers.youtube.transcript_api_client``: VPN guard, cookies) and written by the
existing ``upsert_bronze_transcript`` into ``bronze.bronze_event_youtube_transcript``.
The key is never printed.
"""

from __future__ import annotations

import argparse
import html
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional
from zoneinfo import ZoneInfo

import httpx
from loguru import logger

from ingestion.data_centers.community_events import (
    CREATE_SQL as NEWS_CREATE_SQL,
    TABLE as NEWS_TABLE,
    UPSERT_SQL as NEWS_UPSERT_SQL,
    USER_AGENT,
    NewsItem,
    _dsn,
    dedupe,
)
from ingestion.data_centers.news_apis import redact
from ingestion.data_centers.news_feeds import parse_feed_datetime

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
SOURCE = "youtube_search"
LOG_TABLE = "bronze.bronze_data_center_video_search_log"
SEARCH_COST = 100
DEFAULT_BUDGET = 80
LOOKBACK = timedelta(days=548)  # 18 months
QUOTA_TZ = ZoneInfo("America/Los_Angeles")  # the Data API quota resets at Pacific midnight


class QuotaExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectTarget:
    company: str
    project: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    announced_on: Optional[date] = None


@dataclass(frozen=True)
class VideoQuery:
    query: str
    published_after: date


def quota_day(now: Optional[datetime] = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(QUOTA_TZ).date()


def video_queries(targets: Iterable[ProjectTarget], today: date) -> list[VideoQuery]:
    """The search queries for tracked projects and companies, unique, in a stable order.

    Per project: ``"<project>" town hall``; with a place, ``"<company>" community meeting
    <city or county> <state>``; with a city, ``"<company>" data center <city>``. A company
    with no project gets ``"<company>" data center town hall``. Each searches from the
    project's announced date, never earlier than 18 months ago.
    """
    floor = today - LOOKBACK
    out: dict[str, date] = {}

    def add(q: str, since: Optional[date]) -> None:
        after = max(since, floor) if since else floor
        out[q] = min(out.get(q, after), after)

    for t in sorted(targets, key=lambda t: (t.company, t.project or "")):
        if t.project:
            add(f'"{t.project}" town hall', t.announced_on)
            place = t.city or t.county
            if place:
                add(f'"{t.company}" community meeting {place} {t.state or ""}'.strip(), t.announced_on)
            if t.city:
                add(f'"{t.company}" data center {t.city}', t.announced_on)
        else:
            add(f'"{t.company}" data center town hall', None)
    return [VideoQuery(q, d) for q, d in out.items()]


def due_queries(
    queries: list[VideoQuery],
    last_searched: dict[str, datetime],
    *,
    budget_left: int,
    refresh_days: int,
    now: datetime,
) -> list[VideoQuery]:
    """Queries to run now: never searched first, then the longest-ago searched past the
    refresh window, at most ``budget_left``."""
    if budget_left <= 0:
        return []
    cutoff = now - timedelta(days=refresh_days)
    never = [q for q in queries if q.query not in last_searched]
    stale = sorted((q for q in queries if q.query in last_searched and last_searched[q.query] < cutoff),
                   key=lambda q: last_searched[q.query])
    return (never + stale)[:budget_left]


def rfc3339(d: date) -> str:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_search(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Video hits of a ``search.list`` response: video_id, channel_id, channel, title,
    published_at, description (the API escapes HTML entities; they are decoded)."""
    hits = []
    for item in data.get("items") or []:
        vid = (item.get("id") or {}).get("videoId")
        sn = item.get("snippet") or {}
        if not vid:
            continue
        hits.append({
            "video_id": vid,
            "channel_id": sn.get("channelId"),
            "channel": html.unescape(sn.get("channelTitle") or "") or None,
            "title": html.unescape(sn.get("title") or "").strip(),
            "published_at": sn.get("publishedAt"),
            "description": html.unescape(sn.get("description") or ""),
            "live": sn.get("liveBroadcastContent"),
        })
    return hits


def parse_videos(data: dict[str, Any]) -> dict[str, str]:
    """video_id -> full description from a ``videos.list part=snippet`` response."""
    return {it["id"]: (it.get("snippet") or {}).get("description") or ""
            for it in data.get("items") or [] if it.get("id")}


def hit_item(hit: dict[str, Any], query: VideoQuery, description: Optional[str] = None) -> NewsItem:
    desc = (description if description is not None else hit["description"]).strip()
    url = f"https://www.youtube.com/watch?v={hit['video_id']}"
    return NewsItem(
        source=SOURCE,
        query=query.query,
        url=url,
        title=hit["title"],
        publisher=hit["channel"],
        published_at=parse_feed_datetime(hit["published_at"]),
        snippet=desc[:4000] or None,
        raw={"video_id": hit["video_id"], "channel_id": hit["channel_id"], "channel_title": hit["channel"],
             "live_broadcast_content": hit["live"], "query": query.query,
             "published_after": query.published_after.isoformat()},
    )


class DataApi:
    """The YouTube Data API v3 over httpx, spaced, the key only in the request parameters."""

    def __init__(self, key: str, *, client: Optional[httpx.Client] = None, pause: float = 1.0,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._key = key
        self.client = client or httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT})
        self.pause = pause
        self.sleep = sleep
        self._last = 0.0

    def _get(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        from scrapers.youtube.vpn_guard import require_vpn_for_url

        require_vpn_for_url(url)  # googleapis.com: the guard decides (no-op today)
        gap = self.pause - (time.monotonic() - self._last)
        if gap > 0:
            self.sleep(gap)
        self._last = time.monotonic()
        try:
            resp = self.client.get(url, params={**params, "key": self._key})
        except httpx.HTTPError as err:
            raise RuntimeError(redact(f"{type(err).__name__}: {err}", self._key)) from None
        if resp.status_code == 403 and "quotaExceeded" in resp.text:
            raise QuotaExceeded("YouTube Data API daily quota exceeded")
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {redact(resp.text[:200], self._key)}")
        return resp.json()

    def search(self, q: VideoQuery, max_results: int = 25) -> list[dict[str, Any]]:
        return parse_search(self._get(SEARCH_URL, {
            "part": "snippet", "q": q.query, "type": "video", "maxResults": str(max_results),
            "publishedAfter": rfc3339(q.published_after), "regionCode": "US", "relevanceLanguage": "en",
            "order": "relevance",
        }))

    def descriptions(self, video_ids: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for i in range(0, len(video_ids), 50):
            out.update(parse_videos(self._get(VIDEOS_URL, {"part": "snippet", "id": ",".join(video_ids[i:i + 50])})))
        return out


LOG_CREATE_SQL = f"""
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
        query            text        PRIMARY KEY,
        published_after  date        NOT NULL,
        searched_at      timestamptz NOT NULL,
        quota_day        date        NOT NULL,
        searches_today   integer     NOT NULL DEFAULT 1,
        result_count     integer     NOT NULL,
        status           text        NOT NULL
    );
"""
LOG_UPSERT_SQL = f"""
    INSERT INTO {LOG_TABLE} (query, published_after, searched_at, quota_day, result_count, status)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (query) DO UPDATE SET
        published_after = EXCLUDED.published_after,
        searches_today  = CASE WHEN {LOG_TABLE}.quota_day = EXCLUDED.quota_day
                               THEN {LOG_TABLE}.searches_today + 1 ELSE 1 END,
        searched_at     = EXCLUDED.searched_at,
        quota_day       = EXCLUDED.quota_day,
        result_count    = EXCLUDED.result_count,
        status          = EXCLUDED.status
"""
LOG_READ_SQL = f"select query, searched_at, quota_day, searches_today from {LOG_TABLE}"

TARGETS_SQL = """
    select c.company_name, p.project_name, p.city, p.county, p.state_code, p.announced_on
    from public.mdm_organization_data_center as c
    left join public.data_center_project_company as pc on pc.master_org_id = c.master_org_id
    left join public.data_center_project as p on p.project_id = pc.project_id and p.project_source = 'curated'
    order by 1, 2
"""

RECORDINGS_SQL = """
    select distinct substring(e.recording_url from '(?:v=|youtu\\.be/|/live/)([A-Za-z0-9_-]{11})') as video_id
    from public.data_center_community_event as e
    left join bronze.bronze_event_youtube_transcript as t
        on t.video_id = substring(e.recording_url from '(?:v=|youtu\\.be/|/live/)([A-Za-z0-9_-]{11})')
       and t.has_transcript
    where e.status = 'confirmed' and e.recording_url ~ '(youtube\\.com|youtu\\.be)' and t.video_id is null
"""


def fetch_captions(dsn: str, cookies: Optional[str]) -> int:
    """Captions of confirmed meeting recordings, via the existing caption client and bronze upsert."""
    import psycopg2

    from scrapers.youtube.backfill_jurisdiction_transcripts import upsert_bronze_transcript
    from scrapers.youtube.transcript_api_client import (
        fetch_transcript_from_api,
        format_transcript_error,
        resolve_cookies_path,
    )
    from scrapers.youtube.vpn_guard import VPN_EXIT_CODE, VpnRequiredError, require_vpn

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(RECORDINGS_SQL)
        video_ids = [r[0] for r in cur.fetchall() if r[0]]
    logger.info("{} confirmed meeting recordings without captions", len(video_ids))
    if not video_ids:
        return 0
    try:
        require_vpn()
    except VpnRequiredError as err:
        logger.error("Captions skipped: {}", err)
        return VPN_EXIT_CODE
    cookies_path = resolve_cookies_path(cookies)
    got = 0
    conn = psycopg2.connect(dsn)
    try:
        for vid in video_ids:
            try:
                payload = fetch_transcript_from_api(vid, cookies_file=cookies_path)
            except VpnRequiredError as err:
                logger.error("VPN dropped; captions stopped: {}", err)
                return VPN_EXIT_CODE
            except Exception as err:  # the caption client raises its own error types
                logger.warning("{}: no captions ({})", vid, format_transcript_error(err, max_len=200))
                continue
            upsert_bronze_transcript(conn, vid, payload)
            got += 1
            time.sleep(3.0)
    finally:
        conn.close()
    logger.success("{} caption tracks written to bronze.bronze_event_youtube_transcript", got)
    return 0


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Search and report, but don't write.")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="Most searches per quota day.")
    parser.add_argument("--refresh-days", type=int, default=7, help="Don't repeat a query searched this recently.")
    parser.add_argument("--max-results", type=int, default=25, help="Results per search (max 50).")
    parser.add_argument("--query", action="append", default=[],
                        help="An extra query to search (repeatable); searched over the last 18 months.")
    parser.add_argument("--only-queries", action="store_true", help="Search only the --query queries.")
    parser.add_argument("--fetch-captions", action="store_true",
                        help="Fetch captions of confirmed meeting recordings (VPN guard, cookies) and stop.")
    parser.add_argument("--cookies", default=None, help="cookies.txt for captions (default: repo youtube_cookies.txt).")
    parser.add_argument("--dsn", default="", help="Postgres URL (default: local warehouse).")
    args = parser.parse_args(argv)

    import psycopg2
    from psycopg2.extras import execute_values

    dsn = _dsn(args.dsn)
    if args.fetch_captions:
        return fetch_captions(dsn, args.cookies)

    key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    if not key:
        logger.warning("YOUTUBE_API_KEY not set; video search skipped")
        return 0

    now = datetime.now(timezone.utc)
    today_q = quota_day(now)
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(LOG_CREATE_SQL)
        conn.commit()
        cur.execute(LOG_READ_SQL)
        log = cur.fetchall()
        targets: list[ProjectTarget] = []
        if not args.only_queries:
            cur.execute(TARGETS_SQL)
            targets = [ProjectTarget(*r) for r in cur.fetchall()]
    last = {r[0]: r[1] for r in log}
    used_today = sum(r[3] for r in log if r[2] == today_q)

    extra = [VideoQuery(q.strip(), now.date() - LOOKBACK) for q in args.query if q.strip()]
    planned = extra + [q for q in video_queries(targets, now.date()) if q.query not in {e.query for e in extra}]
    # an explicit --query always runs (within budget), even if it was searched recently
    forced = list(extra)
    rest = due_queries([q for q in planned if q not in forced], last,
                       budget_left=args.budget - used_today - len(forced), refresh_days=args.refresh_days, now=now)
    todo = (forced + rest)[: max(0, args.budget - used_today)]
    logger.info("{} queries planned, {} searches used today ({}), {} to run (~{} quota units)",
                len(planned), used_today, today_q, len(todo), len(todo) * SEARCH_COST)

    api = DataApi(key)
    found: list[NewsItem] = []
    log_rows: list[tuple] = []
    try:
        for q in todo:
            try:
                hits = api.search(q, args.max_results)
            except QuotaExceeded as err:
                logger.warning("{}; stopping, the rest resume next quota day", err)
                break
            except RuntimeError as err:
                logger.warning("search {!r} failed: {}", q.query, err)
                continue
            descs = api.descriptions([h["video_id"] for h in hits]) if hits else {}
            items = [hit_item(h, q, descs.get(h["video_id"])) for h in hits if h["title"]]
            logger.info("{!r} (since {}): {} videos", q.query, q.published_after, len(items))
            found.extend(items)
            log_rows.append((q.query, q.published_after, datetime.now(timezone.utc), today_q, len(items), "ok"))
    finally:
        items = dedupe(found)
        with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
            # searches spend quota even in a dry run, so the log is always kept
            for row in log_rows:
                cur.execute(LOG_UPSERT_SQL, row if not args.dry_run else (*row[:5], "dry_run"))
            if not args.dry_run:
                cur.execute(NEWS_CREATE_SQL)
                if items:
                    execute_values(cur, NEWS_UPSERT_SQL, [i.row() for i in items], page_size=200)
            conn.commit()
        if args.dry_run:
            for i in items:
                logger.info("[{}] {} | {} | {}", i.query, i.published_at, i.publisher, i.title)
            logger.success("Dry run: {} videos from {} searches; only the quota log written", len(items),
                           len(log_rows))
        else:
            logger.success("{}: {} videos landed from {} searches", NEWS_TABLE, len(items), len(log_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
