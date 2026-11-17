"""Recover caption transcripts cached under ``packages/scrapers/data/cache`` (#458).

Until #458, several ``scrapers.youtube`` modules resolved the "repo root" to
``packages/scrapers``, so the caption backfill wrote its transcript cache to
``packages/scrapers/data/cache/gemini_transcript_policy/`` where the analysis
pipeline never looks, and skipped the warehouse write for videos without an
``event_id``. This one-off CLI repairs both:

(a) every ``**/01_transcripts/*.json`` whose ``video_id`` has no
    ``has_transcript`` row in ``bronze.bronze_event_youtube_transcript`` is upserted
    with :func:`scrapers.youtube.backfill_jurisdiction_transcripts.upsert_bronze_transcript`
    (the backfill's own write);
(b) the file is **copied** (never moved) to the same relative path under
    ``data/cache/gemini_transcript_policy/``; destinations that already exist are
    skipped, so nothing is overwritten or deleted.

Dry run by default (reads the warehouse, writes nothing)::

    python -m scrapers.youtube.recover_misplaced_transcripts
    python -m scrapers.youtube.recover_misplaced_transcripts --apply
    python -m scrapers.youtube.recover_misplaced_transcripts --apply --limit 100
"""

from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Optional

from loguru import logger

from core_lib.paths import repo_root
from scrapers.youtube.policy_transcript_cache import read_cached_transcript

REPO_ROOT = repo_root(__file__)
CACHE_REL = Path("data") / "cache" / "gemini_transcript_policy"
DEFAULT_SOURCE_ROOT = REPO_ROOT / "packages" / "scrapers" / CACHE_REL
DEFAULT_DEST_ROOT = REPO_ROOT / CACHE_REL
TRANSCRIPT_GLOB = "**/01_transcripts/*.json"

UpsertFn = Callable[[Any, str, dict[str, Any]], None]


@dataclass
class RecoveryStats:
    files: int = 0
    unreadable: int = 0
    no_transcript: int = 0
    bronze_present: int = 0
    bronze_loaded: int = 0
    bronze_duplicate: int = 0
    copied: int = 0
    copy_skipped_exists: int = 0
    loaded_video_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, int]:
        return {k: v for k, v in self.__dict__.items() if isinstance(v, int)}


def default_database_url() -> str:
    """Local warehouse DSN (bronze is canonical there, not on Neon)."""
    explicit = (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
    if explicit:
        return explicit
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5433")
    user = os.getenv("POSTGRES_USER", "postgres")
    pwd = os.getenv("POSTGRES_PASSWORD", "password")
    db = os.getenv("POSTGRES_DB", "open_navigator")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


def iter_transcript_files(source_root: Path) -> Iterator[Path]:
    """Yield transcript JSON files under ``source_root`` in a stable order."""
    yield from sorted(p for p in source_root.glob(TRANSCRIPT_GLOB) if p.is_file())


def fetch_bronze_transcript_ids(conn: Any, video_ids: Iterable[str]) -> set[str]:
    """Video ids that already have ``has_transcript`` in bronze."""
    ids = sorted(set(video_ids))
    if not ids:
        return set()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT video_id
            FROM bronze.bronze_event_youtube_transcript
            WHERE has_transcript AND video_id = ANY(%(ids)s)
            """,
            {"ids": ids},
        )
        return {str(r[0]) for r in cur.fetchall()}
    finally:
        cur.close()


def recover(
    *,
    source_root: Path,
    dest_root: Path,
    conn: Any,
    apply: bool = False,
    limit: Optional[int] = None,
    upsert: Optional[UpsertFn] = None,
) -> RecoveryStats:
    """Load missing transcripts into bronze and copy files to ``dest_root``.

    With ``apply=False`` nothing is written: counts report what would happen.
    """
    if upsert is None:
        from scrapers.youtube.backfill_jurisdiction_transcripts import (
            upsert_bronze_transcript,
        )

        upsert = upsert_bronze_transcript

    stats = RecoveryStats()
    files = list(iter_transcript_files(source_root))
    if limit is not None:
        files = files[:limit]
    stats.files = len(files)

    parsed: list[tuple[Path, Optional[str], dict[str, Any]]] = []
    for path in files:
        try:
            got = read_cached_transcript(path)
        except (OSError, ValueError) as exc:
            logger.warning("Unreadable transcript {}: {}", path, exc)
            stats.unreadable += 1
            parsed.append((path, None, {}))
            continue
        if got is None:
            stats.unreadable += 1
            parsed.append((path, None, {}))
            continue
        parsed.append((path, got[0], got[1]))

    in_bronze = fetch_bronze_transcript_ids(conn, (v for _, v, _ in parsed if v))
    handled: set[str] = set()

    for path, video_id, yt in parsed:
        if video_id:
            if not yt:
                stats.no_transcript += 1
            elif video_id in in_bronze:
                stats.bronze_present += 1
            elif video_id in handled:
                stats.bronze_duplicate += 1
            else:
                handled.add(video_id)
                stats.bronze_loaded += 1
                stats.loaded_video_ids.append(video_id)
                if apply:
                    upsert(conn, video_id, yt)

        dest = dest_root / path.relative_to(source_root)
        if dest.exists():
            stats.copy_skipped_exists += 1
            continue
        stats.copied += 1
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

    return stats


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load misplaced cached transcripts into bronze and copy them to data/cache (#458).",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help=f"Misplaced cache to read (default: {DEFAULT_SOURCE_ROOT})",
    )
    parser.add_argument(
        "--dest-root",
        type=Path,
        default=DEFAULT_DEST_ROOT,
        help=f"Canonical cache to copy into (default: {DEFAULT_DEST_ROOT})",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Warehouse DSN (default: local warehouse from POSTGRES_* env, localhost:5433)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Process at most N files")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write to bronze and copy files (default: dry run)",
    )
    args = parser.parse_args(argv)

    source_root = args.source_root.resolve()
    dest_root = args.dest_root.resolve()
    if not source_root.is_dir():
        logger.error("Source root does not exist: {}", source_root)
        return 1
    if source_root == dest_root:
        logger.error("Source and destination are the same directory: {}", source_root)
        return 1

    import psycopg2

    conn = psycopg2.connect(args.database_url or default_database_url())
    try:
        stats = recover(
            source_root=source_root,
            dest_root=dest_root,
            conn=conn,
            apply=args.apply,
            limit=args.limit,
        )
    finally:
        conn.close()

    mode = "APPLIED" if args.apply else "DRY RUN (no writes; pass --apply)"
    logger.info("{} source={} dest={}", mode, source_root, dest_root)
    for key, value in stats.as_dict().items():
        logger.info("  {:<20} {:,}", key, value)
    if args.apply:
        logger.success(
            "Loaded {:,} transcripts into bronze; copied {:,} files",
            stats.bronze_loaded,
            stats.copied,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
