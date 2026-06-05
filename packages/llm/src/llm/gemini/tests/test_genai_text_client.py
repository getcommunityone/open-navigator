"""Tests for the AI Studio text client: key-pool sanitizing and retry give-up typing."""

import pytest

from llm.gemini import genai_text_client as m
from llm.gemini.genai_text_client import (
    GenAIDailyQuotaGiveUp,
    GenAIServerOverloadGiveUp,
    GenAITransientGiveUp,
    call_with_genai_quota_retry,
    is_genai_quota_error,
    is_genai_server_overload_error,
    resolve_gemini_api_keys,
)

_KEY_ENV_VARS = (
    ["GEMINI_API_KEYS", "GEMINI_API_KEY", "GOOGLE_API_KEY"]
    + [f"GEMINI_API_KEY_{i}" for i in range(1, 11)]
)


@pytest.fixture
def clean_key_env(monkeypatch):
    """Strip every Gemini key env var so tests see only what they set."""
    for var in _KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_resolve_gemini_api_keys_keeps_all_key_formats(clean_key_env):
    # Regression: "AQ.…" strings are a valid Gemini API key format (verified live
    # that they authenticate via x-goog-api-key, HTTP 200) — NOT OAuth tokens. An
    # earlier version wrongly dropped every non-"AIza" key and silently emptied the
    # pool. resolve_gemini_api_keys must keep keys of any format, only de-duplicating.
    # env_path points nowhere so the real .env is not loaded.
    clean_key_env.setenv("GEMINI_API_KEYS", "AIzaClassic, AQ.NewFormatKey")
    clean_key_env.setenv("GEMINI_API_KEY", "AIzaSingle")

    keys = resolve_gemini_api_keys(env_path="/nonexistent/.env")

    assert keys == ["AIzaClassic", "AQ.NewFormatKey", "AIzaSingle"]


def test_resolve_gemini_api_keys_dedupes_and_preserves_order(clean_key_env):
    clean_key_env.setenv("GEMINI_API_KEYS", "AIzaA AIzaB AIzaA")
    clean_key_env.setenv("GEMINI_API_KEY", "AIzaB")

    assert resolve_gemini_api_keys(env_path="/nonexistent/.env") == ["AIzaA", "AIzaB"]


def test_transient_network_giveup_raises_distinct_subtype(monkeypatch):
    monkeypatch.setattr(m.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setenv("GOVERNANCE_GENAI_NETWORK_RETRIES", "2")

    def _fn():
        raise RuntimeError("Server disconnected without sending a response.")

    # Transient infra give-ups raise the dedicated type so batch callers skip-and-continue,
    # while remaining a RuntimeError so existing `except RuntimeError` handlers still catch it.
    with pytest.raises(GenAITransientGiveUp):
        call_with_genai_quota_retry(_fn, label="test", key_pool_size=1)
    assert issubclass(GenAITransientGiveUp, RuntimeError)


def test_quota_giveup_raises_plain_runtimeerror(monkeypatch):
    monkeypatch.setattr(m.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setenv("GOVERNANCE_GENAI_QUOTA_RETRIES", "2")

    def _fn():
        raise RuntimeError("RESOURCE_EXHAUSTED: 429 quota exceeded")

    # Real quota/server give-ups stay RuntimeError (NOT the transient subtype),
    # so --stop-on-error still halts on them.
    with pytest.raises(RuntimeError) as excinfo:
        call_with_genai_quota_retry(_fn, label="test", key_pool_size=1)
    assert not isinstance(excinfo.value, GenAITransientGiveUp)


def test_daily_quota_giveup_raises_distinct_subtype(monkeypatch):
    monkeypatch.setattr(m.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setenv("GOVERNANCE_GENAI_QUOTA_RETRIES", "2")

    def _fn():
        raise RuntimeError("RESOURCE_EXHAUSTED: 429 quota exceeded")

    # Pool-wide quota/429 give-ups raise the dedicated daily-quota type so a
    # model-cycling driver can rotate models, while remaining a RuntimeError so
    # existing `except RuntimeError`/`except Exception` handlers still catch it.
    with pytest.raises(GenAIDailyQuotaGiveUp):
        call_with_genai_quota_retry(_fn, label="test", key_pool_size=1)
    assert issubclass(GenAIDailyQuotaGiveUp, RuntimeError)


def test_server_overload_giveup_raises_distinct_subtype(monkeypatch):
    monkeypatch.setattr(m.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setenv("GOVERNANCE_GENAI_QUOTA_RETRIES", "2")

    def _fn():
        raise RuntimeError("503 UNAVAILABLE: service overloaded")

    # A sustained server-overload give-up (503/502/504) raises its own type so a
    # model-cycling driver can temporarily rotate off the congested model — but it is
    # NOT the daily-quota subtype (a 503 overload is not a daily wall).
    with pytest.raises(GenAIServerOverloadGiveUp) as excinfo:
        call_with_genai_quota_retry(_fn, label="test", key_pool_size=1)
    assert not isinstance(excinfo.value, GenAIDailyQuotaGiveUp)
    assert issubclass(GenAIServerOverloadGiveUp, RuntimeError)


def test_504_deadline_giveup_is_server_overload(monkeypatch):
    monkeypatch.setattr(m.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setenv("GOVERNANCE_GENAI_QUOTA_RETRIES", "2")

    def _fn():
        raise RuntimeError("504 DEADLINE_EXCEEDED")

    # The live bug: a sustained 504 DEADLINE_EXCEEDED used to give up as a plain
    # RuntimeError, so the driver never moved off the congested model. It must now be
    # the server-overload subtype.
    with pytest.raises(GenAIServerOverloadGiveUp):
        call_with_genai_quota_retry(_fn, label="test", key_pool_size=1)


def test_overload_classifier_excludes_quota():
    # Predicate boundaries: quota (429/RESOURCE_EXHAUSTED) is NOT server-overload, and
    # vice-versa, so the give-up branch routes each to the right type.
    assert is_genai_server_overload_error(RuntimeError("503 UNAVAILABLE"))
    assert is_genai_server_overload_error(RuntimeError("504 DEADLINE_EXCEEDED"))
    assert is_genai_server_overload_error(RuntimeError("502 BAD_GATEWAY"))
    assert not is_genai_server_overload_error(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert is_genai_quota_error(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert not is_genai_quota_error(RuntimeError("503 UNAVAILABLE"))
