"""Usage rows for the governance pipeline's direct Gemini calls (#268). No network."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from llm.governance import genai_quota_retry as gqr
from llm.usage import calls, load_bronze


@pytest.fixture()
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_USAGE_LOG_DIR", str(tmp_path))
    monkeypatch.delenv("LLM_USAGE_LOG", raising=False)
    monkeypatch.setattr(gqr.time, "sleep", lambda s: None)
    return tmp_path


def _response(prompt=100, out=20, thoughts=None):
    return SimpleNamespace(usage_metadata=SimpleNamespace(
        prompt_token_count=prompt, cached_content_token_count=None, candidates_token_count=out,
        thoughts_token_count=thoughts, total_token_count=prompt + out))  # fmt: skip


def _rows(log_dir):
    return list(load_bronze.read_rows(log_dir, "llm_calls"))


def test_no_model_means_no_row(log_dir):
    assert gqr.call_with_genai_quota_retry(lambda: "x", label="t") == "x"
    assert _rows(log_dir) == []


def test_a_call_with_retries_writes_one_row(log_dir):
    outcomes = iter([RuntimeError("429 RESOURCE_EXHAUSTED"), _response(thoughts=7)])

    def fn():
        value = next(outcomes)
        if isinstance(value, Exception):
            raise value
        return value

    gqr.call_with_genai_quota_retry(fn, label="gatekeeper m", model="gemma-4-31b-it", stage="gatekeeper")
    (row,) = _rows(log_dir)
    assert row["model"] == "gemma-4-31b-it" and row["stage"] == "gatekeeper"
    assert row["input_token_count"] == 100 and row["thinking_token_count"] == 7
    assert row["attempt_count"] == 2 and row["is_ok"] is True


def test_a_streamed_answer_uses_its_last_chunk(log_dir):
    streamed = SimpleNamespace(text="hi", last_chunk=_response(prompt=55))
    gqr.call_with_genai_quota_retry(lambda: streamed, label="genai m", model="m", stage="governance")
    assert _rows(log_dir)[0]["input_token_count"] == 55


def test_the_demo_stage_wins_over_the_default(log_dir):
    with calls.llm_call_context(stage="demo3"):
        gqr.call_with_genai_quota_retry(_response, label="genai m", model="m", stage="governance")
    assert _rows(log_dir)[0]["stage"] == "demo3"


def test_a_failed_call_is_recorded_and_raised(log_dir):
    def fn():
        raise ValueError("400 INVALID_ARGUMENT")

    with pytest.raises(ValueError):
        gqr.call_with_genai_quota_retry(fn, label="shield m", model="m", stage="shield")
    (row,) = _rows(log_dir)
    assert row["is_ok"] is False and row["error_type"] == "ValueError" and row["attempt_count"] == 1


def test_demo_runners_label_their_calls(monkeypatch):
    from llm.governance import colab_demos

    seen = []
    monkeypatch.setattr(calls, "record_llm_call", lambda **kw: seen.append(calls.current_context()))
    wrapped = colab_demos._usage_stage("demo2")(lambda: calls.current_context())
    assert wrapped() == {"stage": "demo2"}
    assert colab_demos.run_demo1.__name__ == "run_demo1"  # functools.wraps kept the name


def test_labels_reach_a_call_run_in_a_worker_thread(log_dir):
    # Demo 3 runs its call through call_with_wall_clock_timeout (a worker thread).
    def call():
        return gqr.call_with_genai_quota_retry(_response, label="genai m", model="m", stage="governance")

    with calls.llm_call_context(stage="demo3", video_id="vid"):
        gqr.call_with_wall_clock_timeout(call, timeout_seconds=5)
    (row,) = _rows(log_dir)
    assert row["stage"] == "demo3" and row["video_id"] == "vid"
