"""#848: the Claude text call used by the meeting chat. The SDK client is stubbed; no network."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from llm.claude.text_client import (
    DEFAULT_CHAT_MODEL,
    ClaudeRefusalError,
    call_claude_text,
)


class _Client:
    def __init__(self, response):
        self.response, self.kwargs = response, None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _response(blocks, *, stop_reason="end_turn", usage=None, stop_details=None):
    return SimpleNamespace(content=blocks, stop_reason=stop_reason, usage=usage, stop_details=stop_details)


def _text(value):
    return SimpleNamespace(type="text", text=value)


def test_default_model_is_haiku():
    assert DEFAULT_CHAT_MODEL == "claude-haiku-5-5"


def test_request_shape_and_answer():
    usage = SimpleNamespace(input_tokens=900, output_tokens=200, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    client = _Client(_response([SimpleNamespace(type="thinking", thinking=""), _text(" The council voted 5-2. ")], usage=usage))
    result = call_claude_text(model="claude-haiku-5-5", system="sys", user_text="question", client=client)
    assert client.kwargs == {
        "model": "claude-haiku-5-5",
        "max_tokens": 2048,
        "system": "sys",
        "output_config": {"effort": "low"},
        "messages": [{"role": "user", "content": "question"}],
    }
    # Nothing the current models reject: no sampling parameters, no thinking budget, no prefill.
    assert not {"temperature", "top_p", "top_k", "thinking"} & set(client.kwargs)
    assert result.text == "The council voted 5-2."
    assert (result.input_tokens, result.output_tokens, result.cached_input_tokens) == (900, 200, 0)
    assert result.stop_reason == "end_turn"


def test_input_total_includes_cached_and_written_tokens():
    usage = SimpleNamespace(input_tokens=100, output_tokens=10, cache_read_input_tokens=700, cache_creation_input_tokens=50)
    result = call_claude_text(model="m", system="s", user_text="u", client=_Client(_response([_text("ok")], usage=usage)))
    assert (result.input_tokens, result.cached_input_tokens) == (850, 700)


def test_missing_usage_gives_no_counts_not_zeros():
    result = call_claude_text(model="m", system="s", user_text="u", client=_Client(_response([_text("ok")])))
    assert result.input_tokens is None and result.output_tokens is None


def test_refusal_raises_and_is_never_read_as_an_answer():
    response = _response([], stop_reason="refusal", stop_details=SimpleNamespace(category="general_harms"))
    with pytest.raises(ClaudeRefusalError) as err:
        call_claude_text(model="m", system="s", user_text="u", client=_Client(response))
    assert err.value.category == "general_harms"
    # stop_details can be null on a refusal.
    with pytest.raises(ClaudeRefusalError):
        call_claude_text(model="m", system="s", user_text="u", client=_Client(_response([], stop_reason="refusal")))


def test_unknown_effort_is_rejected_before_any_call():
    client = _Client(_response([_text("ok")]))
    with pytest.raises(ValueError):
        call_claude_text(model="m", system="s", user_text="u", effort="turbo", client=client)
    assert client.kwargs is None
