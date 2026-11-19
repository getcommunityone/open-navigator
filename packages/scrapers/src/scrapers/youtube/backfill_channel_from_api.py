"""Backfill ``bronze.bronze_event_youtube`` from the YouTube Data API uploads playlist.

Uses ``googleapis.com`` only (no youtube.com HTML / caption fetch), so it does not
require the Surfshark VPN guard used by the scraper path (#488). Use this to close
catalog gaps when a channel posted but discovery did not run (#562).

Example::

    python -m scrapers.youtube.backfill_channel_from_api \\
        --channel-id UC74dczS0B3MhDhUHp2ZGRPA \\
        --jurisdiction-id tuscaloosa_0177256 \\
        --jurisdiction-name Tuscaloosa \\
        --state AL \\
        --published-after 2026-06-23 \\
        --published-before 2026-11-16
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.parse
import urllib.request
import json
from datetime import datetime
from typing import Any

import psycopg2
from dotenv import load_dotenv
from loguru import logger

from scrapers.youtube.channel_type_normalize import normalize_channel_type


def _iso_duration_minutes(iso: str | None) -> int | None:
    if not iso:
        return None
    m = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<mins>\d+)M)?(?:(?P<secs>\d+)S)?)?",
        iso,
    )
    if not m:
        return None
    days = int(m.group("days") or 0)
    hours = int(m.group("hours") or 0)
    mins = int(m.group("mins") or 0)
    secs = int(m.group("secs") or 0)
    total = days * 24 * 60 + hours * 60 + mins + (1 if secs else 0)
    return total or None


def _api_get(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def list_uploads(
    api_key: str,
    channel_id: str,
    *,
    published_after: str | None,
    published_before: str | None,
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    uploads = "UU" + channel_id[2:] if channel_id.startswith("UC") else channel_id
    out: list[dict[str, Any]] = []
    token: str | None = None
    for _ in range(max_pages):
        params: dict[str, str] = {
            "part": "snippet,contentDetails",
            "playlistId": uploads,
            "maxResults": "50",
            "key": api_key,
        }
        if token:
            params["pageToken"] = token
        data = _api_get("playlistItems", params)
        for it in data.get("items", []):
            sn = it["snippet"]
            published = (sn.get("publishedAt") or "")[:10]
            if not published:
                continue
            # Uploads playlist is newest-first.
            if published_before and published > published_before:
                continue
            if published_after and published < published_after:
                return out
            out.append(
                {
                    "video_id": sn["resourceId"]["videoId"],
                    "title": sn.get("title"),
                    "description": sn.get("description") or "",
                    "published_at": sn.get("publishedAt"),
                }
            )
        token = data.get("nextPageToken")
        if not token:
            break
    return out


def enrich_videos(api_key: str, video_ids: list[str]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        data = _api_get(
            "videos",
            {
                "part": "snippet,contentDetails",
                "id": ",".join(chunk),
                "key": api_key,
            },
        )
        for it in data.get("items", []):
            sn = it["snippet"]
            by_id[it["id"]] = {
                "title": sn.get("title"),
                "description": (sn.get("description") or "")[:5000],
                "published_at": sn.get("publishedAt"),
                "channel_id": sn.get("channelId"),
                "channel_title": sn.get("channelTitle"),
                "duration_minutes": _iso_duration_minutes(
                    (it.get("contentDetails") or {}).get("duration")
                ),
            }
    return by_id


def upsert_rows(
    conn,
    rows: list[dict[str, Any]],
    *,
    jurisdiction_id: str,
    jurisdiction_name: str,
    jurisdiction_type: str,
    state_code: str,
    state: str,
    city: str,
    channel_id: str,
    channel_type: str,
) -> int:
    channel_type = normalize_channel_type(channel_type)
    sql = """
        INSERT INTO bronze.bronze_event_youtube AS y (
            video_id, title, description, published_at, event_date,
            jurisdiction_id, jurisdiction_name, jurisdiction_type,
            city, state_code, state,
            channel_id, channel_url, channel_type, video_url,
            duration_minutes, datasource, datasource_id, loaded_at, last_updated
        ) VALUES (
            %(video_id)s, %(title)s, %(description)s, %(published_at)s, %(event_date)s,
            %(jurisdiction_id)s, %(jurisdiction_name)s, %(jurisdiction_type)s,
            %(city)s, %(state_code)s, %(state)s,
            %(channel_id)s, %(channel_url)s, %(channel_type)s, %(video_url)s,
            %(duration_minutes)s, 'youtube_data_api', %(video_id)s, NOW(), NOW()
        )
        ON CONFLICT (video_id) DO UPDATE SET
            title = COALESCE(EXCLUDED.title, y.title),
            description = COALESCE(EXCLUDED.description, y.description),
            published_at = COALESCE(EXCLUDED.published_at, y.published_at),
            event_date = COALESCE(EXCLUDED.event_date, y.event_date),
            jurisdiction_id = COALESCE(EXCLUDED.jurisdiction_id, y.jurisdiction_id),
            jurisdiction_name = COALESCE(EXCLUDED.jurisdiction_name, y.jurisdiction_name),
            jurisdiction_type = COALESCE(EXCLUDED.jurisdiction_type, y.jurisdiction_type),
            city = COALESCE(EXCLUDED.city, y.city),
            state_code = COALESCE(EXCLUDED.state_code, y.state_code),
            state = COALESCE(EXCLUDED.state, y.state),
            channel_id = COALESCE(EXCLUDED.channel_id, y.channel_id),
            channel_type = EXCLUDED.channel_type,
            duration_minutes = COALESCE(EXCLUDED.duration_minutes, y.duration_minutes),
            last_updated = NOW()
    """
    cur = conn.cursor()
    n = 0
    for r in rows:
        published = r.get("published_at")
        event_date = None
        published_ts = None
        if published:
            published_ts = datetime.fromisoformat(published.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
            event_date = published_ts.date()
        cur.execute(
            sql,
            {
                "video_id": r["video_id"],
                "title": r.get("title"),
                "description": r.get("description"),
                "published_at": published_ts,
                "event_date": event_date,
                "jurisdiction_id": jurisdiction_id,
                "jurisdiction_name": jurisdiction_name,
                "jurisdiction_type": jurisdiction_type,
                "city": city,
                "state_code": state_code,
                "state": state,
                "channel_id": channel_id,
                "channel_url": f"https://www.youtube.com/channel/{channel_id}",
                "channel_type": channel_type,
                "video_url": f"https://www.youtube.com/watch?v={r['video_id']}",
                "duration_minutes": r.get("duration_minutes"),
            },
        )
        n += cur.rowcount
    conn.commit()
    return n


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--channel-id", required=True)
    p.add_argument("--jurisdiction-id", required=True)
    p.add_argument("--jurisdiction-name", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--jurisdiction-type", default="municipality")
    p.add_argument("--city", default=None)
    p.add_argument("--channel-type", default="municipal")
    p.add_argument("--published-after", default=None, help="YYYY-MM-DD inclusive")
    p.add_argument("--published-before", default=None, help="YYYY-MM-DD inclusive")
    p.add_argument(
        "--database-url",
        default=None,
        help="Default NEON_DATABASE_URL_DEV / local warehouse",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        logger.error("YOUTUBE_API_KEY is required")
        return 2

    channel_id = args.channel_id.strip()
    uploads = list_uploads(
        api_key,
        channel_id,
        published_after=args.published_after,
        published_before=args.published_before,
    )
    logger.info("Uploads playlist matched {} video(s) in window", len(uploads))
    if not uploads:
        return 0

    meta = enrich_videos(api_key, [u["video_id"] for u in uploads])
    rows = []
    for u in uploads:
        m = meta.get(u["video_id"], {})
        rows.append(
            {
                "video_id": u["video_id"],
                "title": m.get("title") or u.get("title"),
                "description": m.get("description") or u.get("description"),
                "published_at": m.get("published_at") or u.get("published_at"),
                "duration_minutes": m.get("duration_minutes"),
            }
        )

    if args.dry_run:
        logger.info("dry-run: would upsert {} row(s)", len(rows))
        for r in rows[:5]:
            logger.info("  {} {}", r["video_id"], (r.get("title") or "")[:80])
        return 0

    db_url = (
        args.database_url
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )
    state_code = args.state.strip().upper()
    city = (args.city or args.jurisdiction_name).strip()
    conn = psycopg2.connect(db_url)
    try:
        n = upsert_rows(
            conn,
            rows,
            jurisdiction_id=args.jurisdiction_id.strip(),
            jurisdiction_name=args.jurisdiction_name.strip(),
            jurisdiction_type=args.jurisdiction_type.strip(),
            state_code=state_code,
            state=state_code,
            city=city,
            channel_id=channel_id,
            channel_type=args.channel_type,
        )
        logger.success("Upserted {} bronze.bronze_event_youtube row(s)", n)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
