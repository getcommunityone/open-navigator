"""#866: DeepSeek calls send thinking off unless DEEPSEEK_THINKING asks for it. The client is stubbed; no network."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from llm.gemini import genai_text_client as client_mod
from llm.gemini.genai_text_client import DEEPSEEK_THINKING_LEVELS, deepseek_thinking_kwargs


@pytest.mark.parametrize("setting", [None, "", "  ", "off", "OFF", " Off "])
def test_off_is_the_default_and_disables_thinking(setting):
    assert deepseek_thinking_kwargs(setting) == {"extra_body": {"thinking": {"type": "disabled"}}}


@pytest.mark.parametrize("level", ["low", "high", "max"])
def test_a_level_turns_thinking_on_at_that_effort(level):
    assert deepseek_thinking_kwargs(level.upper()) == {
        "extra_body": {"thinking": {"type": "enabled"}},
        "reasoning_effort": level,
    }


@pytest.mark.parametrize("bad", ["on", "true", "medium", "none", "0"])
def test_an_unknown_value_is_rejected_with_the_allowed_values(bad):
    with pytest.raises(ValueError) as err:
        deepseek_thinking_kwargs(bad)
    assert all(level in str(err.value) for level in DEEPSEEK_THINKING_LEVELS)


class _Completions:
    def __init__(self):
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        message = SimpleNamespace(content='{"ok": true}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=usage)


@pytest.fixture()
def fake_openai(monkeypatch):
    completions = _Completions()

    class OpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=completions)

    real = sys.modules.get("openai")
    fake = types.ModuleType("openai")
    fake.OpenAI = OpenAI
    for name in dir(real) if real else ():
        if name.endswith("Error") and not hasattr(fake, name):
            setattr(fake, name, getattr(real, name))
    monkeypatch.setitem(sys.modules, "openai", fake)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setattr(client_mod, "_record_usage", lambda **_k: None)
    return completions


def test_the_request_carries_thinking_off_by_default(fake_openai, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_THINKING", raising=False)
    client_mod._call_deepseek_text(model="deepseek-flash", user_text="hello")
    sent = fake_openai.calls[0]
    assert sent["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in sent
    assert sent["model"] == "deepseek-flash" and sent["max_tokens"] == 65536


def test_the_setting_turns_it_on(fake_openai, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_THINKING", "low")
    client_mod._call_deepseek_text(model="deepseek-flash", user_text="hello")
    sent = fake_openai.calls[0]
    assert sent["extra_body"] == {"thinking": {"type": "enabled"}} and sent["reasoning_effort"] == "low"


def test_a_bad_setting_fails_before_any_request(fake_openai, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_THINKING", "medium")
    with pytest.raises(ValueError):
        client_mod._call_deepseek_text(model="deepseek-flash", user_text="hello")
    assert fake_openai.calls == []
