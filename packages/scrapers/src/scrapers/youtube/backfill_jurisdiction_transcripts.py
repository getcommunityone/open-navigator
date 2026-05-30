#!/usr/bin/env python3
"""
Backfill YouTube captions for all videos in a jurisdiction (bronze + optional local cache).

Writes:
- ``bronze.bronze_events_text_ai`` (canonical)
- ``data/cache/gemini_transcript_policy/{state}/{type}/{jurisdiction_id}/01_transcripts/…`` (matches Opus basename)

Permanent caption failures (no subs / disabled / unavailable) may be **tombstoned** in bronze
(``transcript_source`` = ``tombstone:<reason>``, ``has_transcript`` = false).

Each run **clears tombstones** for the jurisdiction (use ``--no-clear-tombstones`` to keep them) and
retries with **cookies** (``youtube_cookies.txt``) plus **yt-dlp** fallback after the caption API.
IP blocks are **not** tombstoned (transient).

Examples::

    # Tuscaloosa — all 400+ bronze videos, skip already on disk or in bronze
    python packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py \\
        --jurisdiction-id municipality_0177256

    # Dry rundev
    python packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py \\
        --jurisdiction-id municipality_0177256 --dry-run

    # Northport — retries tombstoned videos; cookies + yt-dlp fallback (default)
    python packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py \\
        --jurisdiction-id municipality_0155200 --cookies youtube_cookies.txt --delay 10

    # First 50 only, slower pacing
    python packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py \\
        --jurisdiction-id municipality_0177256 --limit 50 --delay 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scrapers.youtube.download_audio_to_drive import (  # noqa: E402
    DEFAULT_YOUTUBE_COOKIES_FILE,
)
from scrapers.youtube.load_youtube_events_to_postgres import (  # noqa: E402
    YouTubeEventsLoader,
)
from llm.gemini.transcript_cache_paths import (  # noqa: E402
    DIR_TRANSCRIPTS,
    jurisdiction_root,
    legacy_transcript_cache_path,
    lookup_jurisdiction_geo_from_db,
    resolve_meeting_event_date,
    resolve_transcript_cache_path,
    transcript_cache_filename,
    transcript_cache_path,
    _is_policy_channel_dir,
)


def _effective_state_code(
    jurisdiction_id: str,
    row: Optional[Dict[str, Any]] = None,
    *,
    explicit: Optional[str] = None,
) -> Optional[str]:
    st = (explicit or "").strip().upper()
    if st:
        return st
    if row:
        st = str(row.get("state_code") or "").strip().upper()
        if st:
            return st
    db_st, _ = lookup_jurisdiction_geo_from_db(jurisdiction_id)
    return db_st

DEFAULT_LOCAL_CACHE = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"
TUSCALOOSA_JURISDICTION_ID = "tuscaloosa_0177256"

# Bronze rows with transcript_source like tombstone:% are skipped on future backfills.
TOMBSTONE_SOURCE_PREFIX = "tombstone:"


def _database_url(explicit: Optional[str]) -> str:
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


_PENDING_ORDER_CLAUSES = {
    # YouTube upload / stream time (matches channel "Latest")
    "published_at": "COALESCE(sub.published_at, sub.event_date::timestamp) DESC NULLS LAST, sub.video_id",
    # Meeting date from title (5/18/2026 in title) then upload time
    "meeting_date": (
        "COALESCE(sub.event_date::timestamp, sub.published_at, sub.last_updated) "
        "DESC NULLS LAST, sub.video_id"
    ),
    "event_date": "sub.event_date DESC NULLS LAST, sub.video_id",
    "last_updated": "sub.last_updated DESC NULLS LAST, sub.video_id",
}


def _sort_timestamp(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).timestamp()
    raw = str(value).strip()
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).timestamp()
        except ValueError:
            continue
    return 0.0


def _row_order_timestamp(row: Dict[str, Any], order_by: str) -> float:
    key_name = (order_by or "published_at").strip().lower()
    if key_name == "meeting_date":
        return _sort_timestamp(row.get("event_date") or row.get("published_at"))
    if key_name == "last_updated":
        return _sort_timestamp(row.get("last_updated"))
    if key_name == "event_date":
        return _sort_timestamp(row.get("event_date"))
    return _sort_timestamp(row.get("published_at") or row.get("event_date"))


def sort_backfill_rows(
    rows: List[Dict[str, Any]],
    order_by: str,
    *,
    prefer_untried: bool = True,
) -> List[Dict[str, Any]]:
    """Restore fetch order after dedupe (dedupe clusters scramble SQL order)."""
    if prefer_untried:
        return sorted(
            rows,
            key=lambda r: (
                int(r.get("transcript_download_attempts") or 0),
                -_row_order_timestamp(r, order_by),
            ),
        )
    return sorted(rows, key=lambda r: -_row_order_timestamp(r, order_by))


def row_needs_backfill(
    row: Dict[str, Any],
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    skip_local_existing: bool,
    include_bronze_existing: bool,
    state_code: Optional[str] = None,
    policy_folder: Optional[Path] = None,
) -> bool:
    """True if this row still needs YouTube fetch and/or local cache sync."""
    if not row.get("bronze_has_transcript"):
        return True
    if include_bronze_existing:
        return True
    if skip_local_existing and local_transcript_exists(
        cache_dir,
        jurisdiction_id,
        row,
        state_code=state_code,
        policy_folder=policy_folder,
    ):
        return False
    if row.get("bronze_has_transcript") and not local_transcript_exists(
        cache_dir,
        jurisdiction_id,
        row,
        state_code=state_code,
        policy_folder=policy_folder,
    ):
        return True
    return False


def fetch_pending_videos(
    database_url: str,
    jurisdiction_id: str,
    *,
    limit: Optional[int] = None,
    skip_bronze: bool = True,
    order_by: str = "published_at",
    video_id: Optional[str] = None,
    prefer_untried: bool = True,
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
            y.channel_id,
            y.duration_minutes,
            y.published_at,
            y.last_updated,
            y.audio_file_path,
            COALESCE(y.transcript_download_attempts, 0) AS transcript_download_attempts,
            y.transcript_download_at,
            y.transcript_file_error,
            t.has_transcript AS bronze_has_transcript
        FROM bronze.bronze_events_youtube y
        LEFT JOIN bronze.bronze_events_text_ai t ON t.video_id = y.video_id
        WHERE y.jurisdiction_id = %s
          AND y.video_id IS NOT NULL
          AND BTRIM(y.video_url) <> ''
    """
    params: list[Any] = [jurisdiction_id]
    if video_id:
        sql += " AND y.video_id = %s"
        params.append(video_id.strip())
    if skip_bronze:
        sql += """
          AND (
            t.video_id IS NULL
            OR COALESCE(t.has_transcript, false) IS NOT TRUE
          )
        """
    sql += """
        ORDER BY y.video_url, y.last_updated DESC NULLS LAST
    """
    order_key = (order_by or "published_at").strip().lower()
    if order_key not in _PENDING_ORDER_CLAUSES:
        raise ValueError(
            f"order_by must be one of: {', '.join(_PENDING_ORDER_CLAUSES)}"
        )
    order_parts: list[str] = []
    if prefer_untried:
        order_parts.append("sub.transcript_download_attempts ASC")
    order_parts.append(_PENDING_ORDER_CLAUSES[order_key])
    sql = f"""
        SELECT * FROM ({sql}) sub
        ORDER BY {", ".join(order_parts)}
    """
    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [apply_resolved_event_date(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def fetch_video_row(
    database_url: str,
    jurisdiction_id: str,
    video_id: str,
) -> Optional[Dict[str, Any]]:
    """Load one catalog row (ignores pending/tombstone filters)."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    y.video_id,
                    y.video_url,
                    y.title,
                    y.event_id,
                    y.event_date::text AS event_date,
                    y.jurisdiction_id,
                    y.channel_id,
                    y.duration_minutes,
                    y.published_at,
                    y.last_updated,
                    y.audio_file_path,
                    COALESCE(y.transcript_download_attempts, 0) AS transcript_download_attempts,
                    y.transcript_download_at,
                    y.transcript_file_error,
                    t.has_transcript AS bronze_has_transcript,
                    t.transcript_source AS bronze_transcript_source
                FROM bronze.bronze_events_youtube y
                LEFT JOIN bronze.bronze_events_text_ai t ON t.video_id = y.video_id
                WHERE y.jurisdiction_id = %s AND y.video_id = %s
                """,
                (jurisdiction_id, video_id.strip()),
            )
            row = cur.fetchone()
            if row:
                return apply_resolved_event_date(dict(row))
            return None
    finally:
        conn.close()


def apply_resolved_event_date(row: Dict[str, Any]) -> Dict[str, Any]:
    """Set ``event_date`` from title or dated audio/transcript basename."""
    resolved = resolve_meeting_event_date(
        str(row.get("title") or ""),
        event_date=row.get("event_date"),
        published_at=row.get("published_at"),
        audio_file_path=row.get("audio_file_path"),
    )
    if resolved:
        row["event_date"] = resolved
    return row


def fix_bronze_event_dates_from_titles(
    database_url: str,
    jurisdiction_id: str,
    *,
    dry_run: bool = False,
) -> int:
    """UPDATE bronze ``event_date`` where title embeds a different calendar date."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    conn = psycopg2.connect(database_url)
    updated = 0
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT video_id, title, event_date::text AS event_date, published_at, audio_file_path
                FROM bronze.bronze_events_youtube
                WHERE jurisdiction_id = %s AND title IS NOT NULL
                """,
                (jurisdiction_id,),
            )
            rows = cur.fetchall()
        for row in rows:
            resolved = resolve_meeting_event_date(
                str(row["title"] or ""),
                event_date=row.get("event_date"),
                published_at=row.get("published_at"),
                audio_file_path=row.get("audio_file_path"),
            )
            if not resolved or resolved == (row.get("event_date") or "")[:10]:
                continue
            updated += 1
            logger.info(
                "{}  {} -> {}  {}",
                row["video_id"],
                row.get("event_date") or "?",
                resolved,
                (row["title"] or "")[:60],
            )
            if dry_run:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE bronze.bronze_events_youtube
                    SET event_date = %s::date, last_updated = NOW()
                    WHERE video_id = %s
                    """,
                    (resolved, row["video_id"]),
                )
        if not dry_run:
            conn.commit()
    finally:
        conn.close()
    return updated


def write_local_from_bronze(
    database_url: str,
    cache_dir: Path,
    jurisdiction_id: str,
    row: Dict[str, Any],
    *,
    state_code: Optional[str] = None,
) -> bool:
    """Copy bronze transcript to local cache without calling YouTube."""
    import json as _json
    import psycopg2
    from psycopg2.extras import RealDictCursor

    video_id = str(row["video_id"])
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT raw_text, segments, language, is_auto_generated, transcript_source
                FROM bronze.bronze_events_text_ai
                WHERE video_id = %s AND has_transcript IS TRUE
                """,
                (video_id,),
            )
            t = cur.fetchone()
    finally:
        conn.close()

    if not t or not (t.get("raw_text") or "").strip():
        return False

    segments = t.get("segments")
    if isinstance(segments, str):
        segments = _json.loads(segments)

    st = _effective_state_code(jurisdiction_id, row, explicit=state_code)
    write_local_transcript(
        local_transcript_path(cache_dir, jurisdiction_id, row, state_code=st),
        row=row,
        yt={
            "video_id": video_id,
            "raw_text": t["raw_text"],
            "segments": segments or [],
            "language": t.get("language"),
            "is_auto_generated": t.get("is_auto_generated"),
            "transcript_source": t.get("transcript_source") or "bronze",
        },
        cache_dir=cache_dir,
        state_code=st,
    )
    return True


def local_transcript_path(
    cache_dir: Path,
    jurisdiction_id: str,
    row: Dict[str, Any],
    *,
    state_code: Optional[str] = None,
) -> Path:
    """Audio-aligned basename: ``YYYY-MM-DD_<sanitized title>.json``."""
    row = apply_resolved_event_date(dict(row))
    st = _effective_state_code(jurisdiction_id, row, explicit=state_code)
    return transcript_cache_path(
        cache_dir,
        jurisdiction_id,
        title=str(row.get("title") or ""),
        event_date=row.get("event_date"),
        state_code=st,
        channel_id=str(row.get("channel_id") or "").strip() or None,
        video_id=str(row.get("video_id") or "").strip() or None,
    )


def local_transcript_exists(
    cache_dir: Path,
    jurisdiction_id: str,
    row: Dict[str, Any],
    *,
    state_code: Optional[str] = None,
    policy_folder: Optional[Path] = None,
) -> bool:
    """Return True if a caption JSON for this row is already on disk."""
    st = _effective_state_code(jurisdiction_id, row, explicit=state_code)
    folder = policy_folder
    if folder is None:
        folder = jurisdiction_root(cache_dir, jurisdiction_id, state_code=st)

    row_resolved = apply_resolved_event_date(dict(row))
    vid = str(row_resolved["video_id"])
    title = str(row_resolved.get("title") or "")
    event_date = row_resolved.get("event_date")
    cid = str(row_resolved.get("channel_id") or "").strip() or None

    if (
        resolve_transcript_cache_path(
            folder,
            video_id=vid,
            title=title,
            event_date=event_date,
        )
        is not None
    ):
        return True

    if cid:
        if _is_policy_channel_dir(folder):
            channel_root = folder
        else:
            channel_root = folder / cid
        if title:
            named = (
                channel_root
                / DIR_TRANSCRIPTS
                / transcript_cache_filename(title, event_date)
            )
            if named.is_file():
                return True

    if policy_folder is not None:
        return False

    if local_transcript_path(cache_dir, jurisdiction_id, row_resolved, state_code=st).is_file():
        return True
    legacy = legacy_transcript_cache_path(
        cache_dir,
        jurisdiction_id,
        vid,
        state_code=st,
        channel_id=cid,
    )
    if legacy.is_file():
        return True
    return False


def write_local_transcript(
    path: Path,
    *,
    row: Dict[str, Any],
    yt: Dict[str, Any],
    cache_dir: Optional[Path] = None,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
) -> Path:
    """Write under ``gemini_transcript_policy`` (``path`` is ignored; kept for callers)."""
    from scrapers.youtube.policy_transcript_cache import (
        write_policy_transcript_cache,
    )

    row = apply_resolved_event_date(dict(row))
    if cache_dir is None:
        raise ValueError("cache_dir is required for write_local_transcript")
    root = cache_dir
    yt_block = {
        k: v
        for k, v in yt.items()
        if k
        not in ("caption_raw_data", "caption_formatted", "caption_preserve_formatting")
    }
    return write_policy_transcript_cache(
        root,
        jurisdiction_id=str(row["jurisdiction_id"]),
        state_code=state_code or str(row.get("state_code") or ""),
        row=row,
        yt=yt_block,
        caption_raw_data=yt.get("caption_raw_data"),
        jurisdiction_type=jurisdiction_type or row.get("jurisdiction_type"),
    )


def clear_transcript_tombstones(
    database_url: str,
    jurisdiction_id: str,
    *,
    video_id: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """Delete bronze rows marked ``tombstone:*`` so the next fetch retries YouTube captions."""
    import psycopg2

    sql = """
        DELETE FROM bronze.bronze_events_text_ai t
        USING bronze.bronze_events_youtube y
        WHERE t.video_id = y.video_id
          AND y.jurisdiction_id = %s
          AND COALESCE(t.transcript_source, '') LIKE 'tombstone:%%'
    """
    params: list[Any] = [jurisdiction_id]
    if video_id:
        sql += " AND y.video_id = %s"
        params.append(video_id.strip())

    count_sql = """
        SELECT COUNT(*)
        FROM bronze.bronze_events_text_ai t
        JOIN bronze.bronze_events_youtube y ON t.video_id = y.video_id
        WHERE y.jurisdiction_id = %s
          AND COALESCE(t.transcript_source, '') LIKE 'tombstone:%%'
    """
    if video_id:
        count_sql += " AND y.video_id = %s"

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            if dry_run:
                cur.execute(count_sql, params)
                return int(cur.fetchone()[0])
            cur.execute(sql, params)
            deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


def tombstone_source(reason: str) -> str:
    return f"{TOMBSTONE_SOURCE_PREFIX}{reason}"


def permanent_failure_reason(
    exc: Optional[BaseException] = None,
    *,
    via_proxy: bool = False,
) -> Optional[str]:
    """
    Return a tombstone reason for permanent caption absence, or None to allow retry.

    Never tombstone rate limits / IP blocks (transient).
    """
    if via_proxy:
        return None
    if exc is not None:
        if is_rate_limited(exc):
            return None
        name = type(exc).__name__.upper()
        msg = str(exc).upper()
        if "TRANSCRIPTSDISABLED" in name or (
            "DISABLED" in msg and ("CAPTION" in msg or "TRANSCRIPT" in msg)
        ):
            return "captions_unavailable"
        if "VIDEOUNAVAILABLE" in name or any(
            k in msg for k in ("UNAVAILABLE", "PRIVATE", "DELETED", "REMOVED")
        ):
            return "video_unavailable"
        if "NOTRANSCRIPT" in name or "NO TRANSCRIPT" in msg:
            return "captions_unavailable"
        return None
    return "captions_unavailable"


def write_transcript_tombstone(
    loader: YouTubeEventsLoader,
    *,
    event_id: int,
    video_id: str,
    reason: str,
) -> None:
    """Record has_transcript=false so pending queries skip this video."""
    source = tombstone_source(reason)
    cur = loader.conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO bronze.bronze_events_text_ai (
                event_id, video_id, raw_text, segments, language,
                is_auto_generated, transcript_source, has_transcript, transcript_quality
            ) VALUES (
                %(event_id)s, %(video_id)s, NULL, NULL, NULL,
                false, %(transcript_source)s, false, 'none'
            )
            ON CONFLICT (video_id) DO UPDATE SET
                event_id = COALESCE(EXCLUDED.event_id, bronze.bronze_events_text_ai.event_id),
                raw_text = NULL,
                segments = NULL,
                language = NULL,
                is_auto_generated = false,
                transcript_source = EXCLUDED.transcript_source,
                has_transcript = false,
                transcript_quality = 'none',
                last_updated = CURRENT_TIMESTAMP
            """,
            {
                "event_id": event_id,
                "video_id": video_id,
                "transcript_source": source,
            },
        )
        loader.conn.commit()
    finally:
        cur.close()


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


@dataclass
class TranscriptProbeResult:
    ok: bool
    video_id: str
    reason: str  # ok | blocked | no_transcript | error
    detail: str = ""
    source: str = ""
    summary: str = ""
    elapsed_sec: float = 0.0


def probe_transcript_access(loader: YouTubeEventsLoader, video_id: str) -> TranscriptProbeResult:
    """Quick health check before a long backfill batch."""
    started = time.monotonic()
    try:
        data = loader.fetch_transcript(video_id)
        elapsed = time.monotonic() - started
        if data and (data.get("raw_text") or "").strip():
            from scrapers.youtube.transcript_api_client import (
                summarize_transcript_payload,
            )

            return TranscriptProbeResult(
                True,
                video_id,
                "ok",
                source=str(data.get("transcript_source") or ""),
                summary=summarize_transcript_payload(data),
                elapsed_sec=elapsed,
            )
        return TranscriptProbeResult(
            False,
            video_id,
            "no_transcript",
            "Caption API and yt-dlp returned no text (may be disabled on this video, not always IP block)",
            elapsed_sec=elapsed,
        )
    except Exception as exc:
        elapsed = time.monotonic() - started
        from scrapers.youtube.transcript_api_client import format_transcript_error

        detail = format_transcript_error(exc, max_len=400)
        if is_rate_limited(exc):
            return TranscriptProbeResult(
                False,
                video_id,
                "blocked",
                detail,
                elapsed_sec=elapsed,
            )
        return TranscriptProbeResult(
            False,
            video_id,
            "error",
            detail,
            elapsed_sec=elapsed,
        )


def format_transcript_block_help(
    *,
    cookies_path: Optional[str],
    proxy_url: Optional[str],
    probe: TranscriptProbeResult,
) -> str:
    """Actionable multi-line message for IP / request blocks."""
    from scrapers.youtube.transcript_api_client import describe_caption_egress

    egress = describe_caption_egress(
        explicit_proxy_url=proxy_url,
        cookies_path=cookies_path,
        ytdlp_fallback=True,
    )
    lines = [
        f"YouTube blocked transcript access on probe video {probe.video_id}.",
        f"  Reason: {probe.detail or probe.reason}",
        f"  Probe took: {probe.elapsed_sec:.1f}s",
        "",
        "What is configured:",
        f"  caption API: {egress['caption_api']}",
        f"  caption egress: {egress['caption_egress_detail']}",
        f"  cookies: {cookies_path or '(none — export youtube_cookies.txt while logged into YouTube)'}",
        f"  yt-dlp fallback: {egress['ytdlp_egress_detail']}",
        "",
        "This is usually YouTube throttling the caption endpoint (/api/timedtext) or blocking the egress IP.",
        "",
        "Fix (try in order):",
        "  1. Run: .venv/bin/python packages/scrapers/src/scrapers/youtube/verify_webshare_proxy.py",
        "  2. Set WEBSHARE_FILTER_IP_LOCATIONS=us and increase --delay (25+)",
        "  3. Re-export youtube_cookies.txt from Chrome while logged into YouTube",
        "  4. Wait 24–48h without caption fetches, then retry with --limit 5",
        "  5. Confirm browser can open youtube.com/watch?v=ajsME66iXbY and show captions",
        "  6. See packages/scrapers/src/scrapers/youtube/BYPASS_IP_BLOCK.md",
        "",
        "Flags: --skip-probe | --abort-on-probe-fail",
    ]
    return "\n".join(lines)


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
    from llm.gemini.transcript_cache_paths import resolve_canonical_jurisdiction_id

    jurisdiction_id = resolve_canonical_jurisdiction_id(args.jurisdiction_id.strip())
    cache_dir = Path(args.local_cache_dir).resolve()
    state_code = _effective_state_code(
        jurisdiction_id, explicit=(getattr(args, "state", None) or "").strip() or None
    )
    prefer_untried = not getattr(args, "no_prefer_untried", False)
    if os.getenv("NO_PREFER_UNTRIED", "").strip().lower() in ("1", "true", "yes"):
        prefer_untried = False

    policy_folder: Optional[Path] = None

    def ensure_policy_folder() -> Path:
        nonlocal policy_folder
        if policy_folder is None:
            policy_folder = jurisdiction_root(
                cache_dir, jurisdiction_id, state_code=state_code
            )
        return policy_folder

    if getattr(args, "fix_event_dates_from_title", False):
        count = fix_bronze_event_dates_from_titles(
            db_url, jurisdiction_id, dry_run=args.dry_run
        )
        if args.dry_run:
            logger.info(
                "Dry run: {} video(s) would get event_date from title for {}",
                count,
                jurisdiction_id,
            )
        else:
            logger.success(
                "Updated event_date from title for {} video(s) in {}",
                count,
                jurisdiction_id,
            )
        return 0

    video_filter = (getattr(args, "video_id", None) or "").strip()

    if not getattr(args, "no_clear_tombstones", False):
        cleared = clear_transcript_tombstones(
            db_url,
            jurisdiction_id,
            video_id=video_filter or None,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            logger.info(
                "Dry run: would clear {} tombstone row(s) for {}{}",
                cleared,
                jurisdiction_id,
                f" video {video_filter}" if video_filter else "",
            )
        elif cleared:
            logger.info(
                "Cleared {} tombstone row(s) for {} — will retry caption fetch",
                cleared,
                jurisdiction_id,
            )

    if getattr(args, "bronze_to_local", False):
        if not video_filter:
            raise SystemExit("--bronze-to-local requires --video-id")
        row = fetch_video_row(db_url, jurisdiction_id, video_filter)
        if not row:
            raise SystemExit(f"Video {video_filter} not in bronze for {jurisdiction_id}")
        if write_local_from_bronze(
            db_url, cache_dir, jurisdiction_id, row, state_code=state_code
        ):
            path = local_transcript_path(
                cache_dir, jurisdiction_id, row, state_code=state_code
            )
            logger.success("Wrote local transcript from bronze: {}", path)
            return 0
        raise SystemExit(
            f"No bronze transcript for {video_filter} (has_transcript=false or empty)"
        )

    if video_filter:
        row = fetch_video_row(db_url, jurisdiction_id, video_filter)
        if not row:
            raise SystemExit(f"Video {video_filter} not in bronze for {jurisdiction_id}")
        src = str(row.get("bronze_transcript_source") or "")
        if src.startswith(TOMBSTONE_SOURCE_PREFIX):
            logger.info(
                "Retrying {} after tombstone clear (was {})",
                video_filter,
                src,
            )
        if row.get("bronze_has_transcript") and not args.include_bronze_existing:
            if args.skip_local_existing and local_transcript_exists(
                cache_dir,
                jurisdiction_id,
                row,
                state_code=state_code,
                policy_folder=ensure_policy_folder(),
            ):
                logger.success(
                    "{} already has bronze + local transcript — nothing to do",
                    video_filter,
                )
                return 0
            if write_local_from_bronze(
                db_url, cache_dir, jurisdiction_id, row, state_code=state_code
            ):
                logger.success(
                    "Bronze transcript exists; wrote local cache (no YouTube fetch). "
                    "Use --include-bronze-existing to re-download from YouTube.",
                )
                return 0
            logger.info(
                "{} has bronze.has_transcript=true — use --include-bronze-existing to re-fetch from YouTube",
                video_filter,
            )
            return 0
        pending = [row]
    else:
        newest_n = int(getattr(args, "newest", 0) or 0)
        if newest_n > 0:
            catalog = fetch_pending_videos(
                db_url,
                jurisdiction_id,
                limit=newest_n,
                skip_bronze=False,
                order_by=args.order_by,
                prefer_untried=prefer_untried,
            )
            local_pf = (
                ensure_policy_folder()
                if not args.include_bronze_existing
                else None
            )
            pending = [
                r
                for r in catalog
                if row_needs_backfill(
                    r,
                    cache_dir,
                    jurisdiction_id,
                    skip_local_existing=args.skip_local_existing,
                    include_bronze_existing=args.include_bronze_existing,
                    state_code=state_code,
                    policy_folder=local_pf,
                )
            ]
            logger.info(
                "Newest mode: {} catalog row(s) → {} need fetch/sync",
                len(catalog),
                len(pending),
            )
        else:
            pending = fetch_pending_videos(
                db_url,
                jurisdiction_id,
                limit=args.limit,
                skip_bronze=not args.include_bronze_existing,
                order_by=args.order_by,
                prefer_untried=prefer_untried,
            )
            if args.skip_local_existing:
                local_pf = ensure_policy_folder()
                filtered: List[Dict[str, Any]] = []
                for row in pending:
                    if local_transcript_exists(
                        cache_dir,
                        jurisdiction_id,
                        row,
                        state_code=state_code,
                        policy_folder=local_pf,
                    ):
                        continue
                    filtered.append(row)
                skipped_local = len(pending) - len(filtered)
                pending = filtered
                if skipped_local:
                    logger.info("Skipped {} already in local cache", skipped_local)

    if pending and not video_filter and not getattr(args, "no_dedupe_duplicates", False):
        from scrapers.youtube.dedupe_meeting_videos import (
            dedupe_meeting_rows,
            log_duplicate_skips,
        )

        title_by_id = {r["video_id"]: str(r.get("title") or "") for r in pending}
        row_by_id = {r["video_id"]: r for r in pending}
        local_pf = ensure_policy_folder()
        for row in pending:
            row["local_has_transcript"] = local_transcript_exists(
                cache_dir,
                jurisdiction_id,
                row,
                state_code=state_code,
                policy_folder=local_pf,
            )
            row["has_transcript"] = (
                row.get("bronze_has_transcript") is True
                or row.get("local_has_transcript") is True
            )
        pending, dedupe = dedupe_meeting_rows(pending)
        log_duplicate_skips(dedupe, title_by_id=title_by_id, row_by_id=row_by_id)

    pending = sort_backfill_rows(
        pending, args.order_by, prefer_untried=prefer_untried
    )
    from llm.gemini.policy_exclusions import filter_rows_not_excluded

    pending = filter_rows_not_excluded(
        pending, cache_dir, jurisdiction_id, state_code=state_code
    )

    row_by_id = {r.get("video_id"): r for r in pending if r.get("video_id")}

    logger.info(
        "Jurisdiction {} — {} video(s) to fetch (order: {} desc{}, prefer_untried={})",
        jurisdiction_id,
        len(pending),
        args.order_by,
        ", untried first" if prefer_untried else "",
        prefer_untried,
    )

    batch_id = (getattr(args, "batch_id", None) or os.getenv("BATCH_JOB_ID") or "").strip()
    batch_store = None
    if batch_id:
        from api.batch_jobs.batch_job_status import (
            BatchJobStore,
            count_policy_files_for_jurisdiction,
        )

        batch_store = BatchJobStore(batch_id)

    def _batch_video(
        vid: str,
        status: str,
        *,
        title: str = "",
        error: str = "",
        source: str = "",
    ) -> None:
        if batch_store:
            from api.batch_jobs.batch_job_status import (
                duration_seconds_from_catalog_minutes,
            )

            batch_store.record_video(
                jurisdiction_id=jurisdiction_id,
                video_id=vid,
                status=status,
                title=title,
                error=error,
                transcript_source=source,
                duration_seconds=duration_seconds_from_catalog_minutes(
                    row_by_id.get(vid, {}).get("duration_minutes")
                )
            )

    if args.dry_run:
        for i, row in enumerate(pending, 1):
            pub = row.get("published_at")
            pub_s = pub.strftime("%Y-%m-%d") if hasattr(pub, "strftime") else str(pub or "?")[:10]
            attempts = int(row.get("transcript_download_attempts") or 0)
            print(
                f"{i:4}. {row['video_id']}  attempts={attempts}  pub={pub_s}  "
                f"meeting={row.get('event_date') or '?'}  tx={row.get('bronze_has_transcript')}  "
                f"{(row.get('title') or '')[:55]}"
            )
        if batch_store:
            j_name = (getattr(args, "jurisdiction_name", None) or "").strip()
            batch_store.jurisdiction_start(
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                jurisdiction_name=j_name,
                pending_videos=len(pending),
            )
            batch_store.jurisdiction_finish(
                jurisdiction_id=jurisdiction_id,
                exit_code=0,
                stats={"dry_run": len(pending)},
            )
        return 0

    if not pending:
        logger.info("Nothing to fetch — all transcripts present (NOOP)")
        if batch_store:
            from api.batch_jobs.batch_job_status import (
                count_policy_files_for_jurisdiction,
                policy_disk_file_counts,
            )

            j_name = (getattr(args, "jurisdiction_name", None) or "").strip()
            batch_store.jurisdiction_start(
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                jurisdiction_name=j_name,
                pending_videos=0,
            )
            batch_store.jurisdiction_finish(
                jurisdiction_id=jurisdiction_id,
                exit_code=0,
                stats={"noop": 1},
                file_counts=policy_disk_file_counts(
                    count_policy_files_for_jurisdiction(
                        cache_dir,
                        state_code=state_code,
                        jurisdiction_id=jurisdiction_id,
                    )
                ),
            )
        return 0

    cookies = resolve_cookies_path(args.cookies or None)
    proxy = (args.proxy or os.getenv("YOUTUBE_TRANSCRIPT_PROXY") or "").strip() or None
    from scrapers.youtube.transcript_api_client import (
        check_proxy_reachable,
        log_caption_fetch_setup,
        resolve_ytdlp_proxy_url,
        ytdlp_proxy_is_webshare,
    )

    ytdlp_proxy = resolve_ytdlp_proxy_url(proxy)

    log_caption_fetch_setup(
        logger,
        cookies_path=cookies,
        explicit_proxy_url=proxy,
        ytdlp_fallback=not args.no_ytdlp_fallback,
        verify_webshare=True,
    )
    if proxy and not ytdlp_proxy_is_webshare(proxy):
        ok, msg = check_proxy_reachable(proxy)
        if not ok:
            logger.error(
                "YOUTUBE_TRANSCRIPT_PROXY not reachable from this shell: {}. "
                "Fix the URL/port or unset it (Webshare via PROXY_* still applies to caption API). "
                "On WSL, 127.0.0.1 is Linux — use the Windows host IP if the VPN runs on Windows.",
                msg,
            )
            return 2
        logger.info("YOUTUBE_TRANSCRIPT_PROXY port check: {}", msg)

    transcript_source = (getattr(args, "transcript_source", None) or "auto").strip().lower()
    if args.no_ytdlp_fallback and transcript_source == "auto":
        transcript_source = "api-only"
    if transcript_source == "ytdlp-only":
        logger.info("Caption path: yt-dlp subtitles only (youtube-transcript-api skipped)")
    elif transcript_source == "api-only":
        logger.info("Caption path: youtube-transcript-api only (--no-ytdlp-fallback)")

    loader = YouTubeEventsLoader(
        database_url=db_url,
        fetch_transcripts=False,
        transcript_delay=args.delay,
        use_ytdlp_fallback=(
            transcript_source == "ytdlp-only" or not args.no_ytdlp_fallback
        ),
        transcript_source=transcript_source,
        cookies_file=cookies,
        proxy_url=ytdlp_proxy,
        ensure_schema_setup=False,
    )

    from scrapers.youtube.bronze_transcript_tracking import (
        ensure_bronze_youtube_transcript_columns,
        record_transcript_download_error,
        record_transcript_download_success,
    )

    ensure_bronze_youtube_transcript_columns(loader.conn)

    stats = {"ok": 0, "fail": 0, "rate_limit": 0, "empty": 0, "tombstoned": 0}
    use_tombstones = args.write_bronze and not getattr(args, "no_tombstones", False)
    consecutive_rl = 0
    max_rl = args.max_consecutive_rate_limits
    exit_code = 0

    probe_id = (args.probe_video_id or "").strip() or "ajsME66iXbY"
    if args.skip_probe or video_filter:
        probe_id = ""
    if probe_id:
        if transcript_source == "ytdlp-only":
            logger.info("Probe: yt-dlp only for {}…", probe_id)
        elif transcript_source == "api-only":
            logger.info("Probe: youtube-transcript-api only for {}…", probe_id)
        else:
            logger.info(
                "Probe: {} — caption API first, yt-dlp fallback if enabled…",
                probe_id,
            )
        probe = probe_transcript_access(loader, probe_id)
        if probe.ok:
            logger.success(
                "Probe OK {} in {:.1f}s — {}",
                probe_id,
                probe.elapsed_sec,
                probe.summary or probe.source or "captions received",
            )
        elif not probe.ok and probe.reason == "blocked":
            help_text = format_transcript_block_help(
                cookies_path=cookies,
                proxy_url=proxy,
                probe=probe,
            )
            if getattr(args, "abort_on_probe_fail", False):
                logger.error("{}\n", help_text)
                return 2
            wait = min(args.delay * (2**consecutive_rl), args.max_backoff)
            logger.error("{}\n  Continuing anyway after {:.0f}s (use --abort-on-probe-fail to stop).", help_text, wait)
            time.sleep(wait)
            consecutive_rl += 1
        elif not probe.ok:
            logger.warning(
                "Probe {} failed in {:.1f}s: {} — {}",
                probe_id,
                probe.elapsed_sec,
                probe.reason,
                probe.detail or "(no detail)",
            )

    from scrapers.youtube.transcript_api_client import (
        format_transcript_error,
        summarize_transcript_payload,
    )

    if batch_store:
        j_name = (getattr(args, "jurisdiction_name", None) or "").strip()
        batch_store.jurisdiction_start(
            state_code=state_code,
            jurisdiction_id=jurisdiction_id,
            jurisdiction_name=j_name,
            pending_videos=len(pending),
        )

    try:
        for i, row in enumerate(pending, 1):
            video_id = row["video_id"]
            test_url = str(row.get("video_url") or "").strip() or f"https://www.youtube.com/watch?v={video_id}"
            title_snip = (str(row.get("title") or "")[:60]).strip()
            row_title = str(row.get("title") or "")
            if i > 1:
                delay = args.delay
                if consecutive_rl > 0:
                    delay = min(args.delay * (2**consecutive_rl), args.max_backoff)
                    logger.warning("Backoff {:.1f}s after rate limit", delay)
                time.sleep(delay)

            logger.info("[{}/{}] {} — {}", i, len(pending), video_id, title_snip or "(no title)")
            if batch_store:
                batch_store.video_start(
                    jurisdiction_id=jurisdiction_id,
                    video_id=video_id,
                    title=row_title,
                )
            event_id = row.get("event_id")
            via_socks = bool(proxy and "socks" in proxy.lower())

            if (
                row.get("bronze_has_transcript")
                and not args.include_bronze_existing
                and not args.no_local_cache
            ):
                if write_local_from_bronze(db_url, cache_dir, jurisdiction_id, row):
                    stats["ok"] += 1
                    _batch_video(video_id, "ok", title=row_title, source="bronze_sync")
                    record_transcript_download_success(
                        loader.conn,
                        video_id,
                        local_transcript_path(
                            cache_dir, jurisdiction_id, row, state_code=state_code
                        ),
                    )
                    logger.success("Synced bronze → local for {} (skip YouTube)", video_id)
                    continue

            try:
                yt = loader.fetch_transcript(video_id)
                if yt is None:
                    reason = permanent_failure_reason(None, via_proxy=via_socks)
                    if reason and use_tombstones and event_id:
                        write_transcript_tombstone(
                            loader,
                            event_id=int(event_id),
                            video_id=video_id,
                            reason=reason,
                        )
                        stats["tombstoned"] += 1
                        _batch_video(video_id, "tombstoned", title=row_title, error=reason or "")
                        record_transcript_download_error(
                            loader.conn, video_id, reason or "captions_unavailable"
                        )
                        logger.info(
                            "Tombstoned {} ({}) — will not retry on future backfills. Test URL: {}",
                            video_id,
                            reason,
                            test_url,
                        )
                    else:
                        stats["fail"] += 1
                        err = getattr(loader, "_last_ytdlp_transcript_error", None) or ""
                        err_msg = str(err) or "no transcript returned"
                        _batch_video(video_id, "fail", title=row_title, error=err_msg)
                        record_transcript_download_error(
                            loader.conn, video_id, err_msg
                        )
                        if via_socks:
                            logger.warning(
                                "No transcript for {} — SOCKS proxy {} cannot reach YouTube "
                                "(Connection reset by peer). Unset YOUTUBE_TRANSCRIPT_PROXY or use a "
                                "residential/VPN egress that supports youtube.com; 9091/Tor often fails here.",
                                video_id,
                                proxy,
                            )
                        else:
                            logger.warning(
                                "No transcript for {} — this upload has no captions (API + yt-dlp); "
                                "skip or use audio/Whisper. Not an IP block if you see 'Captions disabled by uploader' above.",
                                video_id,
                            )
                    continue
            except Exception as exc:
                if is_rate_limited(exc):
                    stats["rate_limit"] += 1
                    rl_err = format_transcript_error(exc, max_len=300)
                    _batch_video(
                        video_id,
                        "rate_limit",
                        title=row_title,
                        error=rl_err,
                    )
                    record_transcript_download_error(loader.conn, video_id, rl_err)
                    consecutive_rl += 1
                    wait = min(args.delay * (2**consecutive_rl), args.max_backoff)
                    logger.warning(
                        "IP blocked / rate limited on {} ({}/{}) — next sleep {:.0f}s (not tombstoned)",
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
                reason = permanent_failure_reason(exc, via_proxy=via_socks)
                if reason and use_tombstones and event_id:
                    write_transcript_tombstone(
                        loader,
                        event_id=int(event_id),
                        video_id=video_id,
                        reason=reason,
                    )
                    stats["tombstoned"] += 1
                    _batch_video(video_id, "tombstoned", title=row_title, error=reason or "")
                    record_transcript_download_error(
                        loader.conn, video_id, reason or "captions_unavailable"
                    )
                    logger.info(
                        "Tombstoned {} ({}) — will not retry on future backfills. Test URL: {}",
                        video_id,
                        reason,
                        test_url,
                    )
                else:
                    stats["fail"] += 1
                    err_msg = format_transcript_error(exc, max_len=300)
                    _batch_video(video_id, "fail", title=row_title, error=err_msg)
                    record_transcript_download_error(loader.conn, video_id, err_msg)
                    logger.warning(
                        "No transcript for {} — {}",
                        video_id,
                        err_msg,
                    )
                consecutive_rl = 0
                continue

            consecutive_rl = 0
            if not (yt.get("raw_text") or "").strip():
                stats["empty"] += 1
                _batch_video(video_id, "empty", title=row_title)
                record_transcript_download_error(
                    loader.conn, video_id, "empty_transcript"
                )
                if use_tombstones and event_id:
                    write_transcript_tombstone(
                        loader,
                        event_id=int(event_id),
                        video_id=video_id,
                        reason="empty_transcript",
                    )
                    stats["tombstoned"] += 1
                    logger.info(
                        "Tombstoned {} (empty_transcript) — will not retry on future backfills. Test URL: {}",
                        video_id,
                        test_url,
                    )
                continue

            written_path = None
            if not args.no_local_cache:
                written_path = write_local_transcript(
                    local_transcript_path(
                        cache_dir, jurisdiction_id, row, state_code=state_code
                    ),
                    row=row,
                    yt=yt,
                    cache_dir=cache_dir,
                    state_code=state_code,
                )

            if args.write_bronze:
                import json as _json

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
            _batch_video(
                video_id,
                "ok",
                title=row_title,
                source=str(yt.get("transcript_source") or ""),
            )
            record_transcript_download_success(
                loader.conn, video_id, written_path
            )
            logger.success(
                "OK {} — {} url={}",
                video_id,
                summarize_transcript_payload(yt),
                test_url,
            )
            if stats["ok"] % 25 == 0:
                logger.info("Progress: {}", stats)

    finally:
        if batch_store:
            exit_code = 0 if stats["rate_limit"] < max_rl else 2
            from api.batch_jobs.batch_job_status import (
                policy_disk_file_counts,
            )

            file_counts = policy_disk_file_counts(
                count_policy_files_for_jurisdiction(
                    cache_dir,
                    state_code=state_code,
                    jurisdiction_id=jurisdiction_id,
                )
            )
            batch_store.jurisdiction_finish(
                jurisdiction_id=jurisdiction_id,
                exit_code=exit_code,
                stats=stats,
                file_counts=file_counts,
            )

    loader.close()
    logger.info("Done: {}", stats)
    return 0 if stats["rate_limit"] < max_rl else 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jurisdiction-id",
        default=TUSCALOOSA_JURISDICTION_ID,
    )
    parser.add_argument(
        "--state",
        default="",
        help="Two-letter state for policy cache path (default: bronze lookup)",
    )
    parser.add_argument("--database-url", default="")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--order-by",
        choices=tuple(_PENDING_ORDER_CLAUSES.keys()),
        default="published_at",
        help="Sort key: published_at = YouTube Latest; meeting_date = date in title",
    )
    parser.add_argument(
        "--newest",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Process like channel Latest: N newest catalog uploads that still need "
            "captions and/or local cache (not only oldest pending backlog)"
        ),
    )
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between YouTube fetches")
    parser.add_argument(
        "--probe-video-id",
        default="ajsME66iXbY",
        help="Probe this video before batch; backs off if IP-blocked",
    )
    parser.add_argument("--skip-probe", action="store_true", help="Skip pre-batch IP probe")
    parser.add_argument(
        "--abort-on-probe-fail",
        action="store_true",
        help="Exit immediately when probe hits IP/request block (default: sleep and continue)",
    )
    parser.add_argument(
        "--cookies",
        default="",
        help="Netscape cookies.txt (or set YOUTUBE_COOKIES / repo youtube_cookies.txt)",
    )
    parser.add_argument("--proxy", default="", help="Proxy URL (or YOUTUBE_TRANSCRIPT_PROXY)")
    parser.add_argument(
        "--transcript-source",
        choices=("auto", "api-only", "ytdlp-only"),
        default="auto",
        help=(
            "auto = caption API then yt-dlp; api-only = youtube-transcript-api; "
            "ytdlp-only = yt-dlp subtitles only (skip /api/timedtext)"
        ),
    )
    parser.add_argument(
        "--no-ytdlp-fallback",
        action="store_true",
        help="Same as --transcript-source api-only",
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
        "--video-id",
        default="",
        help="Process only this YouTube video ID (e.g. ZEUtD3gLRF4)",
    )
    parser.add_argument(
        "--include-bronze-existing",
        action="store_true",
        help="Re-fetch even when bronze.has_transcript is true",
    )
    parser.add_argument(
        "--bronze-to-local",
        action="store_true",
        help="With --video-id: copy bronze transcript to local cache only (no YouTube)",
    )
    parser.add_argument(
        "--fix-event-dates-from-title",
        action="store_true",
        help="Update bronze event_date from meeting date in title (use --dry-run to preview)",
    )
    parser.add_argument(
        "--no-dedupe-duplicates",
        action="store_true",
        help="Fetch every bronze row even when same meeting title/duration duplicates exist",
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
    parser.add_argument(
        "--no-tombstones",
        action="store_true",
        help="Do not write tombstone rows for permanent caption failures (will retry those videos)",
    )
    parser.add_argument(
        "--no-clear-tombstones",
        action="store_true",
        help="Do not delete existing tombstone:* rows before fetching (default: clear and retry)",
    )
    parser.add_argument(
        "--no-prefer-untried",
        action="store_true",
        help="Order only by --order-by (do not fetch never-tried videos before retries)",
    )
    parser.add_argument("--no-write-bronze", action="store_false", dest="write_bronze")
    parser.add_argument(
        "--local-cache-dir",
        type=Path,
        default=DEFAULT_LOCAL_CACHE,
    )
    parser.add_argument(
        "--batch-id",
        default="",
        help="Batch job id for status dashboard (or set BATCH_JOB_ID)",
    )
    parser.add_argument(
        "--jurisdiction-name",
        default="",
        help="Display name for batch dashboard jurisdiction row",
    )
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
