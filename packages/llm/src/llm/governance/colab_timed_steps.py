"""
Timed step lines for Colab notebooks (stdout + optional logger).

- ``GOVERNANCE_STEP_TIMING`` (default on) — ``▶`` / ``✓`` with elapsed seconds
- ``GOVERNANCE_STEP_TIMESTAMPS`` (default on) — ``HH:MM:SS`` prefix on each line
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional


def step_timing_enabled() -> bool:
    return os.environ.get("GOVERNANCE_STEP_TIMING", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def wall_clock_enabled() -> bool:
    return os.environ.get("GOVERNANCE_STEP_TIMESTAMPS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def wall_clock_prefix() -> str:
    if wall_clock_enabled():
        return datetime.now().strftime("%H:%M:%S ")
    return ""


def _emit(
    msg: str,
    *,
    prefix: str,
    logger: Optional[logging.Logger],
) -> None:
    line = f"{prefix}{wall_clock_prefix()}{msg}"
    print(line, flush=True)
    if logger is not None:
        logger.info(line)


def log_line(
    msg: str,
    *,
    prefix: str = "  ",
    logger: Optional[logging.Logger] = None,
) -> None:
    """Print one line with optional wall-clock prefix (and mirror to ``logger``)."""
    _emit(msg, prefix=prefix, logger=logger)


@contextmanager
def timed_step(
    label: str,
    *,
    prefix: str = "  ",
    logger: Optional[logging.Logger] = None,
) -> Iterator[None]:
    """Print ``▶ label …`` then ``✓ label — N.Ns`` (and mirror to ``logger`` if set)."""
    if not step_timing_enabled():
        yield
        return
    t0 = time.perf_counter()
    _emit(f"▶ {label} …", prefix=prefix, logger=logger)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - t0
        _emit(f"✓ {label} — {format_elapsed(elapsed)}", prefix=prefix, logger=logger)


def format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {seconds % 60:.0f}s"


def heartbeat_enabled() -> bool:
    """Periodic ``… still working`` lines during long steps (Colab looks stuck otherwise)."""
    raw = os.environ.get("GOVERNANCE_HEARTBEAT_SECONDS", "45").strip().lower()
    return raw not in ("0", "false", "no", "off")


def heartbeat_interval() -> float:
    try:
        return max(15.0, float(os.environ.get("GOVERNANCE_HEARTBEAT_SECONDS", "45")))
    except ValueError:
        return 45.0


def format_file_size(path: os.PathLike[str] | str) -> str:
    try:
        nbytes = os.path.getsize(path)
    except OSError:
        return ""
    if nbytes >= 1024 * 1024 * 1024:
        return f"{nbytes / (1024**3):.2f} GB"
    if nbytes >= 1024 * 1024:
        return f"{nbytes / (1024**2):.1f} MB"
    if nbytes >= 1024:
        return f"{nbytes / 1024:.0f} KB"
    return f"{nbytes} B"


def configure_pipeline_logging(level: int = logging.INFO) -> None:
    """
    Mirror library loggers to Colab stdout (``gemma_hf_backend`` load progress, etc.).

    Call once in notebook §3. Set ``GOVERNANCE_PIPELINE_LOG_LEVEL=DEBUG`` for more detail.
    """
    raw = os.environ.get("GOVERNANCE_PIPELINE_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, raw, level)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    for name, lvl in (
        ("gemma_hf_backend", level),
        ("transformers", logging.WARNING),
        ("accelerate", logging.WARNING),
        ("huggingface_hub", logging.INFO),
    ):
        logging.getLogger(name).setLevel(lvl)


@contextmanager
def log_phase(
    label: str,
    *,
    prefix: str = "  ",
    detail: str = "",
    logger: Optional[logging.Logger] = None,
) -> Iterator[None]:
    """
    Start/finish lines plus heartbeat while blocked (HF download, ffmpeg, ``generate``).

    Disable heartbeats with ``GOVERNANCE_HEARTBEAT_SECONDS=0``.
    """
    hint = f" — {detail}" if detail else ""
    t0 = time.perf_counter()
    _emit(f"▶ {label}{hint}", prefix=prefix, logger=logger)
    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(heartbeat_interval()):
            _emit(
                f"… still {label} ({format_elapsed(time.perf_counter() - t0)})",
                prefix=prefix,
                logger=logger,
            )

    thread: Optional[threading.Thread] = None
    if heartbeat_enabled():
        thread = threading.Thread(target=_beat, daemon=True)
        thread.start()
    try:
        yield
    finally:
        stop.set()
        if thread is not None:
            thread.join(timeout=2.0)
        _emit(f"✓ {label} — {format_elapsed(time.perf_counter() - t0)}", prefix=prefix, logger=logger)
