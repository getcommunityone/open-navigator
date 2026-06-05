"""Tests for the AI Studio text client: key-pool sanitizing and retry give-up typing."""

import httpx
import pytest

from llm.gemini import genai_text_client as m
from llm.gemini.genai_text_client import (
    GenAIDailyQuotaGiveUp,
    GenAIModelUnavailableGiveUp,
    GenAIServerOverloadGiveUp,
    GenAITransientGiveUp,
    call_with_genai_quota_retry,
    is_genai_model_unavailable_error,
    is_genai_quota_error,
    is_genai_retryable,
    is_genai_server_overload_error,
    is_genai_transient_network_error,
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


# --- Half-open-connection timeout (the 37-minute-hang fix) -------------------


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ReadTimeout("timed out"),
        httpx.TimeoutException("timed out"),
        httpx.ConnectTimeout("timed out"),
        httpx.PoolTimeout("timed out"),
        httpx.WriteTimeout("timed out"),
    ],
)
def test_http_timeout_is_classified_retryable_transient(exc):
    # The half-open-connection fix: a per-request HTTP timeout must be treated like a
    # network disconnect — retryable AND transient — so it rides the transient retry
    # budget and ends in GenAITransientGiveUp, NOT server-overload or quota.
    assert is_genai_transient_network_error(exc)
    assert is_genai_retryable(exc)
    assert not is_genai_server_overload_error(exc)
    assert not is_genai_quota_error(exc)


def test_persistent_http_timeout_raises_transient_giveup(monkeypatch):
    monkeypatch.setattr(m.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setenv("GOVERNANCE_GENAI_NETWORK_RETRIES", "3")
    calls = {"n": 0}

    def _fn():
        # Simulate the SDK request hanging then firing its bounded timeout (instead of
        # the old silent 37-min wedge). Persists across every retry.
        calls["n"] += 1
        raise httpx.ReadTimeout("The read operation timed out")

    # A persistent timeout must end as GenAITransientGiveUp (shard skips-and-continues),
    # never an infinite hang, and never the server-overload/quota give-ups.
    with pytest.raises(GenAITransientGiveUp) as excinfo:
        call_with_genai_quota_retry(_fn, label="gemini-2.5-flash-lite", key_pool_size=2)
    assert not isinstance(excinfo.value, GenAIServerOverloadGiveUp)
    assert not isinstance(excinfo.value, GenAIDailyQuotaGiveUp)
    # It was actually retried (rotated keys) before giving up, not raised on first hit.
    assert calls["n"] == 3


def test_http_timeout_default_is_300_seconds(monkeypatch):
    # Default: 300s (5 min) — comfortably allows ~2-min large-transcript calls while
    # killing a true half-open hang. The SDK timeout is milliseconds, so seconds*1000.
    monkeypatch.delenv("GOVERNANCE_GENAI_HTTP_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("GOVERNANCE_GENAI_REQUEST_TIMEOUT_SECONDS", raising=False)
    assert m._DEFAULT_GENAI_REQUEST_TIMEOUT_SECONDS == 300
    assert m._genai_http_timeout_ms() == 300_000


def test_http_timeout_seconds_env_override(monkeypatch):
    monkeypatch.delenv("GOVERNANCE_GENAI_HTTP_TIMEOUT_MS", raising=False)
    monkeypatch.setenv("GOVERNANCE_GENAI_REQUEST_TIMEOUT_SECONDS", "45")
    assert m._genai_http_timeout_ms() == 45_000


def test_http_timeout_raw_ms_override_wins(monkeypatch):
    # The legacy raw-millisecond knob still takes precedence for operators who tuned it.
    monkeypatch.setenv("GOVERNANCE_GENAI_HTTP_TIMEOUT_MS", "90000")
    monkeypatch.setenv("GOVERNANCE_GENAI_REQUEST_TIMEOUT_SECONDS", "45")
    assert m._genai_http_timeout_ms() == 90_000


class _FakeClientError(Exception):
    """Stand-in for ``google.genai.errors.ClientError`` (carries an HTTP ``code``)."""

    def __init__(self, code: int, message: str):
        super().__init__(f"{code} {message}")
        self.code = code


def test_is_genai_model_unavailable_error_true_for_retired_model():
    # The live bug message: a retired model 404s with "no longer available".
    retired = _FakeClientError(
        404,
        "NOT_FOUND. This model models/gemini-2.0-flash-lite is no longer available.",
    )
    assert is_genai_model_unavailable_error(retired)
    # Plain-string variants (no .code attribute) must also be detected.
    assert is_genai_model_unavailable_error(
        RuntimeError("404 NOT_FOUND: model gemini-foo is not found")
    )
    assert is_genai_model_unavailable_error(
        RuntimeError("404 models/gemini-bar was not found or is not supported")
    )


def test_is_genai_model_unavailable_error_false_for_unrelated_errors():
    # An unrelated 404 (not about the model) must NOT be swallowed.
    assert not is_genai_model_unavailable_error(
        _FakeClientError(404, "NOT_FOUND: requested file does not exist")
    )
    # Other error families are not model-unavailable.
    assert not is_genai_model_unavailable_error(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert not is_genai_model_unavailable_error(RuntimeError("503 UNAVAILABLE"))
    assert not is_genai_model_unavailable_error(RuntimeError("500 INTERNAL"))


def test_model_unavailable_giveup_raises_distinct_subtype(monkeypatch):
    monkeypatch.setattr(m.time, "sleep", lambda *_a, **_k: None)

    def _fn():
        raise _FakeClientError(
            404,
            "NOT_FOUND. This model models/gemini-2.0-flash-lite is no longer available.",
        )

    # A retired-model 404 must surface as the typed give-up — NOT the raw ClientError,
    # which would crash a model-cycling driver. It is NOT retried (a dead model can't
    # recover on a fresh attempt) and is distinct from the quota/overload give-ups.
    with pytest.raises(GenAIModelUnavailableGiveUp) as excinfo:
        call_with_genai_quota_retry(_fn, label="gemini-2.0-flash-lite", key_pool_size=3)
    assert not isinstance(excinfo.value, _FakeClientError)
    assert not isinstance(excinfo.value, GenAIDailyQuotaGiveUp)
    assert not isinstance(excinfo.value, GenAIServerOverloadGiveUp)
    assert issubclass(GenAIModelUnavailableGiveUp, RuntimeError)


# --- Hard wall-clock guard (37-min-hang backstop) ---------------------------
def test_wallclock_default_is_httpx_timeout_plus_buffer(monkeypatch):
    import llm.gemini.genai_text_client as g
    monkeypatch.delenv("GOVERNANCE_GENAI_WALLCLOCK_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("GOVERNANCE_GENAI_HTTP_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("GOVERNANCE_GENAI_REQUEST_TIMEOUT_SECONDS", raising=False)
    # default httpx 300s + 30s buffer
    assert g._genai_wallclock_timeout_seconds() == 330.0
    monkeypatch.setenv("GOVERNANCE_GENAI_WALLCLOCK_TIMEOUT_SECONDS", "12")
    assert g._genai_wallclock_timeout_seconds() == 12.0


def test_hung_call_becomes_transient_giveup_not_infinite_hang(monkeypatch):
    import time
    from llm.gemini.genai_text_client import (
        call_with_genai_quota_retry,
        GenAITransientGiveUp,
    )
    monkeypatch.setenv("GOVERNANCE_GENAI_WALLCLOCK_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("GOVERNANCE_GENAI_NETWORK_RETRIES", "2")

    def hung():
        time.sleep(30)  # far beyond the 1s wall-clock cap

    with pytest.raises(GenAITransientGiveUp):
        call_with_genai_quota_retry(hung, label="test", key_pool_size=1)


def test_wallclock_passes_through_result_and_worker_exception(monkeypatch):
    from llm.gemini.genai_text_client import call_with_genai_quota_retry
    monkeypatch.setenv("GOVERNANCE_GENAI_WALLCLOCK_TIMEOUT_SECONDS", "5")
    assert call_with_genai_quota_retry(lambda: "ok", label="t") == "ok"

    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        call_with_genai_quota_retry(
            lambda: (_ for _ in ()).throw(Boom("x")), label="t"
        )
