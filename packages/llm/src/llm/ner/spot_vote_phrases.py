"""CLI: spot stock vote phrases on Part 1 meeting transcripts and load bronze."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, TextIO

import psycopg2
from loguru import logger

from core_lib.paths import repo_root
from llm.gemini.transcript_db import fetch_db_transcript
from llm.ner.part1_videos import list_part1_video_ids
from llm.ner.spot import file_sha256, spot_segments
from llm.ner.store import ensure_table, replace_hits, table_stats

_BYTES_PER_HIT_EMPTY_TABLE = 120
_CATALOG_VIDEO_COUNT = 200_000


def estimate_full_catalog(
    *,
    videos_scanned: int,
    hits: int,
    table_rows: int,
    table_bytes: int,
) -> dict[str, int]:
    """Linear scale of this run's hit rate and row size to ~200k videos."""
    n = max(videos_scanned, 1)
    hits_per_video = hits / n
    estimate_200k_hits = int(hits_per_video * _CATALOG_VIDEO_COUNT)

    if table_rows > 0:
        bytes_per_hit = table_bytes / table_rows
    else:
        bytes_per_hit = _BYTES_PER_HIT_EMPTY_TABLE

    estimate_200k_bytes = int(estimate_200k_hits * bytes_per_hit)
    return {
        "estimate_200k_hits": estimate_200k_hits,
        "estimate_200k_bytes": estimate_200k_bytes,
    }


def _git_commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "unknown"


def _resolve_database_url(args: argparse.Namespace) -> str | None:
    return (args.database_url or os.environ.get("OPEN_NAVIGATOR_DATABASE_URL") or "").strip() or None


def _format_report(
    *,
    videos_scanned: int,
    videos_with_hits: int,
    hits: int,
    table_rows: int,
    table_bytes: int,
) -> str:
    est = estimate_full_catalog(
        videos_scanned=videos_scanned,
        hits=hits,
        table_rows=table_rows,
        table_bytes=table_bytes,
    )
    return (
        f"videos_scanned={videos_scanned} videos_with_hits={videos_with_hits} "
        f"hits={hits} table_rows={table_rows} table_bytes={table_bytes}\n"
        f"estimate_200k_hits≈{est['estimate_200k_hits']} "
        f"estimate_200k_bytes≈{est['estimate_200k_bytes']}"
    )


def _scan_videos(
    database_url: str,
    video_ids: list[str],
    *,
    dry_run: bool,
    git_sha: str,
    candidates_out: TextIO | None = None,
    candidates_nlp: object | None = None,
) -> tuple[int, int, int, list[str], list[dict]]:
    loaded_ts = datetime.now(timezone.utc)
    videos_with_hits = 0
    total_hits = 0
    file_sha256s: list[str] = []
    rows: list[dict] = []

    for video_id in video_ids:
        yt = fetch_db_transcript(database_url, video_id)
        if yt is None:
            logger.warning("No transcript for {}; skipping", video_id)
            continue

        segments = yt.get("segments") or []
        if not segments:
            logger.warning("Empty segments for {}; skipping", video_id)
            continue

        sha = file_sha256(segments)
        file_sha256s.append(sha)
        hits = spot_segments(video_id, segments)
        if hits:
            videos_with_hits += 1
        total_hits += len(hits)
        logger.info("{}: {} hit(s)", video_id, len(hits))

        for h in hits:
            rows.append(
                {
                    "video_id": h.video_id,
                    "phrase_code": h.phrase_code,
                    "start_seconds": h.start_seconds,
                    "char_offset": h.char_offset,
                    "file_sha256": sha,
                    "loaded_ts": loaded_ts,
                    "git_commit_sha": git_sha,
                }
            )

        if candidates_out is not None and hits:
            from llm.ner.candidates import cluster_candidates

            for cluster in cluster_candidates(
                video_id, segments, hits, nlp=candidates_nlp
            ):
                candidates_out.write(json.dumps(cluster, ensure_ascii=False) + "\n")

    return len(video_ids), videos_with_hits, total_hits, file_sha256s, rows


def _candidates_output_path(utc_run_id: str) -> Path:
    return (
        repo_root(__file__)
        / "data"
        / "cache"
        / "vote_phrase_candidates"
        / utc_run_id
        / "candidates.jsonl"
    )


def _try_build_candidates_nlp() -> object | None:
    try:
        from llm.ner.candidates import build_ruler_nlp

        return build_ruler_nlp()
    except OSError as exc:
        logger.error(
            "spaCy model en_core_web_sm is required for --candidates: {}",
            exc,
        )
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spot vote phrases on Part 1 meeting transcripts.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Postgres URL (default: OPEN_NAVIGATOR_DATABASE_URL)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max videos to process")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report only; do not write bronze",
    )
    parser.add_argument(
        "--candidates",
        action="store_true",
        help="Write clustered hit candidates to data/cache/vote_phrase_candidates/ (JSONL)",
    )
    parser.add_argument(
        "--video-id",
        action="append",
        default=None,
        metavar="ID",
        help="Process only this video (repeatable); skips Part 1 list",
    )
    args = parser.parse_args(argv)

    database_url = _resolve_database_url(args)
    if not database_url:
        logger.error("Set --database-url or OPEN_NAVIGATOR_DATABASE_URL")
        return 1

    if args.video_id:
        video_ids = [v.strip() for v in args.video_id if v and v.strip()]
        if args.limit is not None:
            video_ids = video_ids[: args.limit]
    else:
        video_ids = list_part1_video_ids(database_url, limit=args.limit)

    if not video_ids:
        logger.warning("No videos to scan")
        report = _format_report(
            videos_scanned=0,
            videos_with_hits=0,
            hits=0,
            table_rows=0,
            table_bytes=0,
        )
        print(report)
        return 0

    git_sha = _git_commit_sha()

    candidates_out: IO[str] | None = None
    candidates_nlp: object | None = None
    if args.candidates:
        candidates_nlp = _try_build_candidates_nlp()
        if candidates_nlp is None:
            return 1
        utc_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = _candidates_output_path(utc_run_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        candidates_out = out_path.open("w", encoding="utf-8")
        logger.info("Writing vote-phrase candidates to {}", out_path)

    try:
        videos_scanned, videos_with_hits, hits, file_sha256s, rows = _scan_videos(
            database_url,
            video_ids,
            dry_run=args.dry_run,
            git_sha=git_sha,
            candidates_out=candidates_out,
            candidates_nlp=candidates_nlp,
        )
    finally:
        if candidates_out is not None:
            candidates_out.close()

    table_rows = 0
    table_bytes = 0
    if not args.dry_run:
        conn = psycopg2.connect(database_url)
        try:
            ensure_table(conn)
            replace_hits(conn, file_sha256s=file_sha256s, rows=rows)
            stats = table_stats(conn)
            table_rows = stats["row_count"]
            table_bytes = stats["total_bytes"]
        finally:
            conn.close()

    report = _format_report(
        videos_scanned=videos_scanned,
        videos_with_hits=videos_with_hits,
        hits=hits,
        table_rows=table_rows if not args.dry_run else 0,
        table_bytes=table_bytes if not args.dry_run else 0,
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())