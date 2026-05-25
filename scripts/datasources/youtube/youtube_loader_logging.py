"""
Shared Loguru setup for ``load_youtube_events_to_postgres`` and ``scrape_youtube_channels``.

Parallel county workers must not each attach a stderr handler (causes
``I/O operation on closed file`` when yt-dlp touches stderr). Use one
enqueue-backed file sink plus optional main-thread stderr.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_LOG_DIR = _REPO_ROOT / "data" / "bronze" / "youtube_loader_logs"

# Readable one-line format (no noisy module:function:line).
_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {message}"


def _stream_writable(stream) -> bool:
    if stream is None:
        return False
    try:
        if getattr(stream, "closed", False):
            return False
        stream.flush()
        return True
    except (ValueError, OSError):
        return False


def _parallel_filter(record: dict) -> bool:
    """With multiple workers, hide per-tab yt-dlp chatter; keep progress + warnings."""
    if os.getenv("YOUTUBE_LOADER_PARALLEL") != "1":
        return True
    if record["level"].no >= 30:  # WARNING+
        return True
    module = record.get("module") or ""
    if module in (
        "load_youtube_events_to_postgres",
        "youtube_loader_logging",
        "__main__",
    ):
        return True
    if record["extra"].get("progress"):
        return True
    return False


def _stderr_filter(record: dict) -> bool:
    """Console: progress + warnings/errors from any thread; INFO only on main thread when parallel."""
    if not _parallel_filter(record):
        return False
    if os.getenv("YOUTUBE_LOADER_PARALLEL") == "1":
        if record["level"].no >= 30:
            return True
        return record["thread"].name == "MainThread"
    return True


def configure_youtube_loader_logging(
    *,
    workers: int = 1,
    log_file: Path | str | None = None,
    level: str = "INFO",
) -> Path:
    """
    Configure process-wide logging once. Returns the log file path used.
    """
    logger.remove()

    if workers > 1:
        os.environ["YOUTUBE_LOADER_PARALLEL"] = "1"
    else:
        os.environ.pop("YOUTUBE_LOADER_PARALLEL", None)

    log_path = Path(log_file) if log_file else _DEFAULT_LOG_DIR / (
        f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_path),
        format=_FILE_FORMAT,
        level=level,
        enqueue=True,
        colorize=False,
        filter=_parallel_filter,
    )

    if _stream_writable(sys.stderr):
        logger.add(
            sys.stderr,
            format=_CONSOLE_FORMAT,
            level=level,
            enqueue=True,
            colorize=True,
            filter=_stderr_filter,
        )

    if workers > 1:
        logger.info(
            "Parallel mode ({} workers): detailed yt-dlp logs → {}",
            workers,
            log_path,
        )
    return log_path


def log_progress(message: str, *args, **kwargs) -> None:
    """Coordinator progress line (always shown in parallel mode)."""
    logger.bind(progress=True).info(message, *args, **kwargs)
