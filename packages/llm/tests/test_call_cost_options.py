"""Per-call cost settings: thinking budget, JSON mode, API version, prompt order (#263). No network."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("google.genai")

from llm.gemini import genai_text_client as gtc
from llm.gemini.browser_policy_analysis import DEFAULT_PROMPT_PART_1, VideoRow
from llm.gemini.meeting_transcript_policy import (
    _thinking_budget_arg,
    build_cacheable_part1_message,
    build_parser,
)


@pytest.fixture(autouse=True)
def _no_usage_log(monkeypatch):
    monkeypatch.setenv("LLM_USAGE_LOG", "0")


class _Models:
    """Records each request's config; fails the first call if told to."""

    def __init__(self, fail_first_with=None):
        self.configs, self.fail_first_with = [], fail_first_with

    def generate_content_stream(self, *, model, contents, config):
        self.configs.append(config)
        if self.fail_first_with is not None and len(self.configs) == 1:
            raise self.fail_first_with
        return iter([SimpleNamespace(text='{"ok": true}', usage_metadata=None)])


def _call(monkeypatch, models, **kwargs):
    monkeypatch.setattr(gtc, "_key_pool", lambda fallback: ["k"])
    monkeypatch.setattr(gtc, "_next_client", lambda pool: SimpleNamespace(models=models))
    return gtc.call_gemini_text(api_key="k", user_text="hi", **kwargs)


def test_supports_thinking_budget_only_for_25_flash():
    assert gtc.supports_thinking_budget("gemini-2.5-flash")
    assert gtc.supports_thinking_budget("gemini-2.5-flash-lite")
    assert gtc.supports_thinking_budget("gemini-2.5-flash-preview-05-20")
    for other in ("gemini-2.5-pro", "gemini-3.1-flash-lite-preview", "gemma-4-26b-a4b-it", "deepseek-chat", ""):
        assert not gtc.supports_thinking_budget(other)


def test_client_pins_v1beta(monkeypatch):
    monkeypatch.delenv("GENAI_API_VERSION", raising=False)
    assert gtc._genai_http_options().api_version == "v1beta"


def test_thinking_budget_and_json_mode_are_sent(monkeypatch):
    models = _Models()
    _call(monkeypatch, models, model="gemini-2.5-flash", thinking_budget=0, json_mode=True)
    (config,) = models.configs
    assert config.thinking_config.thinking_budget == 0
    assert config.response_mime_type == "application/json"


def test_defaults_send_neither(monkeypatch):
    models = _Models()
    _call(monkeypatch, models, model="gemini-2.5-flash")
    (config,) = models.configs
    assert config.thinking_config is None and config.response_mime_type is None


def test_thinking_budget_not_sent_to_a_model_that_does_not_take_one(monkeypatch):
    models = _Models()
    _call(monkeypatch, models, model="gemma-4-26b-a4b-it", thinking_budget=0)
    assert models.configs[0].thinking_config is None


@pytest.mark.parametrize(
    ("message", "dropped", "kept"),
    [
        ("400 INVALID_ARGUMENT. Thinking is not enabled for api version v1.", "thinking_config", "response_mime_type"),
        ("400 INVALID_ARGUMENT. JSON mode is not enabled for this model.", "response_mime_type", "thinking_config"),
    ],
)
def test_rejected_setting_is_dropped_and_the_call_retried(monkeypatch, message, dropped, kept):
    models = _Models(fail_first_with=ValueError(message))
    result = _call(monkeypatch, models, model="gemini-2.5-flash", thinking_budget=0, json_mode=True)
    assert result.text == '{"ok": true}'
    first, second = models.configs
    assert getattr(first, dropped) is not None and getattr(second, dropped) is None
    assert getattr(second, kept) is not None
    assert result.usage is None or result.usage.attempt_count == 2


def test_an_unrelated_400_is_not_retried(monkeypatch):
    models = _Models(fail_first_with=ValueError("400 INVALID_ARGUMENT. Request contains an invalid argument."))
    with pytest.raises(ValueError):
        _call(monkeypatch, models, model="gemini-2.5-flash", thinking_budget=0, json_mode=True)
    assert len(models.configs) == 1


# --------------------------------------------------------------------------- #
# Prompt order
# --------------------------------------------------------------------------- #
def _video(video_id: str, title: str) -> VideoRow:
    return VideoRow(video_id=video_id, video_url=f"https://www.youtube.com/watch?v={video_id}", title=title,
                    last_updated=None, event_date="2026-11-03", audio_file_path=None,
                    jurisdiction_id="municipality_0177256")  # fmt: skip


def test_two_videos_share_the_fixed_prompt_as_a_prefix():
    prompt = Path(DEFAULT_PROMPT_PART_1).read_text(encoding="utf-8")
    a = build_cacheable_part1_message(prompt, "[00:00:01] Mayor: call to order", _video("aaaaaaaaaaa", "Council A"))
    b = build_cacheable_part1_message(prompt, "[00:00:09] Clerk: roll call", _video("bbbbbbbbbbb", "Council B"))
    shared = next(i for i, (x, y) in enumerate(zip(a, b)) if x != y)
    fixed = prompt.strip()[: prompt.strip().lower().index("<transcript>")].rstrip()
    assert shared >= len(fixed) > 20_000  # the whole instruction block comes first, identical
    assert a.startswith(fixed)


def test_message_keeps_all_three_parts_in_order():
    msg = build_cacheable_part1_message(
        "RULES\n\n<transcript>\n[INSERT TRANSCRIPT HERE]\n</transcript>\n\nAFTER",
        "line one",
        _video("aaaaaaaaaaa", "Council A"),
        task_line="Use the transcript only.",
    )
    assert "[INSERT TRANSCRIPT HERE]" not in msg
    order = [msg.index(s) for s in ("RULES", "## MEDIA CONTEXT", "aaaaaaaaaaa", "Use the transcript only.",
                                    "<transcript>\nline one\n</transcript>", "AFTER")]  # fmt: skip
    assert order == sorted(order)
    assert msg.count("<transcript>") == 1


def test_prompt_without_a_slot_gets_the_transcript_appended():
    msg = build_cacheable_part1_message("RULES", "line one", _video("aaaaaaaaaaa", "Council A"))
    assert msg.startswith("RULES") and msg.endswith("<transcript>\nline one\n</transcript>")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_defaults_turn_thinking_off_and_json_mode_on(monkeypatch):
    monkeypatch.delenv("GEMINI_THINKING_BUDGET", raising=False)
    args = build_parser().parse_args(["--video-id", "x"])
    assert _thinking_budget_arg(args) == 0 and args.no_json_mode is False


def test_cli_can_restore_the_model_default_or_set_a_budget():
    assert _thinking_budget_arg(build_parser().parse_args(["--thinking-budget", "-1"])) is None
    assert _thinking_budget_arg(build_parser().parse_args(["--thinking-budget", "512"])) == 512
    assert build_parser().parse_args(["--no-json-mode"]).no_json_mode is True
    assert _thinking_budget_arg(SimpleNamespace()) == 0  # args built without the flag (older callers)
