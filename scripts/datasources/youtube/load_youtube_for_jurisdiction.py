#!/usr/bin/env python3
"""
Load YouTube catalog (videos + streams tabs) for a single jurisdiction into bronze.

Examples::

    # City of Tuscaloosa, AL (channel from meetings manifest / @TuscaloosaCityAL)
    python scripts/datasources/youtube/load_youtube_for_jurisdiction.py \\
        --jurisdiction-id municipality_0177256 \\
        --jurisdiction-name Tuscaloosa \\
        --state AL \\
        --channel-id UC74dczS0B3MhDhUHp2ZGRPA \\
        --max-videos 100 \\
        --force

    # Then download meeting audio for that city only
    python scripts/datasources/youtube/download_audio_to_drive.py \\
        --channels Tuscaloosa --meetings-only --years-back 5 --limit 100
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.datasources.youtube.download_audio_to_drive import (  # noqa: E402
    DEFAULT_YOUTUBE_COOKIES_FILE,
)
from scripts.datasources.youtube.load_youtube_events_to_postgres import (  # noqa: E402
    YouTubeEventsLoader,
)


def _resolve_cookies_path(explicit: str | None) -> str | None:
    if explicit and Path(explicit).is_file():
        return explicit
    env = (os.getenv("YOUTUBE_COOKIES") or "").strip()
    if env and Path(env).is_file():
        return env
    if DEFAULT_YOUTUBE_COOKIES_FILE.is_file():
        return str(DEFAULT_YOUTUBE_COOKIES_FILE.resolve())
    return None


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Load YouTube events for one jurisdiction (Videos + Streams tabs)"
    )
    parser.add_argument("--jurisdiction-id", required=True)
    parser.add_argument("--jurisdiction-name", required=True)
    parser.add_argument("--state", required=True, help="USPS state code, e.g. AL")
    parser.add_argument("--channel-id", required=True, help="YouTube channel ID (UC…)")
    parser.add_argument("--channel-title", default=None)
    parser.add_argument(
        "--channel-url",
        default=None,
        help="Defaults to https://www.youtube.com/channel/{channel_id}",
    )
    parser.add_argument("--jurisdiction-type", default="municipality")
    parser.add_argument(
        "--discovery-method",
        default="jurisdictions_details",
        help="Provenance label for channel mapping (e.g. website_scrape, pattern_match, fallback_discovery)",
    )
    parser.add_argument(
        "--confidence-score",
        type=float,
        default=None,
        help="Optional mapping confidence in [0, 1] when known",
    )
    parser.add_argument(
        "--source-priority",
        default="",
        help="Optional source priority tag (e.g. scraped_official_website, fallback_discovery)",
    )
    parser.add_argument("--max-videos", type=int, default=100)
    parser.add_argument(
        "--min-duration-seconds",
        type=int,
        default=120,
        help="Skip videos shorter than this many seconds (default: 120)",
    )
    parser.add_argument("--days", type=int, default=None, help="Only videos newer than N days")
    parser.add_argument("--skip-transcripts", action="store_true")
    parser.add_argument(
        "--transcript-delay",
        type=float,
        default=5.0,
        help="Seconds between caption fetches (default 5; use 8+ if rate limited)",
    )
    parser.add_argument(
        "--cookies",
        default="",
        help="Netscape cookies.txt (or set YOUTUBE_COOKIES / repo youtube_cookies.txt)",
    )
    parser.add_argument(
        "--proxy",
        default="",
        help="Proxy for caption API (or set YOUTUBE_TRANSCRIPT_PROXY)",
    )
    parser.add_argument("--force", action="store_true", help="Ignore incremental cursor")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Postgres URL (default NEON_DATABASE_URL_DEV / NEON_DATABASE_URL)",
    )
    args = parser.parse_args()

    db_url = (
        args.database_url
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )
    channel_id = args.channel_id.strip()
    channel_title = (args.channel_title or args.jurisdiction_name).strip()
    channel_url = (
        args.channel_url or f"https://www.youtube.com/channel/{channel_id}"
    ).strip()
    discovery_method = (args.discovery_method or "").strip() or "jurisdictions_details"
    source_priority = (args.source_priority or "").strip()

    fuzzy_loaded = (
        source_priority == "fallback_discovery"
        or discovery_method in {"pattern_match", "youtube_api", "fallback_discovery"}
    )

    cookies = _resolve_cookies_path((args.cookies or "").strip() or None)
    proxy = (args.proxy or os.getenv("YOUTUBE_TRANSCRIPT_PROXY") or "").strip() or None
    if cookies:
        logger.info("Using cookies for transcript fetches: {}", cookies)
    if proxy:
        logger.info("Using proxy for transcript fetches: {}", proxy)
    if not args.skip_transcripts and not cookies:
        logger.warning(
            "No cookies file — anonymous caption fetches often hit IP blocks in WSL. "
            "Use --skip-transcripts or export youtube_cookies.txt (see BYPASS_IP_BLOCK.md)"
        )

    loader = YouTubeEventsLoader(
        database_url=db_url,
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        max_videos_per_channel=args.max_videos,
        min_duration_seconds=args.min_duration_seconds,
        days_lookback=args.days,
        fetch_transcripts=not args.skip_transcripts,
        force_full_fetch=args.force,
        transcript_delay=args.transcript_delay,
        cookies_file=cookies,
        proxy_url=proxy,
    )

    jurisdiction = {
        "jurisdiction_id": args.jurisdiction_id.strip(),
        "jurisdiction_name": args.jurisdiction_name.strip(),
        "state_code": args.state.strip().upper(),
        "state": args.state.strip().upper(),
        "jurisdiction_type": args.jurisdiction_type.strip(),
        "youtube_channels": [
            {
                "channel_id": channel_id,
                "channel_url": channel_url,
                "channel_title": channel_title,
                "channel_type": "municipal",
                "discovery_method": discovery_method,
                "confidence": args.confidence_score,
                "source_priority": source_priority,
                "fuzzy_loaded": fuzzy_loaded,
            }
        ],
    }

    logger.info(
        "Loading YouTube for {} ({}) channel {} [videos+streams]",
        jurisdiction["jurisdiction_name"],
        jurisdiction["jurisdiction_id"],
        channel_id,
    )
    inserted = loader.process_jurisdiction(jurisdiction)
    if inserted > 0:
        logger.success("Done — wrote {} new/updated event row(s)", inserted)
    else:
        logger.info(
            "Done — NOOP (0 new rows written; channel already up to date or no videos found)"
        )
    loader.conn.close()


if __name__ == "__main__":
    main()
