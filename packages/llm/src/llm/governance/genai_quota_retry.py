"""
Retry helpers for Google AI Studio / Gemini API quota (429 RESOURCE_EXHAUSTED).

Used by ``governance_meeting_llm``, ``gatekeeper_triage``, and demo loops that
burst input tokens (e.g. Demo 2 HIGH pages on ``gemma-4-26b``).
"""

from __future__ import annotations

import os
import re
import time
from typing import Callable, TypeVar

T = TypeVar("T")

_RETRY_IN_RE = re.compile(r"retry in\s+([\d.]+)\s*s", re.IGNORECASE)
_RETRY_DELAY_RE = re.compile(
    r"""retryDelay['"]?\s*[:=]\s*['"]?(\d+(?:\.\d+)?)s?""",
    re.IGNORECASE,
)


def is_genai_quota_exhausted(exc: BaseException) -> bool:
    """True when the SDK error is a per-minute / quota 429."""
    msg = str(exc).upper()
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return True
    for attr in ("code", "status_code", "status"):
        val = getattr(exc, attr, None)
        if val is None:
            continue
        s = str(val).upper()
        if val == 429 or s in ("429", "RESOURCE_EXHAUSTED"):
            return True
    return False


def genai_quota_retry_delay_seconds(exc: BaseException, attempt: int) -> float:
    """Seconds to sleep before the next attempt (API hint or env default)."""
    msg = str(exc)
    m = _RETRY_IN_RE.search(msg)
    if m:
        return max(float(m.group(1)), 1.0)
    m = _RETRY_DELAY_RE.search(msg)
    if m:
        return max(float(m.group(1)), 1.0)
    base = float(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRY_BASE_SECONDS", "30"))
    return base * (1.0 + 0.2 * attempt)


def call_with_genai_quota_retry(fn: Callable[[], T], *, label: str = "Gemma") -> T:
    """Call ``fn``; on 429 RESOURCE_EXHAUSTED, sleep and retry."""
    max_retries = max(1, int(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRIES", "5")))
    buffer = float(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRY_BUFFER_SECONDS", "1.0"))
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            if not is_genai_quota_exhausted(exc) or attempt >= max_retries - 1:
                raise
            last_exc = exc
            delay = genai_quota_retry_delay_seconds(exc, attempt) + buffer
            from .colab_timed_steps import log_line

            log_line(
                f"⚠️  {label}: quota/rate limit (429) — sleeping {delay:.0f}s "
                f"then retry {attempt + 2}/{max_retries}…",
                prefix="   ",
            )
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{label}: quota retry loop exited without result")


def demo3_api_timeout_seconds() -> int:
    """Wall-clock cap per Demo 3 PDF (full document + thinking). 0 = no limit."""
    raw = os.environ.get("GOVERNANCE_DEMO3_API_TIMEOUT_SECONDS", "900").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 900


def call_with_wall_clock_timeout(
    fn: Callable[[], T],
    *,
    timeout_seconds: int,
    label: str = "Gemma",
) -> T:
    """Run ``fn`` in a worker thread; raise ``TimeoutError`` if it exceeds the cap."""
    if timeout_seconds <= 0:
        return fn()
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            raise TimeoutError(
                f"{label} timed out after {timeout_seconds}s. "
                "Interrupt the cell if needed; reuse partial outputs or set "
                "GOVERNANCE_DEMO3_API_TIMEOUT_SECONDS higher. "
                "Faster: GOVERNANCE_THINKING_MODEL=gemma-4-26b-a4b-it or "
                "GOVERNANCE_DEMO_THINKING_BUDGET=0."
            ) from exc


def genai_inter_call_pause(token_budget: str | None = None) -> None:
    """Pace successive generate_content calls to stay under per-model TPM."""
    budget = (token_budget or "").upper()
    if budget == "HIGH":
        delay = float(os.environ.get("GOVERNANCE_GENAI_INTER_CALL_DELAY_HIGH_SECONDS", "5"))
    else:
        delay = float(os.environ.get("GOVERNANCE_GENAI_INTER_CALL_DELAY_SECONDS", "2"))
    if delay > 0:
        time.sleep(delay)
