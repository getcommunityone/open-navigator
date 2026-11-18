"""Search YouTube for recordings of company-hosted data center meetings (#532).

    python -m ingestion.data_centers.recording_candidates             # search + land in bronze
    python -m ingestion.data_centers.recording_candidates --dry-run   # search, print, don't write

For each confirmed ``public.data_center_community_event`` with an event date and a place,
this runs a YouTube search (yt-dlp's ``ytsearch``, metadata only, nothing downloaded) for
the host company, the place and the meeting word, and keeps a video as a *candidate* when
its title names the host company or the place and it was published from 3 days before to
30 days after the meeting. Candidates land in
``bronze.bronze_data_center_event_recording_candidate`` for review; none is attached to
the event.

YouTube is reached only through the VPN guard (``scrapers.youtube.vpn_guard.require_vpn``,
#488). When the guard fails the run stops with exit code 5 and searches nothing.
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from loguru import logger

TABLE = "bronze.bronze_data_center_event_recording_candidate"
KIND_WORDS = {
    "town_hall": "town hall",
    "community_meeting": "community meeting",
    "open_house": "open house",
    "information_session": "information session",
    "public_meeting": "public meeting",
}
WINDOW_BEFORE = timedelta(days=3)
WINDOW_AFTER = timedelta(days=30)


@dataclass(frozen=True)
class Event:
    community_event_id: str
    host_name: str
    city: Optional[str]
    state: Optional[str]
    event_kind: str
    event_date: date


def search_query(event: Event) -> str:
    place = event.city or event.state or ""
    return f"{event.host_name} {place} data center {KIND_WORDS.get(event.event_kind, 'meeting')}".strip()


def match_reason(event: Event, title: str, published_on: Optional[date]) -> Optional[str]:
    """Why a search result is a candidate, or None when it isn't one."""
    if published_on is None:
        return None
    if not (event.event_date - WINDOW_BEFORE <= published_on <= event.event_date + WINDOW_AFTER):
        return None
    low = (title or "").lower()
    named = [w for w in (event.host_name, event.city) if w and w.lower() in low]
    if not named:
        return None
    return "title names " + " and ".join(named) + f"; published {published_on.isoformat()}"


def _published_on(entry: dict[str, Any]) -> Optional[date]:
    raw = entry.get("upload_date")
    if raw and len(str(raw)) == 8:
        try:
            return datetime.strptime(str(raw), "%Y%m%d").date()
        except ValueError:
            return None
    ts = entry.get("timestamp") or entry.get("release_timestamp")
    if ts:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
    return None


def youtube_search(query: str, limit: int = 15) -> list[dict[str, Any]]:
    """Metadata of the top YouTube results for ``query`` (VPN guard checked by the caller)."""
    import yt_dlp

    opts = {"quiet": True, "skip_download": True, "extract_flat": False, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    return [e for e in (info or {}).get("entries") or [] if e]


def candidates_for(event: Event, entries: Iterable[dict[str, Any]], query: str) -> list[tuple]:
    rows = []
    for e in entries:
        url = e.get("webpage_url") or (f"https://www.youtube.com/watch?v={e['id']}" if e.get("id") else None)
        if not url:
            continue
        published = _published_on(e)
        reason = match_reason(event, e.get("title") or "", published)
        if reason:
            rows.append((event.community_event_id, url, e.get("title"), e.get("channel") or e.get("uploader"),
                         published, query, reason))
    return rows


CREATE_SQL = f"""
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS {TABLE} (
        community_event_id text        NOT NULL,
        video_url          text        NOT NULL,
        title              text,
        channel            text,
        published_on       date,
        query              text        NOT NULL,
        match_reason       text        NOT NULL,
        searched_at        timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (community_event_id, video_url)
    );
"""

UPSERT_SQL = f"""
    INSERT INTO {TABLE} (community_event_id, video_url, title, channel, published_on, query, match_reason)
    VALUES %s
    ON CONFLICT (community_event_id, video_url) DO UPDATE SET
        title = EXCLUDED.title, match_reason = EXCLUDED.match_reason, searched_at = now()
"""

EVENTS_SQL = """
    select community_event_id, host_name, city, state, event_kind, event_date
    from public.data_center_community_event
    where status = 'confirmed' and event_date is not null and host_name is not null
      and (city is not null or state is not null)
    order by event_date desc
"""


def _dsn(explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url.startswith(("postgresql://", "postgres://")):
        return url
    password = os.environ.get("POSTGRES_PASSWORD") or "password"
    return f"postgresql://postgres:{password}@localhost:5433/open_navigator"


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=15, help="Search results per event.")
    parser.add_argument("--pause", type=float, default=5.0, help="Seconds between searches.")
    parser.add_argument("--dsn", default="")
    args = parser.parse_args(argv)

    import psycopg2
    from psycopg2.extras import execute_values

    dsn = _dsn(args.dsn)
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(EVENTS_SQL)
        events = [Event(*r) for r in cur.fetchall()]
    logger.info("{} confirmed events with a date and a place", len(events))
    if not events:
        logger.success("Nothing to search")
        return 0

    from scrapers.youtube.vpn_guard import VPN_EXIT_CODE, VpnRequiredError, require_vpn

    try:
        require_vpn()
    except VpnRequiredError as err:
        logger.error("Recording search skipped: {}", err)
        return VPN_EXIT_CODE

    rows: list[tuple] = []
    for i, event in enumerate(events):
        if i:
            time.sleep(args.pause)
        try:
            require_vpn()  # re-checked (cached) before every search
        except VpnRequiredError as err:
            logger.error("VPN dropped; recording search stopped: {}", err)
            return VPN_EXIT_CODE
        query = search_query(event)
        try:
            entries = youtube_search(query, args.limit)
        except Exception as err:  # yt-dlp raises its own error types
            logger.warning("Search failed for {!r}: {}", query, err)
            continue
        got = candidates_for(event, entries, query)
        logger.info("{!r}: {} results, {} candidates", query, len(entries), len(got))
        rows.extend(got)

    if args.dry_run:
        for r in rows:
            logger.info("{} | {} | {}", r[0][:8], r[1], r[2])
        return 0
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(CREATE_SQL)
        if rows:
            execute_values(cur, UPSERT_SQL, rows)
        conn.commit()
    logger.success("{}: {} candidates landed", TABLE, len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
