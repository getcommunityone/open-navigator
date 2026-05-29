#!/usr/bin/env python3
"""
One-shot backfill: stamp ``policy_analysis_at`` / ``policy_report_at`` on
``bronze.bronze_events_youtube`` from existing policy-cache file mtimes.

Migration 083 added the per-event tracking columns, but files written before the
pipeline started recording (and standalone runs) have empty stamps, so the dashboard's
ANALYSIS/REPORTS (24h) cards under-count until enough new runs land. This walks the
policy cache, maps each analysis JSON (and its sibling report markdown) to a
``video_id``, and advances the stamps to the file mtimes.

Stamps only move *forward*: it uses ``GREATEST(existing, file_mtime)`` (Postgres
``GREATEST`` ignores NULLs), so it never clobbers a newer stamp written by a live run.

Usage::

    python scripts/gemini/backfill_policy_event_stamps.py            # whole cache
    python scripts/gemini/backfill_policy_event_stamps.py --state MA # one state
    python scripts/gemini/backfill_policy_event_stamps.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json  # noqa: E402

from scripts.gemini.meeting_transcript_policy import _video_id_from_analysis_path  # noqa: E402
from scripts.gemini.persist_policy_analysis_bronze import database_url  # noqa: E402
from scripts.gemini.policy_processing_status_report import _DEFAULT_CACHE  # noqa: E402
from scripts.gemini.transcript_cache_paths import (  # noqa: E402
    report_path_for_analysis,
    video_id_from_analysis,
)

_DIR_ANALYSIS = "02_analysis"


def _resolve_video_id(analysis_path: Path) -> str:
    """Authoritative video_id from the JSON body, falling back to the filename regex.

    ``_video_id_from_analysis_path`` matches an 11-char filename fragment *first*,
    which yields title fragments (e.g. ``Auburn_City``) for files whose name has no
    real id. The stored ``video_id`` field is authoritative, so prefer it here.
    """
    try:
        data = json.loads(analysis_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            vid = video_id_from_analysis(data)
            if vid:
                return vid
    except (json.JSONDecodeError, OSError):
        pass
    return (_video_id_from_analysis_path(analysis_path) or "").strip()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _mtime_utc(path: Path) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def collect_stamps(
    cache_root: Path, *, state: Optional[str] = None
) -> Dict[str, Dict[str, object]]:
    """Map video_id -> newest analysis/report mtime + repo-relative path from the cache."""
    by_vid: Dict[str, Dict[str, object]] = {}
    analysis_dirs = [d for d in cache_root.rglob(_DIR_ANALYSIS) if d.is_dir()]
    if state:
        st = state.upper()
        analysis_dirs = [
            d for d in analysis_dirs if f"/{st}/" in f"/{_rel(d)}/".upper()
        ]
    logger.info("Scanning {} analysis dir(s) under {}", len(analysis_dirs), cache_root)

    for an_dir in analysis_dirs:
        for ajson in an_dir.glob("*.json"):
            if not ajson.is_file() or ajson.name.startswith("_"):
                continue
            vid = _resolve_video_id(ajson)
            if not vid:
                continue
            a_mtime = _mtime_utc(ajson)
            rec = by_vid.setdefault(
                vid,
                {"analysis_at": None, "analysis_path": None, "report_at": None, "report_path": None},
            )
            if a_mtime and (rec["analysis_at"] is None or a_mtime > rec["analysis_at"]):
                rec["analysis_at"] = a_mtime
                rec["analysis_path"] = _rel(ajson)

            report = report_path_for_analysis(ajson)
            if report and report.is_file():
                r_mtime = _mtime_utc(report)
                if r_mtime and (rec["report_at"] is None or r_mtime > rec["report_at"]):
                    rec["report_at"] = r_mtime
                    rec["report_path"] = _rel(report)

    return by_vid


def apply_stamps(
    by_vid: Dict[str, Dict[str, object]], *, dry_run: bool = False
) -> Tuple[int, int]:
    """Advance stamps on matching bronze rows. Returns (rows_seen, rows_updated)."""
    rows: List[Tuple[str, object, object, object, object]] = [
        (
            vid,
            rec["analysis_at"],
            rec["analysis_path"],
            rec["report_at"],
            rec["report_path"],
        )
        for vid, rec in by_vid.items()
    ]
    if not rows:
        logger.warning("No video_ids resolved from cache — nothing to backfill.")
        return (0, 0)
    if dry_run:
        with_analysis = sum(1 for r in rows if r[1] is not None)
        with_report = sum(1 for r in rows if r[3] is not None)
        logger.info(
            "[dry-run] {} video(s): {} with analysis mtime, {} with report mtime",
            len(rows),
            with_analysis,
            with_report,
        )
        return (len(rows), 0)

    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(database_url(None))
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                UPDATE bronze.bronze_events_youtube AS b
                SET policy_analysis_at = GREATEST(b.policy_analysis_at, v.analysis_at),
                    policy_analysis_path = COALESCE(b.policy_analysis_path, v.analysis_path),
                    policy_report_at = GREATEST(b.policy_report_at, v.report_at),
                    policy_report_path = COALESCE(b.policy_report_path, v.report_path),
                    last_updated = CURRENT_TIMESTAMP
                FROM (VALUES %s) AS v(video_id, analysis_at, analysis_path, report_at, report_path)
                WHERE b.video_id = v.video_id
                """,
                rows,
                template="(%s, %s::timestamptz, %s, %s::timestamptz, %s)",
                page_size=max(len(rows), 1),  # single statement → accurate rowcount
                fetch=False,
            )
            n_updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    logger.info("Backfill done: {} cache video(s), {} bronze row(s) updated", len(rows), n_updated)
    return (len(rows), n_updated)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        default=str(_DEFAULT_CACHE),
        help=f"Policy cache root (default: {_DEFAULT_CACHE})",
    )
    parser.add_argument("--state", default=None, help="Limit to one state code (e.g. MA)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report counts without writing"
    )
    args = parser.parse_args()

    cache_root = Path(args.cache_dir).resolve()
    if not cache_root.is_dir():
        raise SystemExit(f"Cache dir not found: {cache_root}")

    by_vid = collect_stamps(cache_root, state=args.state)
    apply_stamps(by_vid, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
