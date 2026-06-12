"""Bulk-download YouTube thumbnails for every video in the warehouse.

YouTube thumbnails are static images on the i.ytimg.com CDN, addressed purely by
video id:

    https://i.ytimg.com/vi/<VIDEO_ID>/hqdefault.jpg      # always exists
    https://i.ytimg.com/vi/<VIDEO_ID>/maxresdefault.jpg  # HD, only if uploaded

These are plain image GETs — they do NOT consume the YouTube Data API quota, so
this scales to all ~200k+ ``video_id``s in ``bronze.bronze_event_youtube``
without an API key. The frontend mirror of this URL logic lives in
``web_app/src/lib/youtubeThumbnail.ts``.

All thumbnails live under a single ``data/thumbnails`` root, but mirror the
**same subfolder hierarchy and human-readable meeting naming as the
scraped-meetings cache** (e.g. ``…/AL/municipality/tuscumbia_0177280/…``):

    data/thumbnails/{ST}/{type}/{place_slug}_{geoid}/{year}/{stem}.jpg

where ``{stem}`` is the canonical ``YYYY-MM-DD_meeting_title_snake`` meeting stem.

Misses (a ``404`` on every quality, or a network give-up) are recorded to a
cache manifest under ``data/thumbnails/_misses/`` as JSONL, split by reason:

    not_found    every quality 404'd → the video is private/deleted (no thumbnail)
    fetch_error  transient network failure after retries → worth retrying

On resume, ``not_found`` ids are skipped (don't re-hit deleted videos) but
``fetch_error`` ids are retried. The DB post-processing step (``--sync-db`` /
``--sync-only``) reflects the whole cache — the thumbnail files on disk AND the
miss manifest — into ``bronze.bronze_youtube_thumbnail`` so availability is
queryable in the warehouse (``status`` = downloaded | not_found | fetch_error).

Usage:
    python -m scrapers.youtube.download_thumbnails                 # all videos -> data/thumbnails
    python -m scrapers.youtube.download_thumbnails --limit 1000    # smoke test
    python -m scrapers.youtube.download_thumbnails --shard 0/4     # one of 4 parallel workers
    python -m scrapers.youtube.download_thumbnails --sync-db       # download, then sync status to bronze
    python -m scrapers.youtube.download_thumbnails --sync-only     # only sync existing cache -> bronze
    python -m scrapers.youtube.download_thumbnails --dry-run       # show planned paths + counts
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import psycopg2
from loguru import logger
from psycopg2.extras import execute_values

# Cross-package helpers live under the repo root (core_lib / llm / scripts).
_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core_lib.gdrive_paths import resolve_scraped_meetings_output_root  # noqa: E402
from llm.gemini.transcript_cache_paths import (  # noqa: E402
    scraped_meetings_jurisdiction_dir,
)
from scripts.discovery.meeting_document_naming import (  # noqa: E402
    slugify_meeting_filename,
)

QUALITIES = ("default", "mqdefault", "hqdefault", "sddefault", "maxresdefault")
UNASSIGNED_SUBDIR = "_unassigned"  # videos with no jurisdiction
MISSES_SUBDIR = "_misses"          # cache manifest of not_found / fetch_error
STATUS_TABLE = "bronze.bronze_youtube_thumbnail"
REASON_NOT_FOUND = "not_found"
REASON_FETCH_ERROR = "fetch_error"
DEFAULT_THUMBNAILS_ROOT = Path("data/thumbnails")
DEFAULT_DSN = (
    os.getenv("DATABASE_URL")
    or os.getenv("NEON_DATABASE_URL_DEV")
    or "postgresql://postgres:password@localhost:5433/open_navigator"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Video:
    """One YouTube row, with everything needed to place its thumbnail."""

    __slots__ = ("video_id", "jurisdiction_id", "state_code", "place_name",
                 "event_date", "title", "dest")

    def __init__(self, video_id, jurisdiction_id, state_code, place_name,
                 event_date, title):
        self.video_id: str = video_id
        self.jurisdiction_id: str | None = jurisdiction_id or None
        self.state_code: str | None = (state_code or None)
        self.place_name: str | None = place_name or None
        self.event_date: date | None = _as_date(event_date)
        self.title: str | None = title or None
        self.dest: Path | None = None


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _thumb_url(video_id: str, quality: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/{quality}.jpg"


def _meeting_stem(video: Video) -> str:
    """Canonical ``YYYY-MM-DD_title_snake`` meeting stem (``undated`` if no date).

    Falls back to the video id when the title slug is missing/too weak, so the
    stem is always non-empty.
    """
    date_prefix = video.event_date.isoformat() if video.event_date else "undated"
    slug = slugify_meeting_filename(video.title or "")
    if len(slug) < 4:
        slug = slugify_meeting_filename(video.video_id) or video.video_id.lower()
    return f"{date_prefix}_{slug}"


def plan_destinations(
    videos: list[Video], thumb_root: Path, scraped_root: Path
) -> None:
    """Assign each video a destination under the single ``thumb_root``.

    The ``{ST}/{type}/{place_slug}_{geoid}`` segment is resolved with the same
    ``scraped_meetings_jurisdiction_dir`` builder the scrapers use (against
    ``scraped_root``, so existing/legacy folder names are honoured), then
    re-rooted under ``thumb_root`` and suffixed with ``{year}/{stem}.jpg``.

    Videos with no jurisdiction go to ``thumb_root/_unassigned/{ab}/{id}.jpg``.
    When two distinct videos resolve to the same path the id is appended so no
    thumbnail overwrites another.
    """
    stem_groups: dict[tuple[str, str, str], list[Video]] = {}
    for v in videos:
        if v.jurisdiction_id and v.state_code:
            juris_dir = scraped_meetings_jurisdiction_dir(
                scraped_root,
                state_code=v.state_code,
                jurisdiction_id=v.jurisdiction_id,
                place_name=v.place_name,
            )
            rel = juris_dir.relative_to(scraped_root)  # {ST}/{type}/{slug_geoid}
            year = v.event_date.strftime("%Y") if v.event_date else "undated"
            stem = _meeting_stem(v)
            stem_groups.setdefault((str(rel), year, stem), []).append(v)
        else:
            shard = (v.video_id[:2] or "_")
            v.dest = thumb_root / UNASSIGNED_SUBDIR / shard / f"{v.video_id}.jpg"

    for (rel, year, stem), group in stem_groups.items():
        base = thumb_root / rel / year
        collision = len(group) > 1
        for v in group:
            name = f"{stem}_{v.video_id}.jpg" if collision else f"{stem}.jpg"
            v.dest = base / name


def _has_thumbnail(video: Video) -> bool:
    return bool(video.dest and video.dest.exists() and video.dest.stat().st_size > 0)


# --------------------------------------------------------------------------- #
# Miss cache (write during download, read on resume + DB sync)
# --------------------------------------------------------------------------- #
class MissLog:
    """Append-only JSONL writer for one process's misses (single writer/file)."""

    def __init__(self, thumb_root: Path, label: str):
        self.path = thumb_root / MISSES_SUBDIR / f"misses-{label}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a")

    def record(self, video_id: str, reason: str) -> None:
        self._fh.write(
            json.dumps({"video_id": video_id, "reason": reason,
                        "checked_at": _now_iso()}) + "\n"
        )
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def load_known_misses(thumb_root: Path) -> dict[str, tuple[str, str]]:
    """All recorded misses: ``video_id -> (reason, checked_at)`` (last write wins)."""
    misses: dict[str, tuple[str, str]] = {}
    misses_dir = thumb_root / MISSES_SUBDIR
    if not misses_dir.is_dir():
        return misses
    for path in sorted(misses_dir.glob("misses-*.jsonl")):
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = rec.get("video_id")
            if vid:
                misses[vid] = (rec.get("reason", REASON_FETCH_ERROR),
                               rec.get("checked_at") or _now_iso())
    return misses


async def _download_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    video: Video,
    quality: str,
    fallback: bool,
    stats: dict[str, int],
    misslog: MissLog,
) -> None:
    dest = video.dest
    assert dest is not None
    if dest.exists() and dest.stat().st_size > 0:
        stats["skipped"] += 1
        return

    candidates = [quality]
    if fallback and quality != "hqdefault":
        candidates.append("hqdefault")

    last_outcome = REASON_FETCH_ERROR  # reason if every candidate fails
    async with sem:
        for attempt_q in candidates:
            url = _thumb_url(video.video_id, attempt_q)
            for retry in range(3):
                try:
                    resp = await client.get(url)
                except (httpx.TransportError, httpx.TimeoutException) as exc:
                    if retry == 2:
                        logger.debug("net fail {} q={}: {}", video.video_id, attempt_q, exc)
                        last_outcome = REASON_FETCH_ERROR
                        break
                    await asyncio.sleep(0.5 * (retry + 1))
                    continue

                if resp.status_code == 200 and resp.content:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(resp.content)
                    stats["downloaded"] += 1
                    return
                if resp.status_code == 404:
                    last_outcome = REASON_NOT_FOUND  # image absent for this quality
                    break  # try next candidate
                if resp.status_code == 429:
                    await asyncio.sleep(2.0 * (retry + 1))
                    continue
                last_outcome = REASON_FETCH_ERROR
                break

    stats[last_outcome] += 1
    misslog.record(video.video_id, last_outcome)
    logger.debug("miss {} ({}, tried {})", video.video_id, last_outcome, candidates)


async def _run(
    videos: list[Video], quality: str, fallback: bool, concurrency: int,
    misslog: MissLog,
) -> dict[str, int]:
    stats = {"downloaded": 0, "skipped": 0,
             REASON_NOT_FOUND: 0, REASON_FETCH_ERROR: 0}
    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(
        max_connections=concurrency, max_keepalive_connections=concurrency
    )
    total = len(videos)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0),
        limits=limits,
        follow_redirects=True,
        headers={"User-Agent": "open-navigator-thumbnail-fetch/1.0"},
    ) as client:
        tasks = [
            _download_one(client, sem, v, quality, fallback, stats, misslog)
            for v in videos
        ]
        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 1000 == 0 or done == total:
                logger.info(
                    "{}/{} processed  (downloaded={} skipped={} not_found={} fetch_error={})",
                    done, total, stats["downloaded"], stats["skipped"],
                    stats[REASON_NOT_FOUND], stats[REASON_FETCH_ERROR],
                )
    return stats


# --------------------------------------------------------------------------- #
# DB post-processing: reflect the cache (files + miss manifest) into bronze
# --------------------------------------------------------------------------- #
def sync_status_to_bronze(
    dsn: str, videos: list[Video], thumb_root: Path
) -> dict[str, int]:
    """Upsert per-video thumbnail status into ``bronze.bronze_youtube_thumbnail``.

    Derives status from the cache: a present file → ``downloaded`` (+ relative
    ``local_path``); otherwise the miss manifest's ``not_found`` / ``fetch_error``.
    Videos with neither (not yet processed) are left out so the table only holds
    settled outcomes.
    """
    known = load_known_misses(thumb_root)
    rows: list[tuple] = []
    counts = {"downloaded": 0, REASON_NOT_FOUND: 0, REASON_FETCH_ERROR: 0}
    for v in videos:
        if _has_thumbnail(v):
            rel = str(v.dest.resolve().relative_to(thumb_root))
            rows.append((v.video_id, "downloaded", rel, None, _now_iso()))
            counts["downloaded"] += 1
        elif v.video_id in known:
            reason, checked_at = known[v.video_id]
            rows.append((v.video_id, reason, None, reason, checked_at))
            counts[reason] = counts.get(reason, 0) + 1
        # else: pending — not written

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {STATUS_TABLE} (
                video_id   text PRIMARY KEY,
                status     text NOT NULL,
                local_path text,
                reason     text,
                checked_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        if rows:
            execute_values(
                cur,
                f"""
                INSERT INTO {STATUS_TABLE}
                    (video_id, status, local_path, reason, checked_at)
                VALUES %s
                ON CONFLICT (video_id) DO UPDATE SET
                    status     = EXCLUDED.status,
                    local_path = EXCLUDED.local_path,
                    reason     = EXCLUDED.reason,
                    checked_at = EXCLUDED.checked_at
                """,
                rows,
                page_size=5000,
            )
        conn.commit()
    logger.success(
        "Synced {} rows to {} (downloaded={} not_found={} fetch_error={})",
        len(rows), STATUS_TABLE, counts["downloaded"],
        counts[REASON_NOT_FOUND], counts[REASON_FETCH_ERROR],
    )
    return counts


def fetch_videos(dsn: str, limit: int | None) -> list[Video]:
    sql = (
        "SELECT video_id, jurisdiction_id, state_code, jurisdiction_name, "
        "       COALESCE(event_date, published_at::date) AS mdate, title "
        "FROM bronze.bronze_event_youtube "
        "WHERE video_id IS NOT NULL AND video_id <> '' "
        "ORDER BY video_id"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [Video(*row) for row in cur.fetchall()]


def _parse_shard(value: str) -> tuple[int, int]:
    i_str, _, n_str = value.partition("/")
    i, n = int(i_str), int(n_str)
    if n <= 0 or not (0 <= i < n):
        raise argparse.ArgumentTypeError("--shard must be I/N with 0 <= I < N")
    return i, n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="Postgres URL")
    parser.add_argument(
        "--out-root", type=Path, default=DEFAULT_THUMBNAILS_ROOT,
        help="thumbnails root directory (default: data/thumbnails)",
    )
    parser.add_argument("--quality", choices=QUALITIES, default="hqdefault")
    parser.add_argument(
        "--fallback", action="store_true",
        help="if the chosen quality 404s, fall back to hqdefault (guaranteed)",
    )
    parser.add_argument("--concurrency", type=int, default=24)
    parser.add_argument("--limit", type=int, default=None, help="cap video count (testing)")
    parser.add_argument(
        "--shard", type=_parse_shard, default=None, metavar="I/N",
        help="process only shard I of N (split work across processes)",
    )
    parser.add_argument(
        "--sync-db", action="store_true",
        help="after downloading, sync thumbnail status to bronze",
    )
    parser.add_argument(
        "--sync-only", action="store_true",
        help="skip downloading; only sync the existing cache -> bronze (all videos)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report planned paths + counts and exit",
    )
    args = parser.parse_args(argv)

    thumb_root = args.out_root.resolve()
    scraped_root = resolve_scraped_meetings_output_root().resolve()
    logger.info("Reading video ids from {}", args.dsn.split("@")[-1])
    videos = fetch_videos(args.dsn, args.limit)

    # --sync-only reflects the whole cache, so it always runs over every video.
    if args.shard and not args.sync_only:
        i, n = args.shard
        videos = [v for idx, v in enumerate(videos) if idx % n == i]
        logger.info("Shard {}/{}: {} videos", i, n, len(videos))

    plan_destinations(videos, thumb_root, scraped_root)

    if args.sync_only:
        sync_status_to_bronze(args.dsn, videos, thumb_root)
        return 0

    placed = sum(1 for v in videos if v.jurisdiction_id and v.state_code)
    logger.info(
        "{} videos: {} placed by jurisdiction, {} unassigned -> {}",
        len(videos), placed, len(videos) - placed, thumb_root,
    )

    if args.dry_run:
        for v in videos[:8]:
            logger.info("  {} -> {}", v.video_id, v.dest)
        return 0

    # Resume: skip files already on disk, and skip known not_found (deleted
    # videos) — but retry fetch_error misses.
    known = load_known_misses(thumb_root)
    pending = [
        v for v in videos
        if not _has_thumbnail(v) and known.get(v.video_id, ("", ""))[0] != REASON_NOT_FOUND
    ]
    logger.info(
        "{} already on disk/skipped-missing, {} to fetch (quality={})",
        len(videos) - len(pending), len(pending), args.quality,
    )

    if pending:
        label = f"{args.shard[0]}of{args.shard[1]}" if args.shard else "all"
        misslog = MissLog(thumb_root, label)
        try:
            stats = asyncio.run(
                _run(pending, args.quality, args.fallback, args.concurrency, misslog)
            )
        finally:
            misslog.close()
        logger.success(
            "Done. downloaded={} not_found={} fetch_error={}",
            stats["downloaded"], stats[REASON_NOT_FOUND], stats[REASON_FETCH_ERROR],
        )
    else:
        logger.success("Nothing to download — all thumbnails present or known-missing.")

    if args.sync_db:
        # Sync the full picture (re-fetch all videos; a shard only saw its slice).
        all_videos = fetch_videos(args.dsn, args.limit)
        plan_destinations(all_videos, thumb_root, scraped_root)
        sync_status_to_bronze(args.dsn, all_videos, thumb_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
