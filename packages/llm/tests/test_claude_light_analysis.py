"""#871: the light analysis on Claude Haiku. The Anthropic client is stubbed; no network, no key."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from llm.claude import text_client as tc
from llm.gemini import genai_text_client as gtc
from llm.gemini import meeting_transcript_policy as mtp
from llm.usage import calls
from llm.usage.prices import call_cost_usd, load_prices

MODEL = "claude-haiku-5-5"


def _usage(inp=1000, out=200, cache_read=0, cache_write=0):
    return SimpleNamespace(
        input_tokens=inp, output_tokens=out,
        cache_read_input_tokens=cache_read, cache_creation_input_tokens=cache_write,
    )  # fmt: skip


def _message(text="{}", *, stop_reason="end_turn", usage=None, blocks=None, stop_details=None):
    content = blocks if blocks is not None else [
        SimpleNamespace(type="thinking", thinking="hmm"),
        SimpleNamespace(type="text", text=text),
    ]
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, usage=usage or _usage(), stop_details=stop_details
    )


class _Stream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


class _Client:
    """``outcomes`` is consumed one per stream() call; an exception instance is raised."""

    def __init__(self, outcomes=None, *, prompt_tokens=1000, count_error=None):
        self.outcomes = list(outcomes if outcomes is not None else [_message()])
        self.stream_calls: list[dict] = []
        self.count_calls: list[dict] = []
        self._prompt_tokens, self._count_error = prompt_tokens, count_error
        self.messages = SimpleNamespace(stream=self._stream, count_tokens=self._count)

    def _count(self, **kwargs):
        self.count_calls.append(kwargs)
        if self._count_error:
            raise self._count_error
        return SimpleNamespace(input_tokens=self._prompt_tokens)

    def _stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return _Stream(outcome)


def _status_error(cls, status, headers=None):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request, headers=headers or {})
    return cls("boom", response=response, body=None)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for name in ("CLAUDE_EFFORT", "CLAUDE_MAX_PROMPT_TOKENS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_USAGE_LOG_DIR", str(tmp_path / "usage"))
    monkeypatch.setattr(gtc.time, "sleep", lambda s: None)


# --- request shape ---------------------------------------------------------------------------
def test_request_shape_and_thinking_free_text():
    client = _Client([_message('{"a": 1}')])
    result = tc.call_claude_analysis(model=MODEL, system="sys", user_text="transcript", client=client)
    assert result.text == '{"a": 1}'
    kwargs = client.stream_calls[0]
    assert kwargs["model"] == MODEL and kwargs["system"] == "sys"
    assert kwargs["messages"] == [{"role": "user", "content": "transcript"}]
    assert kwargs["output_config"] == {"effort": "low"}
    assert kwargs["cache_control"] == {"type": "ephemeral"}
    assert kwargs["max_tokens"] == 32_000
    for banned in ("temperature", "top_p", "top_k", "thinking"):
        assert banned not in kwargs


def test_max_tokens_is_overridable_and_capped():
    client = _Client([_message(), _message()])
    tc.call_claude_analysis(model=MODEL, system="", user_text="t", max_tokens=65536, client=client)
    tc.call_claude_analysis(model=MODEL, system="", user_text="t", max_tokens=999_999, client=client)
    assert [c["max_tokens"] for c in client.stream_calls] == [65536, 128_000]


def test_chat_call_still_uses_non_streaming_create():
    seen = {}

    def create(**kwargs):
        seen.update(kwargs)
        return _message("hi")

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    assert tc.call_claude_text(model=MODEL, system="s", user_text="q", client=client).text == "hi"
    assert "cache_control" not in seen and seen["output_config"] == {"effort": "low"}


# --- effort ----------------------------------------------------------------------------------
@pytest.mark.parametrize("level", ["low", "medium", "high", "xhigh", "max"])
def test_effort_from_env(monkeypatch, level):
    monkeypatch.setenv("CLAUDE_EFFORT", level)
    client = _Client()
    tc.call_claude_analysis(model=MODEL, system="", user_text="t", client=client)
    assert client.stream_calls[0]["output_config"] == {"effort": level}


def test_bad_effort_fails_before_any_request(monkeypatch):
    monkeypatch.setenv("CLAUDE_EFFORT", "turbo")
    client = _Client()
    with pytest.raises(ValueError, match="CLAUDE_EFFORT"):
        tc.call_claude_analysis(model=MODEL, system="", user_text="t", client=client)
    assert not client.stream_calls and not client.count_calls


# --- long-prompt guard -----------------------------------------------------------------------
def test_prompt_over_limit_is_not_sent():
    client = _Client(prompt_tokens=100_001)
    with pytest.raises(tc.ClaudePromptTooLongError) as caught:
        tc.call_claude_analysis(model=MODEL, system="s", user_text="t", client=client)
    assert str(caught.value) == "prompt is 100,001 tokens, over the 100,000-token price tier"
    assert (caught.value.tokens, caught.value.limit) == (100_001, 100_000)
    assert not client.stream_calls
    assert client.count_calls[0]["model"] == MODEL


@pytest.mark.parametrize("tokens", [100_000, 5])
def test_prompt_at_or_under_limit_is_sent(tokens):
    client = _Client(prompt_tokens=tokens)
    tc.call_claude_analysis(model=MODEL, system="", user_text="t", client=client)
    assert len(client.stream_calls) == 1


def test_guard_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("CLAUDE_MAX_PROMPT_TOKENS", "0")
    client = _Client(prompt_tokens=900_000)
    tc.call_claude_analysis(model=MODEL, system="", user_text="t", client=client)
    assert not client.count_calls and len(client.stream_calls) == 1


def test_limit_comes_from_env(monkeypatch):
    monkeypatch.setenv("CLAUDE_MAX_PROMPT_TOKENS", "500")
    with pytest.raises(tc.ClaudePromptTooLongError):
        tc.call_claude_analysis(model=MODEL, system="", user_text="t", client=_Client(prompt_tokens=501))


def test_count_failure_fails_the_call_without_sending():
    client = _Client(count_error=ValueError("bad"))
    with pytest.raises(tc.ClaudeCountTokensError):
        tc.call_claude_analysis(model=MODEL, system="", user_text="t", client=client)
    assert not client.stream_calls


# --- outcomes --------------------------------------------------------------------------------
def test_refusal_raises():
    details = SimpleNamespace(category="cyber")
    client = _Client([_message("no", stop_reason="refusal", stop_details=details)])
    with pytest.raises(tc.ClaudeRefusalError) as caught:
        tc.call_claude_analysis(model=MODEL, system="", user_text="t", client=client)
    assert caught.value.category == "cyber"


def test_truncation_raises_with_usage():
    client = _Client([_message('{"cut', stop_reason="max_tokens", usage=_usage(out=777))])
    with pytest.raises(tc.ClaudeTruncatedError) as caught:
        tc.call_claude_analysis(model=MODEL, system="", user_text="t", max_tokens=1000, client=client)
    assert caught.value.usage.output_token_count == 777


def test_empty_text_raises():
    client = _Client([_message(blocks=[SimpleNamespace(type="thinking", thinking="only")])])
    with pytest.raises(RuntimeError, match="Empty response"):
        tc.call_claude_analysis(model=MODEL, system="", user_text="t", client=client)


def test_usage_fields_total_input_and_no_invented_thinking_split():
    usage = _usage(inp=100, out=50, cache_read=900, cache_write=0)
    client = _Client([_message(usage=usage)])
    row = tc.call_claude_analysis(model=MODEL, system="", user_text="t", client=client).usage
    assert row.input_token_count == 1000 and row.cached_input_token_count == 900
    assert row.output_token_count == 50 and row.thinking_token_count is None
    assert row.total_token_count == 1050


# --- the pipeline entry point: dispatch, key, retries, usage ---------------------------------
@pytest.fixture
def anthropic_stub(monkeypatch):
    holder: dict = {"client": _Client(), "init": []}

    def factory(**kwargs):
        holder["init"].append(kwargs)
        return holder["client"]

    monkeypatch.setattr(anthropic, "Anthropic", factory)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    rows: list[dict] = []
    monkeypatch.setattr(
        calls, "append_row", lambda prefix, row, when=None: rows.append(row) or None
    )
    holder["rows"] = rows
    return holder


def test_missing_key_fails_before_any_request(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(gtc, "Path", lambda *a, **k: SimpleNamespace(resolve=lambda: Path("/nonexistent/x/y/z/a/b/c")))
    monkeypatch.setattr(anthropic, "Anthropic", lambda **k: pytest.fail("client built without a key"))
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY not set"):
        gtc.call_gemini_text(api_key="", model=MODEL, user_text="t")


def test_success_is_recorded_as_anthropic(anthropic_stub):
    anthropic_stub["client"] = _Client([_message("ok", usage=_usage(inp=100, out=50, cache_read=900))])
    result = gtc.call_gemini_text(api_key="", model=MODEL, user_text="t", system_instruction=" sys ")
    assert result.text == "ok" and result.model == MODEL
    assert anthropic_stub["init"][0]["max_retries"] == 0
    assert anthropic_stub["client"].stream_calls[0]["system"] == "sys"
    row = anthropic_stub["rows"][0]
    assert row["provider"] == "anthropic" and row["model"] == MODEL and row["is_ok"] is True
    assert row["input_token_count"] == 1000 and row["cached_input_token_count"] == 900
    assert row["output_token_count"] == 50 and row["thinking_token_count"] is None
    assert row["attempt_count"] == 1
    assert "sk-test" not in json.dumps(row)


def test_logged_call_is_priced_with_cached_reads_at_the_cached_rate(anthropic_stub):
    anthropic_stub["client"] = _Client([_message("ok", usage=_usage(inp=100, out=50, cache_read=900))])
    gtc.call_gemini_text(api_key="", model=MODEL, user_text="t")
    row = anthropic_stub["rows"][0]
    prices = load_prices()
    cost = call_cost_usd(row, prices)
    # 100 plain input at 0.10, 900 cached at 0.01, 50 output at 0.50 (USD per 1M tokens)
    assert cost == pytest.approx((100 * 0.10 + 900 * 0.01 + 50 * 0.50) / 1_000_000)
    plain = dict(row, cached_input_token_count=0)
    assert call_cost_usd(plain, prices) > cost


@pytest.mark.parametrize("status_cls,status", [(anthropic.RateLimitError, 429), (anthropic.InternalServerError, 500)])
def test_retry_then_success(anthropic_stub, status_cls, status):
    err = _status_error(status_cls, status, {"retry-after": "1"} if status == 429 else None)
    anthropic_stub["client"] = _Client([err, _message("ok")])
    assert gtc.call_gemini_text(api_key="", model=MODEL, user_text="t").text == "ok"
    assert len(anthropic_stub["client"].stream_calls) == 2
    assert anthropic_stub["rows"][0]["attempt_count"] == 2


def test_retry_after_header_is_honoured():
    err = _status_error(anthropic.RateLimitError, 429, {"retry-after": "7"})
    assert gtc._claude_retry_delay(err, 0) == 7.0
    assert gtc._claude_retry_delay(_status_error(anthropic.InternalServerError, 500), 1) == 4.0


def test_gives_up_after_three_attempts(anthropic_stub):
    errs = [_status_error(anthropic.InternalServerError, 500) for _ in range(3)]
    anthropic_stub["client"] = _Client(errs)
    with pytest.raises(RuntimeError, match="Claude call failed"):
        gtc.call_gemini_text(api_key="", model=MODEL, user_text="t")
    assert len(anthropic_stub["client"].stream_calls) == 3
    row = anthropic_stub["rows"][0]
    assert row["is_ok"] is False and row["attempt_count"] == 3 and row["error_type"] == "InternalServerError"


def test_no_retry_on_400(anthropic_stub):
    anthropic_stub["client"] = _Client([_status_error(anthropic.BadRequestError, 400), _message("late")])
    with pytest.raises(RuntimeError, match="Claude call failed"):
        gtc.call_gemini_text(api_key="", model=MODEL, user_text="t")
    assert len(anthropic_stub["client"].stream_calls) == 1
    row = anthropic_stub["rows"][0]
    assert row["is_ok"] is False and row["provider"] == "anthropic" and row["attempt_count"] == 1


def test_too_long_prompt_is_recorded_as_failure_and_not_retried(anthropic_stub):
    anthropic_stub["client"] = _Client(prompt_tokens=150_000)
    with pytest.raises(tc.ClaudePromptTooLongError, match="over the 100,000-token price tier"):
        gtc.call_gemini_text(api_key="", model=MODEL, user_text="t")
    assert not anthropic_stub["client"].stream_calls
    row = anthropic_stub["rows"][0]
    assert row["is_ok"] is False and row["error_type"] == "ClaudePromptTooLongError"


def test_truncated_call_records_the_tokens_it_billed(anthropic_stub):
    anthropic_stub["client"] = _Client([_message("cut", stop_reason="max_tokens", usage=_usage(out=321))])
    with pytest.raises(tc.ClaudeTruncatedError):
        gtc.call_gemini_text(api_key="", model=MODEL, user_text="t")
    row = anthropic_stub["rows"][0]
    assert row["is_ok"] is False and row["output_token_count"] == 321


def test_pdf_bytes_are_rejected():
    with pytest.raises(ValueError, match="text-only"):
        gtc.call_gemini_text(api_key="", model=MODEL, user_text="t", pdf_bytes=b"%PDF")


def test_bad_effort_env_fails_before_client_is_built(monkeypatch):
    monkeypatch.setenv("CLAUDE_EFFORT", "nope")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.setattr(anthropic, "Anthropic", lambda **k: pytest.fail("client built"))
    with pytest.raises(ValueError, match="CLAUDE_EFFORT"):
        gtc.call_gemini_text(api_key="", model=MODEL, user_text="t")


# --- dispatch by model id --------------------------------------------------------------------
@pytest.mark.parametrize(
    ("model", "target"),
    [("claude-haiku-5-5", "_call_claude_text"), ("deepseek-flash", "_call_deepseek_text")],
)
def test_dispatch_by_model_id(monkeypatch, model, target):
    hit: list[str] = []
    for name in ("_call_claude_text", "_call_deepseek_text"):
        monkeypatch.setattr(gtc, name, lambda _n=name, **k: hit.append(_n) or "r")
    assert gtc.call_gemini_text(api_key="k", model=model, user_text="t") == "r"
    assert hit == [target]


def test_gemini_model_reaches_neither_claude_nor_deepseek(monkeypatch):
    monkeypatch.setattr(gtc, "_call_claude_text", lambda **k: pytest.fail("claude"))
    monkeypatch.setattr(gtc, "_call_deepseek_text", lambda **k: pytest.fail("deepseek"))
    monkeypatch.setitem(sys.modules, "google.genai", SimpleNamespace(types=SimpleNamespace(Part=None)))
    monkeypatch.setattr(gtc, "_key_pool", lambda key: (_ for _ in ()).throw(LookupError("gemini path")))
    with pytest.raises(LookupError, match="gemini path"):
        gtc.call_gemini_text(api_key="k", model="gemini-2.5-flash-lite", user_text="t")


# --- model selection -------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("model", "part_2", "expected"),
    [
        ("claude-haiku-5-5", "", True),
        ("claude-haiku-5-5", "claude-haiku-5-5", True),
        ("claude-haiku-5-5", "deepseek-flash", True),
        ("claude-haiku-5-5", "gemini-2.5-flash-lite", False),
        ("gemini-2.5-flash-lite", "claude-haiku-5-5", False),
        ("", "", False),
        ("", "claude-haiku-5-5", False),
    ],
)
def test_claude_needs_no_gemini_key(model, part_2, expected):
    assert mtp.uses_no_gemini_key(model, part_2) is expected


def test_light_stage_defaults_to_claude_haiku():
    from llm.gemini.tier_model_guard import DEFAULT_LIGHT_MODEL, light_model

    assert DEFAULT_LIGHT_MODEL == "claude-haiku-5-5"
    assert light_model({}, "gemini-2.5-flash-lite") == "claude-haiku-5-5"
    assert light_model({"LIGHT_MODEL": "deepseek-flash"}, "g") == "deepseek-flash"
    assert light_model({"LIGHT_MODEL": ""}, "g") == "g"
    script = Path(__file__).resolve().parents[3] / "packages/scrapers/scripts/youtube_run_priority_states_last_n.sh"
    text = script.read_text(encoding="utf-8")
    assert "LIGHT_MODEL-claude-haiku-5-5" in text
    # the full tier's stages do not pass a model of their own
    assert text.count("--model \"$light_model\"") == 1


def test_prompt_too_long_is_a_skip_in_both_loops():
    """A too-long prompt is logged as a skip and recorded as a failed event, ahead of the generic
    handler, in the analysis loop and in the report loop (the reason text reaches the event)."""
    source = Path(mtp.__file__).read_text(encoding="utf-8")
    assert source.count("except ClaudePromptTooLongError") == 2
    assert source.index("except ClaudePromptTooLongError") < source.index('logger.exception("Part 2 failed')
    assert source.rindex("except ClaudePromptTooLongError") < source.index('logger.exception("Failed {}')
