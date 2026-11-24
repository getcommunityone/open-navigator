"""One-shot text call to a Claude model through the official Anthropic SDK (#848).

Used by the meeting chat (``api/routes/chat_meetings.py``). The SDK reads the key from
``ANTHROPIC_API_KEY``; this module never reads, stores or logs it.
"""

from __future__ import annotations

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
