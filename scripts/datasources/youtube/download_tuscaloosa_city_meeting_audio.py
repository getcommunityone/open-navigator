#!/usr/bin/env python3
"""
Catalog and download City of Tuscaloosa, AL YouTube audio (committee / meeting titles only).

Uses the @TuscaloosaCityAL channel (Videos + Streams tabs), no date cutoff, title filter
``committee`` OR ``meeting`` (case-insensitive substring), then writes Opus under
``data/cache/youtube_audio/al/``.

Examples::

    # Full run: refresh catalog + download all matching audio not yet on disk
    python scripts/datasources/youtube/download_tuscaloosa_city_meeting_audio.py

    # List matches without downloading
    python scripts/datasources/youtube/download_tuscaloosa_city_meeting_audio.py --dry-run

    # Catalog only (Postgres bronze rows, no yt-dlp audio)
    python scripts/datasources/youtube/download_tuscaloosa_city_meeting_audio.py --catalog-only

    # Download only (rows already in bronze from a prior catalog pass)
    python scripts/datasources/youtube/download_tuscaloosa_city_meeting_audio.py --download-only
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_LOCALVIEW = _REPO_ROOT / "scripts" / "localview"
if str(_LOCALVIEW) not in sys.path:
    sys.path.insert(0, str(_LOCALVIEW))

from scrape_youtube_channels import MunicipalYouTubeScraper  # noqa: E402

from scripts.datasources.youtube.download_audio_to_drive import (  # noqa: E402
    DEFAULT_YOUTUBE_AUDIO_OUTPUT_DIR,
    DEFAULT_YOUTUBE_COOKIES_FILE,
    YouTubeAudioDownloader,
)
from scripts.datasources.youtube.load_youtube_events_to_postgres import (  # noqa: E402
    YouTubeEventsLoader,
)

# City of Tuscaloosa, AL — from meetings manifest / @TuscaloosaCityAL
TUSCALOOSA_JURISDICTION_ID = "tuscaloosa_0177256"
TUSCALOOSA_JURISDICTION_NAME = "Tuscaloosa"
TUSCALOOSA_STATE = "AL"
TUSCALOOSA_CHANNEL_ID = "UC74dczS0B3MhDhUHp2ZGRPA"
TUSCALOOSA_CHANNEL_TITLE = "City of Tuscaloosa"
DEFAULT_TITLE_KEYWORDS = ("committee", "meeting")


def _database_url(explicit: str | None) -> str:
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def title_matches(title: str, keywords: Iterable[str]) -> bool:
    text = (title or "").lower()
    return any(kw.lower() in text for kw in keywords)


def catalog_matching_videos(
    loader: YouTubeEventsLoader,
    channel_id: str,
    *,
    jurisdiction_id: str,
    jurisdiction_name: str,
    state_code: str,
    jurisdiction_type: str,
    channel_title: str,
    title_keywords: Sequence[str],
    max_videos: int,
) -> tuple[int, int]:
    """
    Fetch channel listing (videos + streams tabs), keep title matches, upsert bronze.

    Returns (fetched_from_youtube, inserted_or_updated_rows).
    """
    logger.info(
        "Fetching up to {} videos from channel {} (no date filter, videos+streams)",
        max_videos,
        channel_id,
    )
    videos = loader.scraper.get_channel_videos(
        channel_id=channel_id,
        max_results=max_videos,
        published_after=None,
    )
    logger.info("Channel returned {} video(s) from YouTube", len(videos))

    matched = [v for v in videos if title_matches(v.get("title", ""), title_keywords)]
    logger.info(
        "Title filter {!r}: {} match(es)",
        list(title_keywords),
        len(matched),
    )
    for v in matched[:15]:
        logger.info("  • {}", (v.get("title") or "")[:100])
    if len(matched) > 15:
        logger.info("  … and {} more", len(matched) - 15)

    if not matched:
        return len(videos), 0

    loader.upsert_channel(
        channel_id=channel_id,
        channel_url=f"https://www.youtube.com/channel/{channel_id}",
        channel_title=channel_title,
        channel_type="municipal",
        jurisdiction_id=jurisdiction_id,
        jurisdiction_name=jurisdiction_name,
        state_code=state_code,
        discovery_method="tuscaloosa_meeting_download",
    )

    events = [
        loader.video_to_event_record(
            video=v,
            jurisdiction_id=jurisdiction_id,
            jurisdiction_name=jurisdiction_name,
            jurisdiction_type=jurisdiction_type,
            state_code=state_code,
            state=state_code,
            channel_id=channel_id,
            channel_type="municipal",
        )
        for v in matched
    ]
    inserted = loader.insert_events(events)
    return len(videos), inserted


def run_download(
    database_url: str,
    output_dir: Path,
    *,
    title_keywords: Sequence[str],
    limit: int | None,
    cookies_file: str | None,
    not_yet_downloaded: bool,
) -> None:
    downloader = YouTubeAudioDownloader(
        database_url=database_url,
        output_dir=str(output_dir),
        limit=limit,
        channels_filter=[TUSCALOOSA_JURISDICTION_NAME],
        states_filter=[TUSCALOOSA_STATE],
        title_keywords=list(title_keywords),
        jurisdiction_ids=[TUSCALOOSA_JURISDICTION_ID],
        not_yet_downloaded=not_yet_downloaded,
        skip_existing=True,
        cookies_file=cookies_file,
        meetings_only=False,
        years_back=None,
        days_recent=None,
    )
    downloader.run()


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description=(
            "City of Tuscaloosa YouTube: catalog + download Opus for titles "
            "containing committee or meeting (all dates)"
        )
    )
    parser.add_argument(
        "--title-keywords",
        default=",".join(DEFAULT_TITLE_KEYWORDS),
        help="Comma-separated substrings (default: committee,meeting)",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=500,
        help="Max videos to read from the channel listing (default 500)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_YOUTUBE_AUDIO_OUTPUT_DIR,
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--limit", type=int, default=None, help="Cap downloads this run")
    parser.add_argument(
        "--cookies",
        default=str(DEFAULT_YOUTUBE_COOKIES_FILE) if DEFAULT_YOUTUBE_COOKIES_FILE.is_file() else None,
    )
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument(
        "--re-download",
        action="store_true",
        help="Include rows that already have audio_downloaded_at set",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.catalog_only and args.download_only:
        logger.error("Use only one of --catalog-only or --download-only")
        return 2

    keywords = [k.strip() for k in args.title_keywords.split(",") if k.strip()]
    if not keywords:
        logger.error("At least one --title-keyword is required")
        return 2

    db_url = _database_url(args.database_url)
    output_dir = args.output_dir.expanduser().resolve()

    logger.info("=" * 72)
    logger.info("Tuscaloosa city YouTube — committee/meeting audio")
    logger.info("Jurisdiction: {} ({})", TUSCALOOSA_JURISDICTION_NAME, TUSCALOOSA_JURISDICTION_ID)
    logger.info("Channel: {} ({})", TUSCALOOSA_CHANNEL_TITLE, TUSCALOOSA_CHANNEL_ID)
    logger.info("Title keywords: {}", ", ".join(keywords))
    logger.info("Output: {}", output_dir)
    logger.info("=" * 72)

    if args.dry_run:
        logger.info("[dry-run] Would catalog (max {}) then download matching titles", args.max_videos)
        return 0

    do_catalog = not args.download_only
    do_download = not args.catalog_only

    if do_catalog:
        loader = YouTubeEventsLoader(
            database_url=db_url,
            youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
            max_videos_per_channel=args.max_videos,
            days_lookback=None,
            fetch_transcripts=False,
            force_full_fetch=True,
        )
        try:
            fetched, inserted = catalog_matching_videos(
                loader,
                TUSCALOOSA_CHANNEL_ID,
                jurisdiction_id=TUSCALOOSA_JURISDICTION_ID,
                jurisdiction_name=TUSCALOOSA_JURISDICTION_NAME,
                state_code=TUSCALOOSA_STATE,
                jurisdiction_type="municipality",
                channel_title=TUSCALOOSA_CHANNEL_TITLE,
                title_keywords=keywords,
                max_videos=args.max_videos,
            )
            logger.success(
                "Catalog done — {} fetched from YouTube, {} bronze row(s) written",
                fetched,
                inserted,
            )
        finally:
            loader.conn.close()

    if do_download:
        logger.info("Starting Opus downloads…")
        run_download(
            db_url,
            output_dir,
            title_keywords=keywords,
            limit=args.limit,
            cookies_file=args.cookies,
            not_yet_downloaded=not args.re_download,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
