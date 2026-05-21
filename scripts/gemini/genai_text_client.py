"""
Text-only Google AI Studio calls (``google-genai``) with quota retry.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from loguru import logger

T = TypeVar("T")

_RETRY_IN_RE = re.compile(r"retry in\s+([\d.]+)\s*s", re.IGNORECASE)
_RETRY_DELAY_RE = re.compile(
    r"""retryDelay['"]?\s*[:=]\s*['"]?(\d+(?:\.\d+)?)s?""",
    re.IGNORECASE,
)


def is_genai_retryable(exc: BaseException) -> bool:
    """429 quota and transient 503/502 overload — retry with backoff."""
    msg = str(exc).upper()
    if any(
        token in msg
        for token in (
            "429",
            "RESOURCE_EXHAUSTED",
            "503",
            "UNAVAILABLE",
            "502",
            "BAD_GATEWAY",
            "OVERLOADED",
            "HIGH DEMAND",
        )
    ):
        return True
    for attr in ("code", "status_code", "status"):
        val = getattr(exc, attr, None)
        if val is None:
            continue
        s = str(val).upper()
        if val in (429, 502, 503) or s in ("429", "502", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"):
            return True
    return False


def is_genai_quota_exhausted(exc: BaseException) -> bool:
    return is_genai_retryable(exc)


def _genai_http_code(exc: BaseException) -> Optional[int]:
    for attr in ("code", "status_code", "status"):
        val = getattr(exc, attr, None)
        if val is None:
            continue
        if isinstance(val, int):
            return val
        s = str(val).strip()
        if s.isdigit():
            return int(s)
    msg = str(exc)
    for token in ("429", "502", "503"):
        if token in msg:
            return int(token)
    return None


def classify_genai_error(exc: BaseException) -> str:
    """Short category for logs (quota vs overload vs gateway)."""
    code = _genai_http_code(exc)
    msg = str(exc).upper()
    if code == 429 or "RESOURCE_EXHAUSTED" in msg or "QUOTA" in msg:
        return "rate limit / quota (429)"
    if code == 503 or "UNAVAILABLE" in msg or "OVERLOADED" in msg or "HIGH DEMAND" in msg:
        return "service overloaded (503)"
    if code == 502 or "BAD_GATEWAY" in msg:
        return "upstream bad gateway (502)"
    if code:
        return f"HTTP {code}"
    return "transient API error"


def describe_genai_error(exc: BaseException, *, max_len: int = 220) -> str:
    """One-line detail for operators (type, code, API message)."""
    parts = [type(exc).__name__]
    code = _genai_http_code(exc)
    if code is not None:
        parts.append(f"HTTP {code}")
    msg = re.sub(r"\s+", " ", str(exc).strip())
    if msg:
        if len(msg) > max_len:
            msg = msg[: max_len - 1] + "…"
        parts.append(msg)
    return " — ".join(parts)


def genai_quota_retry_delay_seconds(exc: BaseException, attempt: int) -> float:
    msg = str(exc)
    m = _RETRY_IN_RE.search(msg)
    if m:
        return max(float(m.group(1)), 1.0)
    m = _RETRY_DELAY_RE.search(msg)
    if m:
        return max(float(m.group(1)), 1.0)
    base = float(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRY_BASE_SECONDS", "30"))
    return base * (1.0 + 0.2 * attempt)


def call_with_genai_quota_retry(fn: Callable[[], T], *, label: str = "Gemini") -> T:
    max_retries = max(1, int(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRIES", "5")))
    buffer = float(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRY_BUFFER_SECONDS", "1.0"))
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not is_genai_retryable(exc):
                logger.error("{}: non-retryable API failure — {}", label, describe_genai_error(exc))
                raise
            if attempt >= max_retries - 1:
                logger.error(
                    "{}: gave up after {} attempt(s) — {}",
                    label,
                    max_retries,
                    describe_genai_error(exc),
                )
                raise RuntimeError(
                    f"{label}: failed after {max_retries} attempt(s) ({classify_genai_error(exc)}). "
                    f"{describe_genai_error(exc)}"
                ) from exc
            delay = genai_quota_retry_delay_seconds(exc, attempt) + buffer
            logger.warning(
                "{}: {} — sleeping {:.0f}s, retry {}/{} ({})",
                label,
                classify_genai_error(exc),
                delay,
                attempt + 2,
                max_retries,
                describe_genai_error(exc, max_len=160),
            )
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"{label}: quota retry loop exited without result")


@dataclass
class TextGenAIResult:
    text: str
    model: str
    raw_response: Any = None


def default_flash_lite_model() -> str:
    return (
        os.environ.get("GEMINI_FLASH_LITE_MODEL")
        or os.environ.get("GOVERNANCE_GENAI_MODEL")
        or "gemini-2.5-flash-lite"
    ).strip()


def call_gemini_text(
    *,
    api_key: str,
    model: str,
    user_text: str,
    system_instruction: str = "",
    temperature: float = 0.1,
    max_output_tokens: int = 65536,
) -> TextGenAIResult:
    """Single-turn text generation via AI Studio API."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    parts = [types.Part.from_text(text=user_text)]
    config_kwargs: dict[str, Any] = dict(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    if system_instruction.strip():
        config_kwargs["system_instruction"] = system_instruction.strip()

    def _generate():
        return client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(**config_kwargs),
        )

    response = call_with_genai_quota_retry(_generate, label=model)
    text = (getattr(response, "text", None) or "").strip()
    if not text:
        raise RuntimeError(f"Empty response from {model}")
    return TextGenAIResult(text=text, model=model, raw_response=response)


def extract_json_from_model_text(text: str) -> Optional[dict[str, Any]]:
    """Best-effort JSON object from fenced or bare model output."""
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(raw[start : i + 1])
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    return None
    return None
