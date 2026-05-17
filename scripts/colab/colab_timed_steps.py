"""
Timed step lines for Colab notebooks (stdout + optional logger).

Enable/disable with ``GOVERNANCE_STEP_TIMING`` (default on).
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator, Optional


def step_timing_enabled() -> bool:
    return os.environ.get("GOVERNANCE_STEP_TIMING", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _emit(
    msg: str,
    *,
    prefix: str,
    logger: Optional[logging.Logger],
) -> None:
    line = f"{prefix}{msg}"
    print(line, flush=True)
    if logger is not None:
        logger.info(line)


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
        _emit(f"✓ {label} — {elapsed:.1f}s", prefix=prefix, logger=logger)


def format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {seconds % 60:.0f}s"
