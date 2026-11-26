"""One-shot text call to a Claude model through the official Anthropic SDK (#848).

Used by the meeting chat (``api/routes/chat_meetings.py``). The SDK reads the key from
``ANTHROPIC_API_KEY``; this module never reads, stores or logs it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

#: The chat's default model. Change it with ``CHAT_MODEL``, not here.
DEFAULT_CHAT_MODEL = "claude-haiku-5-5"

_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


class ClaudeRefusalError(RuntimeError):
    """The model declined to answer (``stop_reason == "refusal"``). ``category`` may be ``None``."""

    def __init__(self, category: str | None = None) -> None:
        super().__init__(f"Claude declined to answer (category: {category or 'not given'})")
        self.category = category


@dataclass(frozen=True)
class ClaudeTextResult:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int
    stop_reason: str | None


def _input_token_total(usage: Any) -> tuple[int | None, int]:
    """All input tokens of the call and how many of them were read from the cache.

    The API reports uncached, cache-read and cache-write input separately; the usage report prices
    "input minus cached" at the input rate, so the total is what it needs. Cache writes cost a
    little more than plain input and are counted as plain input here (the chat does not cache)."""
    if usage is None:
        return None, 0
    plain = getattr(usage, "input_tokens", None)
    if plain is None:
        return None, 0
    cached = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    written = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    return int(plain) + cached + written, cached


def call_claude_text(
    *,
    model: str,
    system: str,
    user_text: str,
    max_tokens: int = 2048,
    effort: str = "low",
    client: Any = None,
) -> ClaudeTextResult:
    """Send one system prompt and one user message; return the answer text and token counts.

    Thinking is left at the model's default (adaptive) and its depth is set with ``effort``; no
    sampling parameters are sent, because current Claude models reject non-default ones. Output
    tokens include thinking tokens, as the API bills them. Raises ``ClaudeRefusalError`` on a
    refusal and lets the SDK's own errors (``anthropic.AuthenticationError`` and the rest) through.
    """
    if effort not in _EFFORT_LEVELS:
        raise ValueError(f"effort must be one of {_EFFORT_LEVELS}, not {effort!r}")
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": user_text}],
    )
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        raise ClaudeRefusalError(getattr(details, "category", None))
    text = "".join(
        block.text for block in (response.content or []) if getattr(block, "type", None) == "text"
    ).strip()
    usage = getattr(response, "usage", None)
    input_tokens, cached = _input_token_total(usage)
    output_tokens = getattr(usage, "output_tokens", None) if usage is not None else None
    return ClaudeTextResult(
        text=text,
        input_tokens=input_tokens,
        output_tokens=int(output_tokens) if output_tokens is not None else None,
        cached_input_tokens=cached,
        stop_reason=stop_reason,
    )


# --- The transcript-analysis call (#871) -----------------------------------------------------------
#
# The light analysis and its reports send a whole meeting transcript and get a long JSON or Markdown
# answer back. That needs streaming (a large ``max_tokens`` can outlive an HTTP timeout), prompt
# caching (the report stage re-sends one transcript several times), a guard against the long-prompt
# price tier, and a usage object the usage log can price. ``call_claude_text`` above stays as the
# chat's small call.

#: Output cap the analysis call uses unless the caller passes its own; the API allows up to 128,000.
DEFAULT_ANALYSIS_MAX_TOKENS = 32_000
MAX_OUTPUT_TOKENS_CAP = 128_000
DEFAULT_EFFORT = "low"
#: Above this many prompt tokens the API bills the whole call at five times the rate.
DEFAULT_MAX_PROMPT_TOKENS = 100_000


class ClaudePromptTooLongError(RuntimeError):
    """The prompt is over ``CLAUDE_MAX_PROMPT_TOKENS``; nothing was sent."""

    def __init__(self, tokens: int, limit: int) -> None:
        super().__init__(f"prompt is {tokens:,} tokens, over the {limit:,}-token price tier")
        self.tokens = tokens
        self.limit = limit


class ClaudeTruncatedError(RuntimeError):
    """The answer hit ``max_tokens`` and was cut off, so it is not usable as JSON or a report."""

    def __init__(self, max_tokens: int, usage: Any = None) -> None:
        super().__init__(f"Claude output was cut off at max_tokens={max_tokens:,}")
        self.max_tokens = max_tokens
        self.usage = usage


class ClaudeCountTokensError(RuntimeError):
    """``count_tokens`` failed, so the long-prompt guard could not run; the call is not sent blind."""


@dataclass(frozen=True)
class ClaudeAnalysisResult:
    """Thinking-free answer text, the billed token counts and why generation stopped."""

    text: str
    usage: Any  # llm.usage.calls.LLMCallUsage
    stop_reason: str | None
    raw_response: Any = None


def claude_effort(value: str | None = None) -> str:
    """``CLAUDE_EFFORT`` (default ``low``), validated; a bad value fails before any request."""
    raw = value if value is not None else os.environ.get("CLAUDE_EFFORT")
    level = (raw or DEFAULT_EFFORT).strip().lower() or DEFAULT_EFFORT
    if level not in _EFFORT_LEVELS:
        raise ValueError(f"CLAUDE_EFFORT must be one of {_EFFORT_LEVELS}, not {raw!r}")
    return level


def claude_max_prompt_tokens(value: str | None = None) -> int:
    """``CLAUDE_MAX_PROMPT_TOKENS`` (default 100000); ``0`` turns the guard off."""
    raw = value if value is not None else os.environ.get("CLAUDE_MAX_PROMPT_TOKENS")
    if raw is None or not str(raw).strip():
        return DEFAULT_MAX_PROMPT_TOKENS
    try:
        limit = int(str(raw).strip())
    except ValueError:
        raise ValueError(f"CLAUDE_MAX_PROMPT_TOKENS must be a whole number, not {raw!r}") from None
    if limit < 0:
        raise ValueError(f"CLAUDE_MAX_PROMPT_TOKENS must be 0 or more, not {raw!r}")
    return limit


def _usage_row(usage: Any) -> Any:
    """The API's usage as an ``LLMCallUsage``.

    Thinking tokens are billed as output and are already inside ``output_tokens``; the API does not
    split them out, so ``thinking_token_count`` stays ``None`` rather than a guessed split."""
    from llm.usage.calls import LLMCallUsage

    total_in, cached = _input_token_total(usage)
    out = getattr(usage, "output_tokens", None) if usage is not None else None
    out = int(out) if out is not None else None
    return LLMCallUsage(
        input_token_count=total_in,
        cached_input_token_count=cached if total_in is not None else None,
        output_token_count=out,
        thinking_token_count=None,
        total_token_count=(total_in + out) if total_in is not None and out is not None else None,
    )


def guard_prompt_length(
    client: Any, *, model: str, system: str, user_text: str, max_prompt_tokens: int
) -> int | None:
    """Count the prompt and raise ``ClaudePromptTooLongError`` when it is over the limit.

    ``count_tokens`` is free. Returns the count, or ``None`` when the guard is off. If the count
    itself fails the call is not sent blind: ``ClaudeCountTokensError`` (SDK errors a retry can fix
    are re-raised as they are, so the caller's retry loop sees them)."""
    if max_prompt_tokens <= 0:
        return None
    import anthropic

    try:
        counted = client.messages.count_tokens(
            model=model, system=system, messages=[{"role": "user", "content": user_text}]
        )
        tokens = int(counted.input_tokens)
    except anthropic.APIError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ClaudeCountTokensError(f"could not count prompt tokens: {exc}") from exc
    if tokens > max_prompt_tokens:
        raise ClaudePromptTooLongError(tokens, max_prompt_tokens)
    return tokens


def call_claude_analysis(
    *,
    model: str,
    system: str,
    user_text: str,
    max_tokens: int = DEFAULT_ANALYSIS_MAX_TOKENS,
    effort: str | None = None,
    max_prompt_tokens: int | None = None,
    cache: bool = True,
    client: Any,
) -> ClaudeAnalysisResult:
    """One streamed request for the transcript analysis; a single attempt (the caller retries).

    Sends no sampling parameters, no ``thinking`` block and no prefill: Claude models reject them.
    ``effort`` and ``max_prompt_tokens`` default to ``CLAUDE_EFFORT`` / ``CLAUDE_MAX_PROMPT_TOKENS``,
    read here so a bad value fails before anything is sent. Raises ``ClaudePromptTooLongError``,
    ``ClaudeRefusalError``, ``ClaudeTruncatedError`` and ``RuntimeError`` for an empty answer; the
    last three carry ``.usage`` so the caller can still log what the call cost.
    """
    level = claude_effort(effort)
    limit = claude_max_prompt_tokens() if max_prompt_tokens is None else max_prompt_tokens
    max_tokens = max(1, min(int(max_tokens), MAX_OUTPUT_TOKENS_CAP))
    guard_prompt_length(client, model=model, system=system, user_text=user_text, max_prompt_tokens=limit)

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_text}],
        "output_config": {"effort": level},
    }
    if cache:
        kwargs["cache_control"] = {"type": "ephemeral"}
    with client.messages.stream(**kwargs) as stream:
        message = stream.get_final_message()

    usage = _usage_row(getattr(message, "usage", None))
    stop_reason = getattr(message, "stop_reason", None)
    if stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        refusal = ClaudeRefusalError(getattr(details, "category", None))
        refusal.usage = usage  # type: ignore[attr-defined]
        raise refusal
    if stop_reason == "max_tokens":
        raise ClaudeTruncatedError(max_tokens, usage)
    text = "".join(
        block.text for block in (message.content or []) if getattr(block, "type", None) == "text"
    ).strip()
    if not text:
        empty = RuntimeError(f"Empty response from {model} (stop_reason={stop_reason})")
        empty.usage = usage  # type: ignore[attr-defined]
        raise empty
    return ClaudeAnalysisResult(text=text, usage=usage, stop_reason=stop_reason, raw_response=message)
