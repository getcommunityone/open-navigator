#!/usr/bin/env python3
"""
Backfill YouTube captions for all videos in a jurisdiction (bronze + optional local cache).

Writes:
- ``bronze.bronze_events_text_ai`` (canonical)
- ``data/cache/gemini_transcript_policy/<jurisdiction_id>/YYYY-MM-DD_<title>.json`` (optional; matches Opus basename)

Examples::

    # Tuscaloosa — all 400+ bronze videos, skip already on disk or in bronze
    python scripts/datasources/youtube/backfill_jurisdiction_transcripts.py \\
        --jurisdiction-id municipality_0177256

    # Dry rundev
    python scripts/datasources/youtube/backfill_jurisdiction_transcripts.py \\
        --jurisdiction-id municipality_0177256 --dry-run

    # First 50 only, slower pacing
    python scripts/datasources/youtube/backfill_jurisdiction_transcripts.py \\
        --jurisdiction-id municipality_0177256 --limit 50 --delay 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.datasources.youtube.download_audio_to_drive import (  # noqa: E402
    DEFAULT_YOUTUBE_COOKIES_FILE,
)
from scripts.datasources.youtube.load_youtube_events_to_postgres import (  # noqa: E402
    YouTubeEventsLoader,
)
from scripts.gemini.transcript_cache_paths import (  # noqa: E402
    legacy_transcript_cache_path,
    resolve_transcript_cache_path,
    transcript_cache_path,
)

DEFAULT_LOCAL_CACHE = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"
TUSCALOOSA_JURISDICTION_ID = "municipality_0177256"


def _database_url(explicit: Optional[str]) -> str:
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def fetch_pending_videos(
    database_url: str,
    jurisdiction_id: str,
    *,
    limit: Optional[int] = None,
    skip_bronze: bool = True,
) -> List[Dict[str, Any]]:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    sql = """
        SELECT DISTINCT ON (y.video_url)
            y.video_id,
            y.video_url,
            y.title,
            y.event_id,
            y.event_date::text AS event_date,
            y.jurisdiction_id,
            t.has_transcript AS bronze_has_transcript
        FROM bronze.bronze_events_youtube y
        LEFT JOIN bronze.bronze_events_text_ai t ON t.video_id = y.video_id
        WHERE y.jurisdiction_id = %s
          AND y.video_id IS NOT NULL
          AND BTRIM(y.video_url) <> ''
    """
    params: list[Any] = [jurisdiction_id]
    if skip_bronze:
        sql += " AND (t.has_transcript IS NOT TRUE OR t.has_transcript IS NULL)"
    sql += """
        ORDER BY y.video_url, y.last_updated DESC NULLS LAST
    """
    sql = f"""
        SELECT * FROM ({sql}) sub
        ORDER BY event_date DESC NULLS LAST, video_id
    """
    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def local_transcript_path(cache_dir: Path, jurisdiction_id: str, row: Dict[str, Any]) -> Path:
    """Audio-aligned basename: ``YYYY-MM-DD_<sanitized title>.json``."""
    return transcript_cache_path(
        cache_dir,
        jurisdiction_id,
        title=str(row.get("title") or ""),
        event_date=row.get("event_date"),
    )


def local_transcript_exists(cache_dir: Path, jurisdiction_id: str, row: Dict[str, Any]) -> bool:
    folder = cache_dir / jurisdiction_id
    if local_transcript_path(cache_dir, jurisdiction_id, row).is_file():
        return True
    legacy = legacy_transcript_cache_path(cache_dir, jurisdiction_id, str(row["video_id"]))
    if legacy.is_file():
        return True
    return resolve_transcript_cache_path(
        folder,
        video_id=str(row["video_id"]),
        title=str(row.get("title") or ""),
        event_date=row.get("event_date"),
    ) is not None


def write_local_transcript(
    path: Path,
    *,
    row: Dict[str, Any],
    yt: Dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "video_id": row["video_id"],
        "video_url": row["video_url"],
        "title": row.get("title"),
        "event_date": row.get("event_date"),
        "jurisdiction_id": row["jurisdiction_id"],
        "youtube": yt,
        "segment_count": len(yt.get("segments") or []),
        "transcript_chars": len(yt.get("raw_text") or ""),
        "transcript_source": yt.get("transcript_source"),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_rate_limited(exc: BaseException) -> bool:
    name = type(exc).__name__.upper()
    if name in ("IPBLOCKED", "REQUESTBLOCKED", "TOOMANYREQUESTS"):
        return True
    msg = str(exc).upper()
    return (
        "RATE_LIMITED" in msg
        or "429" in msg
        or "TOO MANY REQUESTS" in msg
        or "IPBLOCKED" in msg
        or "IP BLOCKED" in msg
        or "REQUEST BLOCKED" in msg
        or "REQUESTBLOCKED" in msg
        or "RESOURCE_EXHAUSTED" in msg
    )


def probe_transcript_access(loader: YouTubeEventsLoader, video_id: str) -> bool:
    """Return False when the first fetch looks IP-blocked (triggers backoff)."""
    try:
        loader.fetch_transcript(video_id)
        return True
    except Exception as exc:
        return not is_rate_limited(exc)


def resolve_cookies_path(explicit: Optional[str]) -> Optional[str]:
    if explicit and Path(explicit).is_file():
        return explicit
    env = (os.getenv("YOUTUBE_COOKIES") or "").strip()
    if env and Path(env).is_file():
        return env
    if DEFAULT_YOUTUBE_COOKIES_FILE.is_file():
        return str(DEFAULT_YOUTUBE_COOKIES_FILE.resolve())
    return None


def run(args: argparse.Namespace) -> int:
    load_dotenv(_REPO_ROOT / ".env")
    db_url = _database_url(args.database_url or None)
    jurisdiction_id = args.jurisdiction_id.strip()
    cache_dir = Path(args.local_cache_dir).resolve()

    pending = fetch_pending_videos(
        db_url,
        jurisdiction_id,
        limit=args.limit,
        skip_bronze=not args.include_bronze_existing,
    )

    if args.skip_local_existing:
        filtered: List[Dict[str, Any]] = []
        for row in pending:
            if local_transcript_exists(cache_dir, jurisdiction_id, row):
                continue
            filtered.append(row)
        skipped_local = len(pending) - len(filtered)
        pending = filtered
        if skipped_local:
            logger.info("Skipped {} already in local cache", skipped_local)

    logger.info(
        "Jurisdiction {} — {} video(s) to fetch",
        jurisdiction_id,
        len(pending),
    )

    if args.dry_run:
        for i, row in enumerate(pending, 1):
            print(
                f"{i:4}. {row['video_id']}  {row.get('event_date') or '?'}  "
                f"{(row.get('title') or '')[:70]}"
            )
        return 0

    if not pending:
        logger.success("Nothing to fetch — all transcripts present")
        return 0

    cookies = resolve_cookies_path(args.cookies or None)
    proxy = (args.proxy or os.getenv("YOUTUBE_TRANSCRIPT_PROXY") or "").strip() or None
    if cookies:
        logger.info("Using cookies file: {}", cookies)
    if proxy:
        logger.info("Using proxy for transcript fetches: {}", proxy)
    else:
        logger.warning(
            "No YOUTUBE_TRANSCRIPT_PROXY — requests use raw egress (WSL may bypass host VPN)"
        )

    loader = YouTubeEventsLoader(
        database_url=db_url,
        fetch_transcripts=False,
        transcript_delay=args.delay,
        use_ytdlp_fallback=not args.no_ytdlp_fallback,
        cookies_file=cookies,
        proxy_url=proxy,
    )

    stats = {"ok": 0, "fail": 0, "rate_limit": 0, "empty": 0}
    consecutive_rl = 0
    max_rl = args.max_consecutive_rate_limits

    probe_id = (args.probe_video_id or "").strip() or "ajsME66iXbY"
    if args.skip_probe:
        probe_id = ""
    if probe_id and not probe_transcript_access(loader, probe_id):
        wait = min(args.delay * (2**consecutive_rl), args.max_backoff)
        logger.error(
            "Probe video {} looks IP-blocked — sleeping {:.0f}s before batch "
            "(fix VPN/proxy or set YOUTUBE_TRANSCRIPT_PROXY)",
            probe_id,
            wait,
        )
        time.sleep(wait)
        consecutive_rl += 1

    for i, row in enumerate(pending, 1):
        video_id = row["video_id"]
        if i > 1:
            delay = args.delay
            if consecutive_rl > 0:
                delay = min(args.delay * (2**consecutive_rl), args.max_backoff)
                logger.warning("Backoff {:.1f}s after rate limit", delay)
            time.sleep(delay)

        logger.info("[{}/{}] {}", i, len(pending), video_id)
        try:
            yt = loader.fetch_transcript(video_id)
            if yt is None:
                stats["fail"] += 1
                logger.warning(
                    "No transcript for {} — captions disabled, yt-dlp failed, or IP blocked "
                    "(re-run IP test; not always 'disabled')",
                    video_id,
                )
                continue
        except Exception as exc:
            if is_rate_limited(exc):
                stats["rate_limit"] += 1
                consecutive_rl += 1
                wait = min(args.delay * (2**consecutive_rl), args.max_backoff)
                logger.warning(
                    "IP blocked / rate limited on {} ({}/{}) — next sleep {:.0f}s",
                    video_id,
                    consecutive_rl,
                    max_rl,
                    wait,
                )
                if consecutive_rl >= max_rl:
                    logger.error(
                        "Stopping after {} consecutive blocks — fix VPN/proxy, wait, then re-run",
                        max_rl,
                    )
                    break
                continue
            stats["fail"] += 1
            consecutive_rl = 0
            logger.warning("No transcript for {}: {}", video_id, exc)
            continue

        consecutive_rl = 0
        if not (yt.get("raw_text") or "").strip():
            stats["empty"] += 1
            continue

        if not args.no_local_cache:
            write_local_transcript(
                local_transcript_path(cache_dir, jurisdiction_id, row),
                row=row,
                yt=yt,
            )

        if args.write_bronze:
            import json as _json

            event_id = row.get("event_id")
            if event_id:
                segments = yt.get("segments")
                seg_json = _json.dumps(segments) if segments else None
                quality = "medium" if yt.get("is_auto_generated") else "high"
                cur = loader.conn.cursor()
                try:
                    cur.execute(
                        """
                        INSERT INTO bronze.bronze_events_text_ai (
                            event_id, video_id, raw_text, segments, language,
                            is_auto_generated, transcript_source, has_transcript, transcript_quality
                        ) VALUES (
                            %(event_id)s, %(video_id)s, %(raw_text)s, %(segments)s::jsonb, %(language)s,
                            %(is_auto_generated)s, %(transcript_source)s, true, %(transcript_quality)s
                        )
                        ON CONFLICT (video_id) DO UPDATE SET
                            raw_text = EXCLUDED.raw_text,
                            segments = EXCLUDED.segments,
                            language = EXCLUDED.language,
                            is_auto_generated = EXCLUDED.is_auto_generated,
                            transcript_source = EXCLUDED.transcript_source,
                            has_transcript = EXCLUDED.has_transcript,
                            transcript_quality = EXCLUDED.transcript_quality,
                            last_updated = CURRENT_TIMESTAMP
                        """,
                        {
                            "event_id": event_id,
                            "video_id": video_id,
                            "raw_text": yt.get("raw_text"),
                            "segments": seg_json,
                            "language": yt.get("language"),
                            "is_auto_generated": yt.get("is_auto_generated"),
                            "transcript_source": yt.get("transcript_source"),
                            "transcript_quality": quality,
                        },
                    )
                    loader.conn.commit()
                finally:
                    cur.close()

        stats["ok"] += 1
        if stats["ok"] % 25 == 0:
            logger.info("Progress: {}", stats)

    loader.close()
    logger.info("Done: {}", stats)
    return 0 if stats["rate_limit"] < max_rl else 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jurisdiction-id",
        default=TUSCALOOSA_JURISDICTION_ID,
    )
    parser.add_argument("--database-url", default="")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between YouTube fetches")
    parser.add_argument(
        "--probe-video-id",
        default="ajsME66iXbY",
        help="Probe this video before batch; backs off if IP-blocked",
    )
    parser.add_argument("--skip-probe", action="store_true", help="Skip pre-batch IP probe")
    parser.add_argument(
        "--cookies",
        default="",
        help="Netscape cookies.txt (or set YOUTUBE_COOKIES / repo youtube_cookies.txt)",
    )
    parser.add_argument("--proxy", default="", help="Proxy URL (or YOUTUBE_TRANSCRIPT_PROXY)")
    parser.add_argument(
        "--no-ytdlp-fallback",
        action="store_true",
        help="Do not fall back to yt-dlp when youtube_transcript_api fails",
    )
    parser.add_argument("--max-backoff", type=float, default=60.0)
    parser.add_argument(
        "--max-consecutive-rate-limits",
        type=int,
        default=8,
        help="Stop batch after this many consecutive 429/IP blocks",
    )
    parser.add_argument("--languages", nargs="+", default=["en"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-local-existing",
        action="store_true",
        default=True,
        help="Skip videos that already have a local transcript JSON (default: true)",
    )
    parser.add_argument(
        "--no-skip-local-existing",
        action="store_false",
        dest="skip_local_existing",
    )
    parser.add_argument(
        "--include-bronze-existing",
        action="store_true",
        help="Re-fetch even when bronze.has_transcript is true",
    )
    parser.add_argument(
        "--no-local-cache",
        action="store_true",
        help="Do not write gemini_transcript_policy JSON files",
    )
    parser.add_argument(
        "--write-bronze",
        action="store_true",
        default=True,
        help="Upsert bronze.bronze_events_text_ai (default: true)",
    )
    parser.add_argument("--no-write-bronze", action="store_false", dest="write_bronze")
    parser.add_argument(
        "--local-cache-dir",
        type=Path,
        default=DEFAULT_LOCAL_CACHE,
    )
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
