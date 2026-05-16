#!/usr/bin/env python3
"""
Transcode GoMeet (and other) **video** files under ``_gomeet_downloads/`` to **Opus** (``.opus``),
audio-only — same spirit as SuiteOne in
:mod:`scripts.discovery.comprehensive_discovery_pipeline_jurisdiction`.

Uses the same defaults as meetings video:

- ``SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS`` — default **on**; set ``false`` to skip transcoding in the
  downloader hook (this CLI ignores it unless you pass ``--respect-download-mp4-opus-env``).
- ``SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS`` — default **on**; removes the source ``.mp4`` after a
  successful encode (when Opus size ≥ ``SCRAPED_MEETINGS_MIN_OPUS_BYTES_FOR_MP4_DELETE``).
- Optional: ``GOMEET_OPUS_BITRATE`` (e.g. ``96k``) overrides audio bitrate.

If MP4s are never removed, check logs for ``gomeet_ytdlp_post_*`` / ``gomeet_opus_*``: common causes
are ``SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS=false`` (skips ffmpeg entirely), missing ``ffmpeg`` on
``PATH``, ``SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS=false``, Opus output below the min-bytes
threshold, or ``--skip-opus`` on the GoMeet downloader.

Examples::

    .venv/bin/python -m scripts.discovery.gomeet_mp4_to_opus \\
        --jurisdiction-dir data/cache/scraped_meetings/MT/county/county_30097

    .venv/bin/python -m scripts.discovery.gomeet_mp4_to_opus \\
        --scraped-meetings-root data/cache/scraped_meetings --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple

from loguru import logger

_SOURCE_SUFFIXES = frozenset({".mp4", ".webm", ".mkv", ".m4a"})
_SKIP_SUFFIXES = frozenset({".part", ".ytdl", ".tmp"})


def _unlink_source_media(path: Path) -> bool:
    """
    Remove downloaded container after Opus encode. Retries briefly for Windows/WSL file locks.
    """
    for attempt in range(1, 6):
        try:
            path.unlink(missing_ok=True)
            if not path.is_file():
                return True
        except OSError as exc:
            logger.warning(
                "gomeet_opus_unlink_attempt_failed path={} attempt={}/5 err={}",
                path.name,
                attempt,
                exc,
            )
        time.sleep(0.35 * attempt)
    return path.is_file()


def _env_truthy(key: str, default: str = "1") -> bool:
    v = (os.getenv(key) or default).strip().lower()
    return v not in ("0", "false", "no", "off")


def meetings_delete_mp4_after_opus() -> bool:
    return _env_truthy("SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS", "1")


def meetings_min_opus_bytes_for_mp4_cleanup() -> int:
    try:
        return max(1_024, int(os.getenv("SCRAPED_MEETINGS_MIN_OPUS_BYTES_FOR_MP4_DELETE") or "102400"))
    except ValueError:
        return 102_400


def meetings_download_mp4_opus_enabled() -> bool:
    return _env_truthy("SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS", "1")


def opus_bitrate() -> str:
    b = (os.getenv("GOMEET_OPUS_BITRATE") or "96k").strip()
    return b if b else "96k"


def _ffmpeg_mp4_to_opus(mp4: Path, opus: Path, *, bitrate: str, timeout_s: int = 7200) -> None:
    opus.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(mp4),
            "-vn",
            "-c:a",
            "libopus",
            "-b:a",
            bitrate,
            str(opus),
        ],
        check=True,
        capture_output=True,
        timeout=timeout_s,
    )


def transcode_one_media_to_opus(
    media_path: Path,
    *,
    bitrate: Optional[str] = None,
    delete_after: Optional[bool] = None,
    min_opus_bytes: Optional[int] = None,
    force: bool = False,
) -> Tuple[bool, str]:
    """
    Encode ``media_path`` → sibling ``<stem>.opus``. Optionally delete source (meetings env defaults).

    Returns ``(ok, reason)``.
    """
    if not media_path.is_file():
        return False, "missing_file"
    if media_path.suffix.lower() not in _SOURCE_SUFFIXES:
        return False, "suffix_not_transcoded"
    low = media_path.name.lower()
    if any(low.endswith(s) for s in _SKIP_SUFFIXES):
        return False, "partial_fragment"

    if not shutil.which("ffmpeg"):
        return False, "ffmpeg_not_on_path"

    br = bitrate or opus_bitrate()
    opus_path = media_path.with_suffix(".opus")
    if opus_path.is_file() and not force:
        min_b0 = min_opus_bytes if min_opus_bytes is not None else meetings_min_opus_bytes_for_mp4_cleanup()
        if opus_path.stat().st_size >= min_b0:
            # Fresh yt-dlp MP4 next to an already-good Opus: drop the redundant container (same as post-encode cleanup).
            do_del = meetings_delete_mp4_after_opus() if delete_after is None else delete_after
            if do_del:
                if _unlink_source_media(media_path):
                    logger.info(
                        "gomeet_opus_deleted_source_redundant src={} (opus_exists_skip)",
                        media_path.name,
                    )
                else:
                    logger.warning(
                        "gomeet_opus_delete_source_redundant_failed path={} (file still present)",
                        media_path.name,
                    )
            else:
                logger.info(
                    "gomeet_opus_retain_source_redundant src={} SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS=off",
                    media_path.name,
                )
            return True, "opus_exists_skip"
        try:
            opus_path.unlink(missing_ok=True)
        except OSError:
            pass

    try:
        logger.info("gomeet_opus_transcode_start src={}", media_path.name)
        _ffmpeg_mp4_to_opus(media_path, opus_path, bitrate=br)
    except subprocess.CalledProcessError as exc:
        try:
            opus_path.unlink(missing_ok=True)
        except OSError:
            pass
        tail = (exc.stderr or b"").decode("utf-8", errors="replace")[:800]
        logger.warning("gomeet_opus_transcode_fail path={} err={}", media_path.name, tail)
        return False, f"ffmpeg:{tail}"

    min_b = min_opus_bytes if min_opus_bytes is not None else meetings_min_opus_bytes_for_mp4_cleanup()
    try:
        if not opus_path.is_file() or opus_path.stat().st_size < min_b:
            logger.warning(
                "gomeet_opus_too_small path={} bytes={}",
                media_path.name,
                opus_path.stat().st_size if opus_path.is_file() else 0,
            )
            try:
                opus_path.unlink(missing_ok=True)
            except OSError:
                pass
            logger.warning(
                "gomeet_opus_mp4_retained opus_below_min_bytes src={} min_bytes={} "
                "(raise SCRAPED_MEETINGS_MIN_OPUS_BYTES_FOR_MP4_DELETE or fix encode)",
                media_path.name,
                min_b,
            )
            return False, "opus_too_small"
    except OSError:
        return False, "opus_stat_error"

    logger.success("gomeet_opus_transcode_done opus={}", opus_path.name)

    do_del = meetings_delete_mp4_after_opus() if delete_after is None else delete_after
    if do_del:
        if _unlink_source_media(media_path):
            logger.info("gomeet_opus_deleted_source mp4={} opus={}", media_path.name, opus_path.name)
        else:
            logger.warning(
                "gomeet_opus_delete_source_failed path={} (file still present after retries)",
                media_path.name,
            )
    else:
        logger.info(
            "gomeet_opus_retain_source_after_encode src={} SCRAPED_MEETINGS_DELETE_MP4_AFTER_OPUS=off",
            media_path.name,
        )

    return True, "ok"


def transcode_gomeet_downloads_under(
    jurisdiction_dir: Path,
    *,
    dry_run: bool,
    force: bool,
    respect_download_mp4_opus_env: bool,
) -> Tuple[int, int, int]:
    """
    Returns ``(ok, skipped, failed)`` for eligible sources under ``_gomeet_downloads``.
    """
    gdir = jurisdiction_dir / "_gomeet_downloads"
    if not gdir.is_dir():
        return 0, 0, 0

    if respect_download_mp4_opus_env and not meetings_download_mp4_opus_enabled():
        logger.info("gomeet_opus_skip SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS disabled dir={}", jurisdiction_dir)
        return 0, 0, 0

    ok = skipped = failed = 0
    for p in sorted(gdir.rglob("*")):
        if not p.is_file():
            continue
        low = p.name.lower()
        if any(low.endswith(s) for s in _SKIP_SUFFIXES):
            continue
        if p.suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        if p.suffix.lower() == ".opus":
            continue

        opus_guess = p.with_suffix(".opus")

        if dry_run:
            logger.info("gomeet_opus_dry_run would_encode {} -> {}", p, opus_guess.name)
            ok += 1
            continue

        good, reason = transcode_one_media_to_opus(p, force=force)
        if good:
            if reason == "opus_exists_skip":
                skipped += 1
            else:
                ok += 1
        else:
            failed += 1
    return ok, skipped, failed


def post_ytdlp_transcode_output(
    year_dir: Path,
    stem: str,
    *,
    respect_download_mp4_opus_env: bool = True,
) -> None:
    """
    After ``yt-dlp`` with ``-o '{stem}.%(ext)s``, find written file(s) and transcode to ``.opus``.
    """
    if respect_download_mp4_opus_env and not meetings_download_mp4_opus_enabled():
        logger.info(
            "gomeet_ytdlp_post_skip SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS disabled stem={} (MP4 kept)",
            stem,
        )
        return
    if not shutil.which("ffmpeg"):
        logger.warning(
            "gomeet_ytdlp_post_no_ffmpeg skip_opus stem={} dir={} (install ffmpeg; MP4 kept)",
            stem,
            year_dir,
        )
        return
    if not year_dir.is_dir():
        return

    esc = re.escape(stem)
    sources = [
        p
        for p in sorted(year_dir.glob(f"{esc}.*"))
        if p.suffix.lower() in _SOURCE_SUFFIXES
    ]
    if not sources:
        logger.warning(
            "gomeet_ytdlp_post_no_source_files stem={} dir={} (expected {}.mp4/webm/… next to final output)",
            stem,
            year_dir,
            stem,
        )
        return
    for p in sources:
        ok, reason = transcode_one_media_to_opus(p, force=False)
        if not ok and reason not in ("opus_exists_skip",):
            logger.warning("gomeet_ytdlp_post_transcode stem={} path={} reason={}", stem, p.name, reason)


def _iter_gomeet_roots(scraped_root: Path) -> List[Path]:
    found: Set[Path] = set()
    for g in scraped_root.rglob("_gomeet_downloads"):
        if g.is_dir():
            found.add(g.parent)
    return sorted(found)


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ModuleNotFoundError:
        pass

    ap = argparse.ArgumentParser(description="Transcode GoMeet MP4/webm/mkv under _gomeet_downloads to Opus.")
    ap.add_argument("--jurisdiction-dir", default="", help="Scrape folder with _gomeet_downloads.")
    ap.add_argument(
        "--scraped-meetings-root",
        default="",
        help="Process every jurisdiction that has _gomeet_downloads under this tree.",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="Re-encode even when .opus exists.")
    ap.add_argument(
        "--respect-download-mp4-opus-env",
        action="store_true",
        help="Honor SCRAPED_MEETINGS_DOWNLOAD_MP4_OPUS=false (skip all).",
    )
    args = ap.parse_args()

    targets: List[Path] = []
    if args.jurisdiction_dir:
        targets.append(Path(args.jurisdiction_dir).expanduser().resolve())
    root = (args.scraped_meetings_root or "").strip()
    if root:
        rp = Path(root).expanduser().resolve()
        if not rp.is_dir():
            logger.error("Not a directory: {}", rp)
            raise SystemExit(2)
        targets.extend(_iter_gomeet_roots(rp))

    if not targets:
        logger.error("Pass --jurisdiction-dir and/or --scraped-meetings-root.")
        raise SystemExit(2)

    seen: Set[Path] = set()
    unique: List[Path] = []
    for t in targets:
        if t in seen:
            continue
        seen.add(t)
        unique.append(t)

    t_ok = t_sk = t_fail = 0
    for jdir in unique:
        o, s, f = transcode_gomeet_downloads_under(
            jdir,
            dry_run=args.dry_run,
            force=args.force,
            respect_download_mp4_opus_env=args.respect_download_mp4_opus_env,
        )
        if o or s or f:
            logger.info("gomeet_opus_jurisdiction dir={} ok={} skipped={} failed={}", jdir, o, s, f)
        t_ok += o
        t_sk += s
        t_fail += f

    logger.info(
        "gomeet_opus_total ok={} skipped={} failed={} dry_run={}",
        t_ok,
        t_sk,
        t_fail,
        args.dry_run,
    )


if __name__ == "__main__":
    main()
