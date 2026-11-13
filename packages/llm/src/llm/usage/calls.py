"""One usage row per model call (#262).

``call_gemini_text`` records every call here: the token counts the API reports
(input, cached input, output, thinking), the wall time including retries, the
number of attempts, and whether it succeeded. Callers add labels with
:func:`llm_call_context`::

    with llm_call_context(stage="part1", video_id=video_id, jurisdiction_id=jid):
        result = call_gemini_text(...)
    result.usage.thinking_token_count

A count the API did not report stays ``None``; it is never guessed.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[5]
_WRITE_LOCK = threading.Lock()
_RUN_ID = (os.environ.get("LLM_USAGE_RUN_ID") or "").strip() or uuid.uuid4().hex[:12]
_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("llm_call_context", default=None)

# Labels a caller may set; anything else passed to llm_call_context is dropped,
# so a transcript or prompt can never end up in the usage log by accident.
CONTEXT_LABELS = ("stage", "video_id", "jurisdiction_id", "api_mode")

TOKEN_COLUMNS = (
    "input_token_count",
    "cached_input_token_count",
    "output_token_count",
    "thinking_token_count",
    "total_token_count",
)


@dataclass
class LLMCallUsage:
    """What one model call used. ``None`` means the API did not report it."""

    input_token_count: int | None = None
    cached_input_token_count: int | None = None
    output_token_count: int | None = None
    thinking_token_count: int | None = None
    total_token_count: int | None = None
    latency_seconds: float | None = None
    attempt_count: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _field(obj: Any, *names: str) -> Any:
    """First of ``names`` present on an SDK object or a JSON dict."""
    for name in names:
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        if value is not None:
            return value
    return None


def usage_from_genai_response(raw: Any) -> LLMCallUsage:
    """Token counts from a google-genai response, a stream's last chunk, or a
    Batch API result line (camelCase JSON). Missing metadata gives all ``None``."""
    meta = _field(raw, "usage_metadata", "usageMetadata") if raw is not None else None
    if meta is None:
        return LLMCallUsage()
    return LLMCallUsage(
        input_token_count=_int_or_none(_field(meta, "prompt_token_count", "promptTokenCount")),
        cached_input_token_count=_int_or_none(
            _field(meta, "cached_content_token_count", "cachedContentTokenCount")
        ),
        output_token_count=_int_or_none(
            _field(meta, "candidates_token_count", "candidatesTokenCount")
        ),
        thinking_token_count=_int_or_none(
            _field(meta, "thoughts_token_count", "thoughtsTokenCount")
        ),
        total_token_count=_int_or_none(_field(meta, "total_token_count", "totalTokenCount")),
    )


def usage_from_openai_response(raw: Any) -> LLMCallUsage:
    """Token counts from an OpenAI-protocol response (DeepSeek). Reasoning tokens
    are part of ``completion_tokens`` there, so they are taken out of the output
    count to keep ``output + thinking`` the billed output, as for Gemini."""
    meta = _field(raw, "usage") if raw is not None else None
    if meta is None:
        return LLMCallUsage()
    completion = _int_or_none(_field(meta, "completion_tokens"))
    details = _field(meta, "completion_tokens_details")
    thinking = _int_or_none(_field(details, "reasoning_tokens")) if details is not None else None
    output = completion - thinking if completion is not None and thinking else completion
    cached = _int_or_none(_field(meta, "prompt_cache_hit_tokens"))
    if cached is None:
        prompt_details = _field(meta, "prompt_tokens_details")
        if prompt_details is not None:
            cached = _int_or_none(_field(prompt_details, "cached_tokens"))
    return LLMCallUsage(
        input_token_count=_int_or_none(_field(meta, "prompt_tokens")),
        cached_input_token_count=cached,
        output_token_count=output,
        thinking_token_count=thinking,
        total_token_count=_int_or_none(_field(meta, "total_tokens")),
    )


@contextmanager
def llm_call_context(**labels: Any) -> Iterator[None]:
    """Labels for every model call made inside the block (see ``CONTEXT_LABELS``)."""
    merged = dict(_CONTEXT.get() or {})
    merged.update(
        {k: str(v) for k, v in labels.items() if k in CONTEXT_LABELS and v not in (None, "")}
    )
    token = _CONTEXT.set(merged)
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def current_context() -> dict[str, Any]:
    return dict(_CONTEXT.get() or {})


def usage_enabled() -> bool:
    return os.environ.get("LLM_USAGE_LOG", "1").strip().lower() not in ("0", "false", "no", "off")


def usage_log_dir() -> Path:
    explicit = (os.environ.get("LLM_USAGE_LOG_DIR") or "").strip()
    return Path(explicit).expanduser() if explicit else _REPO_ROOT / "data" / "logs" / "llm_usage"


def run_id() -> str:
    """One id per process (or ``LLM_USAGE_RUN_ID``), to group a run's rows."""
    return _RUN_ID


def append_row(prefix: str, row: dict[str, Any], *, when: datetime | None = None) -> Path | None:
    """Append one JSON line to ``<prefix>_YYYYMMDD.jsonl``. Returns the file, or
    ``None`` when recording is off or the write failed (logged, never raised)."""
    if not usage_enabled():
        return None
    try:
        day = (when or datetime.now(UTC)).strftime("%Y%m%d")
        path = usage_log_dir() / f"{prefix}_{day}.jsonl"
        line = json.dumps(row, ensure_ascii=False, default=str)
        with _WRITE_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return path
    except Exception as exc:  # noqa: BLE001 - usage logging never breaks a run
        logger.warning("usage log write skipped ({}): {}", prefix, exc)
        return None


def record_llm_call(
    *,
    provider: str,
    model: str,
    usage: LLMCallUsage | None,
    is_ok: bool,
    error_type: str | None = None,
    api_mode: str | None = None,
    called_at: datetime | None = None,
    **labels: Any,
) -> dict[str, Any]:
    """Write one call's row and return it. Labels given here win over the context."""
    context = current_context()
    context.update({k: str(v) for k, v in labels.items() if k in CONTEXT_LABELS and v})
    when = called_at or datetime.now(UTC)
    used = usage or LLMCallUsage()
    row: dict[str, Any] = {
        "llm_call_id": str(uuid.uuid4()),
        "called_at": when.isoformat(),
        "provider": provider,
        "model": model,
        "api_mode": api_mode or context.get("api_mode") or "interactive",
        "stage": context.get("stage"),
        "video_id": context.get("video_id"),
        "jurisdiction_id": context.get("jurisdiction_id"),
        "run_id": run_id(),
        **{name: getattr(used, name) for name in TOKEN_COLUMNS},
        "latency_seconds": (
            round(used.latency_seconds, 3) if used.latency_seconds is not None else None
        ),
        "attempt_count": used.attempt_count,
        "is_ok": bool(is_ok),
        "error_type": error_type,
        "host_name": socket.gethostname(),
    }
    append_row("llm_calls", row, when=when)
    logger.info(
        "llm call {} {} [{}] {}: in={} cached={} out={} thinking={} seconds={} attempts={} ok={}",
        provider,
        model,
        row["stage"] or "-",
        row["api_mode"],
        row["input_token_count"],
        row["cached_input_token_count"],
        row["output_token_count"],
        row["thinking_token_count"],
        row["latency_seconds"],
        row["attempt_count"],
        row["is_ok"],
    )
    return row
