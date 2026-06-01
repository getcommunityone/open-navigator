#!/usr/bin/env python3
"""
Backfill transcripts for YouTube events that don't have them yet.

This script:
1. Finds all YouTube events in event that don't have transcripts
2. Fetches transcripts (with timing data) for those videos
3. Inserts them into events_text_search table

Usage:
    # Backfill all missing transcripts
    python packages/scrapers/src/scrapers/youtube/backfill_transcripts.py
    
    # Limit to specific states
    python packages/scrapers/src/scrapers/youtube/backfill_transcripts.py --states AL,MA,WI
    
    # Limit number of transcripts to fetch
    python packages/scrapers/src/scrapers/youtube/backfill_transcripts.py --limit 100
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
import argparse
from urllib.parse import parse_qs, urlparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv

from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

from scrapers.youtube.transcript_api_client import (
    fetch_transcript_from_api,
    format_transcript_error,
    log_caption_fetch_setup,
    resolve_cookies_path,
)

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')


# A YouTube video ID is exactly 11 chars from [A-Za-z0-9_-]. Anchoring on this
# lets us pull the ID out of path-style URLs regardless of trailing junk.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
# Path prefixes that carry the video ID as the next path segment.
_PATH_ID_SEGMENTS = ("embed", "v", "shorts", "live", "e")


def _clean_video_id(candidate: Optional[str]) -> Optional[str]:
    """Strip query/fragment leftovers and validate the 11-char ID shape."""
    if not candidate:
        return None
    # Defensive: drop anything past a stray ?, &, /, or # that slipped through.
    candidate = re.split(r"[?&/#]", candidate.strip())[0]
    return candidate if _VIDEO_ID_RE.match(candidate) else None


def extract_video_id_from_url(url: str) -> Optional[str]:
    """Extract an 11-char video ID from any common YouTube URL format.

    Handles ``watch?v=`` (with ``v`` in any query position), ``youtu.be/<id>``,
    and path forms ``/embed/``, ``/v/``, ``/shorts/``, ``/live/``, ``/e/``.
    Returns ``None`` when no valid ID is present.
    """
    if not url:
        return None

    url = url.strip()
    # Bare 11-char ID with no URL wrapper.
    direct = _clean_video_id(url)
    if direct:
        return direct

    parsed = urlparse(url if "//" in url else f"//{url}", scheme="https")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path or ""

    # youtu.be/<id> — the ID is the first path segment.
    if host == "youtu.be":
        return _clean_video_id(path.lstrip("/"))

    # watch?v=<id> — v can sit anywhere in the query string.
    if "v" in (qs := parse_qs(parsed.query)):
        cleaned = _clean_video_id(qs["v"][0])
        if cleaned:
            return cleaned

    # Path-style: /embed/<id>, /v/<id>, /shorts/<id>, /live/<id>, /e/<id>.
    segments = [seg for seg in path.split("/") if seg]
    for i, seg in enumerate(segments[:-1]):
        if seg.lower() in _PATH_ID_SEGMENTS:
            return _clean_video_id(segments[i + 1])

    return None


# Network/egress failures (dead Webshare proxy, TLS handshake timeout, DNS, reset
# connections) surface as SSLError / ProxyError / Timeout chains — NOT as a
# missing-caption result. They mean the egress is down, so retrying the same
# video is futile and slow; the caller skips fast and trips a circuit breaker.
_CONNECTION_ERROR_MARKERS = (
    "sslerror",
    "ssl:",
    "max retries exceeded",
    "proxyerror",
    "connection aborted",
    "connection reset",
    "connectionerror",
    "failed to establish a new connection",
    "read timed out",
    "readtimeout",
    "handshake operation timed out",
    "timed out",
    "name or service not known",
    "temporary failure in name resolution",
)


def _is_connection_error(error_msg: str) -> bool:
    """True when an error string is an egress/network failure, not a real result."""
    low = (error_msg or "").lower()
    return any(marker in low for marker in _CONNECTION_ERROR_MARKERS)


def fetch_transcript_simple(
    video_id: str,
    *,
    cookies_file: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch captions via the shared transcript client.

    Routes through ``transcript_api_client``, which uses the Webshare rotating
    residential proxy (``PROXY_USER_NAME`` / ``PROXY_PASSWORD``) plus
    ``youtube_cookies.txt`` when configured — a fresh egress IP per request, so
    the per-IP 429 ceiling is spread across the pool instead of hammering one IP.

    Returns the transcript payload, or ``None`` when the video simply has no
    caption track / is unavailable. Block/rate-limit errors (``RequestBlocked``,
    ``IpBlocked``) propagate so the caller can back off.
    """
    if not video_id:
        return None

    try:
        return fetch_transcript_from_api(video_id, cookies_file=cookies_file)
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        # Genuinely no transcript for this video — not a rate-limit signal.
        return None


# ---------------------------------------------------------------------------
# Negative cache for transcript fetches.
#
# A row only lands in bronze_events_text_ai on SUCCESS, so a video that has no
# caption track stays "missing" forever and gets re-fetched on every run — which
# is why a repeat run is a wall of "⊘ No transcript available" against the same
# dead videos. This table records the videos we've already tried and found to
# have no transcript, keyed by video_id so it covers BOTH event sources
# (event mart + LocalView); bronze_events_youtube can't, since LocalView videos
# have no row there. The selection below then skips a video until
# `retry_after_days` has elapsed, and orders never-tried videos first.
# ---------------------------------------------------------------------------


def ensure_transcript_fetch_attempts_table(conn) -> None:
    """Create the fetch-attempt tracking table if missing (idempotent)."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_transcript_fetch_attempts (
                video_id        VARCHAR(64) PRIMARY KEY,
                last_attempt_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                attempts        INTEGER     NOT NULL DEFAULT 0,
                last_status     VARCHAR(32),
                last_error      TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transcript_fetch_attempts_last
            ON bronze.bronze_transcript_fetch_attempts (last_attempt_at)
            """
        )
        conn.commit()
    finally:
        cur.close()


def record_transcript_unavailable(
    conn,
    video_id: str,
    *,
    status: str = "unavailable",
    error: Optional[str] = None,
) -> None:
    """Mark a genuine no-transcript outcome so repeat runs skip it.

    Best-effort: a tracking write must never abort the backfill, so a failure
    here is rolled back and swallowed rather than propagated.
    """
    vid = (video_id or "").strip()
    if not vid:
        return
    msg = (error or "").strip()[:2000] or None
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO bronze.bronze_transcript_fetch_attempts
                (video_id, last_attempt_at, attempts, last_status, last_error)
            VALUES (%s, CURRENT_TIMESTAMP, 1, %s, %s)
            ON CONFLICT (video_id) DO UPDATE SET
                last_attempt_at = CURRENT_TIMESTAMP,
                attempts        = bronze.bronze_transcript_fetch_attempts.attempts + 1,
                last_status     = EXCLUDED.last_status,
                last_error      = EXCLUDED.last_error
            """,
            (vid, status, msg),
        )
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - tracking must never break the run
        conn.rollback()
        logger.debug("Could not record fetch attempt for {}: {}", vid, exc)
    finally:
        cur.close()


def get_events_missing_transcripts(
    conn,
    states: Optional[List[str]] = None,
    limit: Optional[int] = None,
    *,
    retry_after_days: int = 30,
    retry_failed: bool = False,
) -> List[Dict]:
    """Get YouTube events without transcripts yet, never-tried videos first.

    Videos previously tried and found to have no transcript are recorded in
    bronze_transcript_fetch_attempts and skipped until ``retry_after_days`` has
    elapsed (set ``retry_failed`` to ignore the negative cache entirely).
    Never-attempted videos sort ahead of due-for-retry ones so a capped
    ``--limit`` run spends its budget on fresh videos.
    """
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Build query to find videos without transcripts.
        # int_events_union merges every event source that carries a meeting
        # video URL (event mart + LocalView), deduped to one row per video_id.
        # Anti-join the bronze transcript landing on video_id to skip videos
        # whose transcript is already landed, and LEFT JOIN the negative cache
        # to skip / deprioritise videos we've already found to have none.
        query = """
            SELECT
                u.event_id,
                u.video_url,
                u.event_title,
                u.jurisdiction_id,
                u.jurisdiction_name,
                u.state_code,
                u.state
            FROM intermediate.int_events_union u
            LEFT JOIN bronze.bronze_events_text_ai t ON t.video_id = u.video_id
            LEFT JOIN bronze.bronze_transcript_fetch_attempts a ON a.video_id = u.video_id
            WHERE u.video_url IS NOT NULL
              AND t.id IS NULL  -- No transcript landed yet
        """

        params: List[Any] = []

        # Negative cache: skip videos tried within the retry window. Never-tried
        # videos (a.video_id IS NULL) always remain eligible.
        if not retry_failed:
            query += (
                " AND (a.video_id IS NULL"
                " OR a.last_attempt_at < CURRENT_TIMESTAMP - make_interval(days => %s))"
            )
            params.append(int(retry_after_days))

        if states:
            placeholders = ','.join(['%s'] * len(states))
            query += f" AND u.state_code IN ({placeholders})"
            params.extend(states)

        # Never-attempted videos first (FALSE sorts before TRUE), then newest
        # meetings first: a capped run should spend its budget on fresh videos
        # rather than re-trying known caption-less ones, and recent uploads are
        # likelier to carry (auto-)captions than decades-old municipal videos.
        query += (
            " ORDER BY (a.video_id IS NOT NULL),"
            " u.event_date DESC NULLS LAST, u.event_id ASC"
        )

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        cursor.execute(query, params)
        results = cursor.fetchall()

        return [dict(row) for row in results]

    finally:
        cursor.close()


def backfill_transcripts(
    database_url: str,
    youtube_api_key: Optional[str] = None,
    states: Optional[List[str]] = None,
    limit: Optional[int] = None,
    retry_after_days: int = 30,
    retry_failed: bool = False,
):
    """Backfill missing transcripts for YouTube events."""

    # Connect to database
    conn = psycopg2.connect(database_url)

    try:
        # Negative cache for "no transcript" outcomes (created if missing) so we
        # prioritise never-tried videos and don't re-fetch known caption-less ones.
        ensure_transcript_fetch_attempts_table(conn)

        # Get events missing transcripts
        logger.info("Finding YouTube events without transcripts...")
        events = get_events_missing_transcripts(
            conn,
            states=states,
            limit=limit,
            retry_after_days=retry_after_days,
            retry_failed=retry_failed,
        )
        # Release the read transaction's AccessShareLock on int_events_union
        # immediately — otherwise the whole (potentially hours-long) fetch loop
        # pins the view and blocks dbt from rebuilding it (CREATE OR REPLACE /
        # rename-swap need an exclusive lock). Inserts below open their own txns.
        conn.rollback()

        if not events:
            logger.success("✓ All YouTube events already have transcripts!")
            return

        logger.info(f"Found {len(events)} events missing transcripts")

        # Resolve cookies once and log where caption fetches egress (Webshare
        # rotating residential proxy vs direct). Rotating IPs are what let this
        # run avoid the per-IP 429 wall the old direct fetcher hit.
        cookies_path = resolve_cookies_path()
        log_caption_fetch_setup(logger, cookies_path=cookies_path, ytdlp_fallback=False)

        # Process each event
        inserted = 0
        failed = 0
        rate_limited = 0
        consecutive_rate_limits = 0
        max_backoff = 60  # Maximum 60 seconds backoff
        base_delay = 1.0  # Between fetches; rotating proxy IPs tolerate a tighter cadence
        max_block_retries = 5  # Per-video block retries before skipping the video
        max_block_giveups = 5  # Consecutive fully-blocked videos ⇒ abort (pool is down)
        block_giveup_streak = 0
        consecutive_egress_errors = 0  # SSL/proxy/timeout in a row ⇒ egress is down
        max_egress_errors = 3  # Abort fast rather than grind for hours inserting nothing

        import time
        
        for i, event in enumerate(events, 1):
            # Progressive delay based on rate limit history
            if consecutive_rate_limits > 0:
                # Exponential backoff: 2s, 4s, 8s, 16s, 32s, 60s (max)
                backoff_delay = min(base_delay * (2 ** consecutive_rate_limits), max_backoff)
                logger.warning(f"  ⏱️  Backing off {backoff_delay:.1f}s due to {consecutive_rate_limits} consecutive rate limits...")
                time.sleep(backoff_delay)
            elif i > 1:
                time.sleep(base_delay)  # Normal delay between requests
            event_id = event['event_id']
            video_url = event['video_url']
            title = event['event_title']
            jurisdiction = event['jurisdiction_name']
            state = event['state_code']
            # Geo carried from the event mart (via int_events_union). LocalView
            # videos have no bronze_events_youtube row, so the sync trigger can't
            # fill these — write them at insert time so coverage is complete.
            jurisdiction_id = event.get('jurisdiction_id')
            state_name = event.get('state')

            # Extract video ID
            video_id = extract_video_id_from_url(video_url)
            
            if not video_id:
                logger.warning(f"[{i}/{len(events)}] Could not extract video ID from: {video_url}")
                failed += 1
                continue
            
            logger.info(f"[{i}/{len(events)}] Fetching transcript for: {jurisdiction}, {state} - {title[:50]}...")
            logger.debug(f"  Video ID: {video_id}, Event ID: {event_id}")
            
            # Fetch via the shared Webshare-aware client. Three outcomes:
            #  • block (rate limit / IP block): back off and retry the SAME video
            #    — a transient block on a captioned video shouldn't cost it.
            #  • connection/egress error (SSL, proxy, timeout): the egress is
            #    down, so retrying is futile and slow — skip immediately and let
            #    the consecutive-error guard abort the run fast.
            #  • anything else: the video genuinely has no transcript.
            transcript_data = None
            skip_video = False
            block_giveup = False
            egress_down = False
            for attempt in range(1, max_block_retries + 1):
                try:
                    transcript_data = fetch_transcript_simple(video_id, cookies_file=cookies_path)
                    consecutive_rate_limits = 0  # Reset on any clean fetch (incl. "no captions")
                    consecutive_egress_errors = 0  # a clean response ⇒ egress is healthy
                    break
                except Exception as e:
                    error_msg = format_transcript_error(e)
                    is_block = (
                        isinstance(e, (RequestBlocked, IpBlocked))
                        or '429' in error_msg
                        or 'Too Many Requests' in error_msg
                    )
                    if not is_block and _is_connection_error(error_msg):
                        # Egress failure (dead proxy / TLS timeout / DNS), not a
                        # missing-caption result. Don't retry this video — bail.
                        consecutive_egress_errors += 1
                        logger.error(
                            f"  🔌 Egress error "
                            f"({consecutive_egress_errors}/{max_egress_errors}): {error_msg[:140]}"
                        )
                        failed += 1
                        skip_video = True
                        egress_down = consecutive_egress_errors >= max_egress_errors
                        break
                    # Reached YouTube (block or a real no-caption error) ⇒ egress works.
                    consecutive_egress_errors = 0
                    if not is_block:
                        logger.warning(f"  ⊘ No transcript available: {error_msg[:100]}")
                        # Reached YouTube and there's genuinely no caption track —
                        # record it so future runs skip this video for a while.
                        record_transcript_unavailable(
                            conn, video_id, status="unavailable", error=error_msg
                        )
                        failed += 1
                        skip_video = True
                        break
                    rate_limited += 1
                    consecutive_rate_limits += 1
                    logger.warning(
                        f"  ⚠️  Rate limited! ({rate_limited} total, {consecutive_rate_limits} "
                        f"consecutive, attempt {attempt}/{max_block_retries})"
                    )
                    if attempt >= max_block_retries:
                        logger.error(f"  ❌ Still blocked after {attempt} attempts — skipping video")
                        failed += 1
                        skip_video = True
                        block_giveup = True
                        break
                    backoff_delay = min(base_delay * (2 ** consecutive_rate_limits), max_backoff)
                    logger.warning(f"  ⏱️  Backing off {backoff_delay:.1f}s, then retrying same video...")
                    time.sleep(backoff_delay)

            # Egress is down (consecutive SSL/proxy/timeout failures): retrying any
            # video is pointless. Abort loudly with where to look.
            if egress_down:
                logger.error(
                    f"  ❌ Egress appears down — {consecutive_egress_errors} consecutive "
                    "connection/SSL failures. Check Webshare quota "
                    "(https://dashboard.webshare.io/proxy/stats), the direct-IP block, or "
                    "YOUTUBE_USE_WEBSHARE. Aborting run."
                )
                break

            # Circuit breaker: many videos blocked back-to-back ⇒ the proxy pool
            # is down or we're globally throttled. Abort rather than burn the list.
            if block_giveup:
                block_giveup_streak += 1
                if block_giveup_streak >= max_block_giveups:
                    logger.error(f"  ❌ {block_giveup_streak} videos blocked in a row — aborting run")
                    break
            else:
                block_giveup_streak = 0

            if skip_video:
                continue

            if transcript_data:
                # Insert transcript
                cursor = conn.cursor()
                
                try:
                    import json
                    
                    # Prepare data
                    transcript_data['event_id'] = event_id
                    transcript_data['state_code'] = state
                    transcript_data['state'] = state_name
                    transcript_data['jurisdiction_id'] = jurisdiction_id
                    transcript_data['jurisdiction_name'] = jurisdiction

                    # Capture the real segment count BEFORE serializing — once
                    # 'segments' becomes a JSON string, len() would report the
                    # character count, not the number of caption snippets.
                    segments_list = transcript_data.get('segments') or []
                    segment_count = len(segments_list)

                    # Convert segments list to JSON string
                    if segments_list:
                        transcript_data['segments'] = json.dumps(segments_list)
                    else:
                        transcript_data['segments'] = None

                    # Geo (state_code, state, jurisdiction_id, jurisdiction_name) is
                    # written here from the event mart. The sync_text_ai_geo_from_youtube
                    # trigger still overrides it with the YouTube catalog's canonical
                    # geo when a matching youtube row exists, but no longer clobbers
                    # these with NULL for LocalView-only videos (see migration 087).
                    insert_query = """
                        INSERT INTO bronze.bronze_events_text_ai (
                            event_id, video_id, raw_text, segments, language,
                            is_auto_generated, transcript_source,
                            state_code, state, jurisdiction_id, jurisdiction_name
                        ) VALUES (
                            %(event_id)s, %(video_id)s, %(raw_text)s, %(segments)s::jsonb, %(language)s,
                            %(is_auto_generated)s, %(transcript_source)s,
                            %(state_code)s, %(state)s, %(jurisdiction_id)s, %(jurisdiction_name)s
                        )
                        ON CONFLICT (video_id) DO UPDATE SET
                            raw_text = EXCLUDED.raw_text,
                            segments = EXCLUDED.segments,
                            language = EXCLUDED.language,
                            is_auto_generated = EXCLUDED.is_auto_generated,
                            transcript_source = EXCLUDED.transcript_source,
                            state_code = COALESCE(bronze.bronze_events_text_ai.state_code, EXCLUDED.state_code),
                            state = COALESCE(bronze.bronze_events_text_ai.state, EXCLUDED.state),
                            jurisdiction_id = COALESCE(bronze.bronze_events_text_ai.jurisdiction_id, EXCLUDED.jurisdiction_id),
                            jurisdiction_name = COALESCE(bronze.bronze_events_text_ai.jurisdiction_name, EXCLUDED.jurisdiction_name)
                    """
                    
                    cursor.execute(insert_query, transcript_data)
                    conn.commit()
                    
                    inserted += 1
                    logger.success(f"  ✓ Inserted transcript ({segment_count} segments)")
                    
                    # Commit every 10 transcripts
                    if inserted % 10 == 0:
                        logger.info(f"Progress: {inserted}/{len(events)} transcripts inserted")
                    
                except Exception as e:
                    conn.rollback()
                    error_msg = str(e)
                    if '429' in error_msg or 'Too Many Requests' in error_msg:
                        logger.warning(f"  ✗ Rate limited during insert: {error_msg[:100]}")
                        rate_limited += 1
                        consecutive_rate_limits += 1
                        time.sleep(5)  # Longer pause after rate limit
                    else:
                        logger.error(f"  ✗ Error inserting transcript: {e}")
                    failed += 1
                finally:
                    cursor.close()
            else:
                logger.warning(f"  ⊘ No transcript available")
                # Clean fetch that returned no caption track — negative-cache it
                # so repeat runs prioritise videos we haven't tried yet.
                record_transcript_unavailable(conn, video_id, status="unavailable")
                failed += 1

        # Summary
        logger.info("")
        logger.success("=" * 80)
        logger.success("✓ BACKFILL COMPLETE")
        logger.success("=" * 80)
        logger.success(f"Transcripts inserted: {inserted}")
        logger.success(f"Failed/unavailable: {failed}")
        if rate_limited > 0:
            logger.warning(f"Rate limited: {rate_limited} (consider reducing concurrency)")
        logger.success(f"Total processed: {len(events)}")
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Backfill transcripts for YouTube events')
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated list of state codes (e.g., AL,MA,WI)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of transcripts to fetch'
    )
    parser.add_argument(
        '--retry-after-days',
        type=int,
        default=30,
        help='Re-attempt a previously-unavailable video only after this many '
             'days (default: 30). Never-tried videos are always prioritised first.'
    )
    parser.add_argument(
        '--retry-failed',
        action='store_true',
        help='Ignore the negative cache and re-attempt every missing video, '
             'including ones already found to have no transcript.'
    )

    args = parser.parse_args()

    # Parse states
    states = None
    if args.states:
        states = [s.strip().upper() for s in args.states.split(',')]
        logger.info(f"Filtering to states: {', '.join(states)}")

    # Run backfill
    backfill_transcripts(
        database_url=DATABASE_URL,
        youtube_api_key=YOUTUBE_API_KEY,
        states=states,
        limit=args.limit,
        retry_after_days=args.retry_after_days,
        retry_failed=args.retry_failed,
    )


if __name__ == '__main__':
    main()
