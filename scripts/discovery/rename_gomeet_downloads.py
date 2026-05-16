#!/usr/bin/env python3
"""
Move legacy flat GoMeet downloads into ``_gomeet_downloads/{calendar_year}/`` with the same
``YYYY-MM-DD_title_snake`` stems used by :mod:`scripts.discovery.download_gomeet_recordings`.

Matching uses :func:`output_stem` on each known GoMeet URL from the jurisdiction manifest / crawl
(see :func:`iter_gomeet_jobs`). Files whose paths already look like the new layout are skipped.

Examples::

    .venv/bin/python -m scripts.discovery.rename_gomeet_downloads \\
        --jurisdiction-dir data/cache/scraped_meetings/MT/county/county_30097 --dry-run

    .venv/bin/python -m scripts.discovery.rename_gomeet_downloads \\
        --scraped-meetings-root data/cache/scraped_meetings
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger

from scripts.discovery.download_gomeet_recordings import (
    GomeetJob,
    build_gomeet_video_stem_and_year,
    iter_gomeet_jobs,
    output_stem,
)

_MEDIA_SUFFIXES = frozenset({".mp4", ".webm", ".mkv", ".m4a", ".opus"})
_SKIP_SUFFIXES = frozenset({".part", ".ytdl", ".tmp"})


def _looks_like_new_layout(path: Path) -> bool:
    """Heuristic: under a 4-digit year folder with date/year-prefixed stem (post-migration)."""
    if not path.parent.name.isdigit() or len(path.parent.name) != 4:
        return False
    y = int(path.parent.name)
    if not (1990 <= y <= 2100):
        return False
    st = path.stem
    return bool(
        re.match(r"^(?:\d{4}-\d{2}-\d{2}|[12][09]\d{2}|undated)_", st, re.I)
        or re.match(r"^\d{4}-\d{2}-\d{2}$", st)
    )


def _build_old_stem_index(jobs: List[GomeetJob]) -> Tuple[Dict[str, GomeetJob], List[str]]:
    by_stem: Dict[str, GomeetJob] = {}
    collisions: List[str] = []
    for j in jobs:
        ost = output_stem(j.url)
        if ost in by_stem and by_stem[ost].url != j.url:
            collisions.append(f"old_stem={ost!r} urls={by_stem[ost].url!r} vs {j.url!r}")
        else:
            by_stem[ost] = j
    return by_stem, collisions


def _find_job_for_media_path(
    path: Path,
    jobs: List[GomeetJob],
    by_old_stem: Dict[str, GomeetJob],
) -> Optional[GomeetJob]:
    stem = path.stem
    if stem in by_old_stem:
        return by_old_stem[stem]
    low_stem = stem.lower()
    for j in jobs:
        if low_stem in j.url.lower().replace("-", "_"):
            return j
        if output_stem(j.url).lower() == low_stem:
            return j
    return None


def _unique_destination(dest: Path) -> Path:
    if not dest.exists():
        return dest
    base = dest.with_suffix("")
    suf = dest.suffix
    n = 2
    while True:
        cand = Path(f"{base}_dup{n}{suf}")
        if not cand.exists():
            return cand
        n += 1


def _iter_gomeet_download_dirs(scraped_root: Path) -> List[Path]:
    found: Set[Path] = set()
    for g in scraped_root.rglob("_gomeet_downloads"):
        if g.is_dir():
            found.add(g)
    return sorted(found)


def migrate_jurisdiction_gomeet_downloads(
    jurisdiction_dir: Path,
    *,
    dry_run: bool,
    fallback_year: int,
) -> Tuple[int, int, int]:
    """
    Returns ``(n_moved, n_skipped, n_unmatched)`` for media files under ``_gomeet_downloads``.
    """
    gdir = jurisdiction_dir / "_gomeet_downloads"
    if not gdir.is_dir():
        return 0, 0, 0

    jobs = iter_gomeet_jobs(jurisdiction_dir)
    by_old_stem, collisions = _build_old_stem_index(jobs)
    for c in collisions:
        logger.warning("gomeet_rename_collision {}", c)

    media_files: List[Path] = []
    for p in sorted(gdir.rglob("*")):
        if not p.is_file():
            continue
        low = p.name.lower()
        if any(low.endswith(s) for s in _SKIP_SUFFIXES):
            continue
        if p.suffix.lower() not in _MEDIA_SUFFIXES:
            continue
        media_files.append(p)

    n_moved = n_skipped = n_unmatched = 0

    for src in media_files:
        if _looks_like_new_layout(src):
            logger.info("gomeet_rename_skip_already_layout path={}", src.relative_to(gdir))
            n_skipped += 1
            continue

        job = _find_job_for_media_path(src, jobs, by_old_stem)
        if not job:
            logger.warning("gomeet_rename_unmatched path={}", src)
            n_unmatched += 1
            continue

        year_folder, new_stem = build_gomeet_video_stem_and_year(
            job.url,
            job.anchor_text,
            fallback_year=fallback_year,
        )
        dest_dir = gdir / year_folder
        dest = dest_dir / f"{new_stem}{src.suffix.lower()}"
        dest = _unique_destination(dest)

        if src.resolve() == dest.resolve():
            n_skipped += 1
            continue

        try:
            rel_src = src.relative_to(gdir)
            rel_dest = dest.relative_to(gdir)
        except ValueError:
            rel_src = src
            rel_dest = dest

        if dry_run:
            logger.info("gomeet_rename_dry_run {} -> {}", rel_src, rel_dest)
            n_moved += 1
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        src.replace(dest)
        logger.info("gomeet_rename_ok {} -> {}", rel_src, rel_dest)
        n_moved += 1

    # Prune empty year dirs if we moved everything out of root
    if not dry_run and n_moved:
        for p in sorted(gdir.glob("*"), reverse=True):
            if p.is_dir():
                try:
                    if not any(p.iterdir()):
                        p.rmdir()
                        logger.info("gomeet_rename_rmdir_empty {}", p.name)
                except OSError:
                    pass

    return n_moved, n_skipped, n_unmatched


def main() -> None:
    ap = argparse.ArgumentParser(description="Rename legacy GoMeet downloads to year/title layout.")
    ap.add_argument(
        "--jurisdiction-dir",
        default="",
        help="Single scrape folder containing _gomeet_downloads (e.g. .../county_30097).",
    )
    ap.add_argument(
        "--scraped-meetings-root",
        default="",
        help="Walk this tree for every _gomeet_downloads (e.g. data/cache/scraped_meetings).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Log moves only.")
    ap.add_argument(
        "--fallback-year",
        type=int,
        default=0,
        metavar="YYYY",
        help="Year hint when infer_calendar_folder_year has no anchor/URL date (default: current year).",
    )
    args = ap.parse_args()

    fy_raw = int(args.fallback_year or 0)
    fallback_year = fy_raw if 1990 <= fy_raw <= 2100 else datetime.now().year

    targets: List[Path] = []
    if args.jurisdiction_dir:
        targets.append(Path(args.jurisdiction_dir).expanduser().resolve())
    root = (args.scraped_meetings_root or "").strip()
    if root:
        rp = Path(root).expanduser().resolve()
        if not rp.is_dir():
            logger.error("Not a directory: {}", rp)
            raise SystemExit(2)
        for gd in _iter_gomeet_download_dirs(rp):
            targets.append(gd.parent)

    if not targets:
        logger.error("Pass --jurisdiction-dir and/or --scraped-meetings-root.")
        raise SystemExit(2)

    seen: Set[Path] = set()
    uniq_dirs: List[Path] = []
    for t in targets:
        if t in seen:
            continue
        seen.add(t)
        uniq_dirs.append(t)

    total_m = total_s = total_u = 0
    for jdir in uniq_dirs:
        if not jdir.is_dir():
            logger.warning("skip_not_dir {}", jdir)
            continue
        m, s, u = migrate_jurisdiction_gomeet_downloads(
            jdir,
            dry_run=args.dry_run,
            fallback_year=fallback_year,
        )
        if m or s or u:
            logger.info(
                "gomeet_rename_jurisdiction dir={} moved={} skipped={} unmatched={} dry_run={}",
                jdir,
                m,
                s,
                u,
                args.dry_run,
            )
        total_m += m
        total_s += s
        total_u += u

    logger.info(
        "gomeet_rename_total moved={} skipped={} unmatched={} dry_run={}",
        total_m,
        total_s,
        total_u,
        args.dry_run,
    )


if __name__ == "__main__":
    main()
