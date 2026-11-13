"""Usage records for model calls and GPU steps (#262). No network, no GPU, no database."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm.usage import calls, gpu, load_bronze, prices, report


@pytest.fixture()
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_USAGE_LOG_DIR", str(tmp_path))
    monkeypatch.delenv("LLM_USAGE_LOG", raising=False)
    return tmp_path


def _rows(log_dir: Path, prefix: str) -> list[dict]:
    return list(load_bronze.read_rows(log_dir, prefix))


# --------------------------------------------------------------------------- #
# Token counts
# --------------------------------------------------------------------------- #
def test_usage_from_genai_sdk_object():
    raw = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=1200,
            cached_content_token_count=800,
            candidates_token_count=300,
            thoughts_token_count=450,
            total_token_count=1950,
        )
    )
    usage = calls.usage_from_genai_response(raw)
    assert usage.input_token_count == 1200
    assert usage.cached_input_token_count == 800
    assert usage.output_token_count == 300
    assert usage.thinking_token_count == 450
    assert usage.total_token_count == 1950


def test_usage_from_batch_result_json_is_camel_case():
    raw = {"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4, "totalTokenCount": 14}}
    usage = calls.usage_from_genai_response(raw)
    assert (usage.input_token_count, usage.output_token_count, usage.total_token_count) == (10, 4, 14)
    assert usage.thinking_token_count is None


def test_missing_usage_is_none_not_zero():
    usage = calls.usage_from_genai_response(SimpleNamespace(usage_metadata=None))
    assert usage.as_dict() == {k: None for k in usage.as_dict()}
    assert calls.usage_from_genai_response(None).input_token_count is None


def test_openai_reasoning_tokens_are_split_from_output():
    raw = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=70,
            total_tokens=170,
            prompt_cache_hit_tokens=40,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=50),
        )
    )
    usage = calls.usage_from_openai_response(raw)
    assert usage.output_token_count == 20
    assert usage.thinking_token_count == 50
    assert usage.cached_input_token_count == 40


# --------------------------------------------------------------------------- #
# The call log
# --------------------------------------------------------------------------- #
def test_record_llm_call_writes_one_row_with_context(log_dir):
    usage = calls.LLMCallUsage(input_token_count=5, output_token_count=2, latency_seconds=1.23456, attempt_count=3)
    with calls.llm_call_context(stage="part1", video_id="abc", jurisdiction_id="m_1", transcript="SECRET"):
        calls.record_llm_call(provider="gemini", model="gemini-2.5-flash", usage=usage, is_ok=True)
    (row,) = _rows(log_dir, "llm_calls")
    assert row["stage"] == "part1" and row["video_id"] == "abc" and row["jurisdiction_id"] == "m_1"
    assert row["api_mode"] == "interactive"
    assert row["input_token_count"] == 5 and row["attempt_count"] == 3
    assert row["latency_seconds"] == 1.235
    assert row["is_ok"] is True and row["error_type"] is None
    assert "SECRET" not in json.dumps(row)  # only the known labels are kept


def test_context_is_restored_after_the_block(log_dir):
    with calls.llm_call_context(stage="part1"):
        with calls.llm_call_context(stage="part2", video_id="v"):
            assert calls.current_context() == {"stage": "part2", "video_id": "v"}
        assert calls.current_context() == {"stage": "part1"}
    assert calls.current_context() == {}


def test_failed_call_is_recorded(log_dir):
    calls.record_llm_call(provider="gemini", model="m", usage=None, is_ok=False, error_type="GenAITransientGiveUp")
    (row,) = _rows(log_dir, "llm_calls")
    assert row["is_ok"] is False and row["error_type"] == "GenAITransientGiveUp"
    assert row["input_token_count"] is None


def test_switch_off(log_dir, monkeypatch):
    monkeypatch.setenv("LLM_USAGE_LOG", "0")
    calls.record_llm_call(provider="gemini", model="m", usage=None, is_ok=True)
    assert _rows(log_dir, "llm_calls") == []


def test_unwritable_log_dir_does_not_raise(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("LLM_USAGE_LOG_DIR", str(blocker / "under_a_file"))
    calls.record_llm_call(provider="gemini", model="m", usage=None, is_ok=True)


# --------------------------------------------------------------------------- #
# call_gemini_text records every call
# --------------------------------------------------------------------------- #
class _FakeModels:
    def __init__(self, chunks=None, error=None):
        self.chunks, self.error, self.calls = chunks or [], error, 0

    def generate_content_stream(self, **_):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return iter(self.chunks)


def _patch_client(monkeypatch, models):
    from llm.gemini import genai_text_client as gtc

    monkeypatch.setattr(gtc, "_key_pool", lambda fallback: ["k"])
    monkeypatch.setattr(gtc, "_next_client", lambda pool: SimpleNamespace(models=models))
    return gtc


def test_call_gemini_text_returns_and_logs_usage(log_dir, monkeypatch):
    pytest.importorskip("google.genai")
    meta = SimpleNamespace(prompt_token_count=9, cached_content_token_count=None, candidates_token_count=3,
                           thoughts_token_count=7, total_token_count=19)  # fmt: skip
    models = _FakeModels(chunks=[SimpleNamespace(text="he", usage_metadata=None),
                                 SimpleNamespace(text="llo", usage_metadata=meta)])  # fmt: skip
    gtc = _patch_client(monkeypatch, models)
    with calls.llm_call_context(stage="part1", video_id="vid"):
        result = gtc.call_gemini_text(api_key="k", model="gemini-2.5-flash", user_text="hi")
    assert result.text == "hello"
    assert result.usage.thinking_token_count == 7 and result.usage.attempt_count == 1
    assert result.usage.latency_seconds is not None
    (row,) = _rows(log_dir, "llm_calls")
    assert row["provider"] == "gemini" and row["model"] == "gemini-2.5-flash"
    assert (row["input_token_count"], row["output_token_count"], row["thinking_token_count"]) == (9, 3, 7)
    assert row["video_id"] == "vid" and row["is_ok"] is True


def test_call_gemini_text_logs_a_failed_call(log_dir, monkeypatch):
    pytest.importorskip("google.genai")
    gtc = _patch_client(monkeypatch, _FakeModels(error=ValueError("400 INVALID_ARGUMENT bad request")))
    with pytest.raises(ValueError):
        gtc.call_gemini_text(api_key="k", model="gemini-2.5-flash", user_text="hi")
    (row,) = _rows(log_dir, "llm_calls")
    assert row["is_ok"] is False and row["error_type"] == "ValueError" and row["attempt_count"] == 1


def test_retry_attempts_are_counted(monkeypatch):
    from llm.gemini import genai_text_client as gtc

    monkeypatch.setattr(gtc.time, "sleep", lambda s: None)
    outcomes = iter([RuntimeError("503 UNAVAILABLE"), RuntimeError("503 UNAVAILABLE"), "done"])

    def fn():
        value = next(outcomes)
        if isinstance(value, Exception):
            raise value
        return value

    stats: dict = {}
    assert gtc.call_with_genai_quota_retry(fn, label="t", stats=stats) == "done"
    assert stats["attempts"] == 3


# --------------------------------------------------------------------------- #
# GPU steps
# --------------------------------------------------------------------------- #
def _stamp(unix: float) -> str:
    return datetime.fromtimestamp(unix).strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]


def test_gpu_stats_from_samples(tmp_path):
    start = datetime(2026, 11, 13, 12, 0, 0).timestamp()
    samples = tmp_path / "s.csv"
    lines = [gpu.SAMPLE_HEADER]
    lines.append(f"{_stamp(start - 60)}, 0, 99, 9999, 300.0")  # before the step: ignored
    for i, (util, mem, watts) in enumerate([(50, 4000, 60.0), (100, 9000, 80.0)]):
        lines.append(f"{_stamp(start + 5 + i * 5)}, 0, {util}, {mem}, {watts}")
        lines.append(f"{_stamp(start + 5 + i * 5)}, 1, 0, 100, [N/A]")  # a GPU with no power reading
    lines.append("2026/11/13 12:00:2")  # a cut-off last line
    samples.write_text("\n".join(lines) + "\n")
    stats = gpu.gpu_stats(samples, start, start + 3600)
    assert stats["gpu_sample_count"] == 4
    assert stats["avg_gpu_utilization_pct"] == 37.5
    assert stats["max_gpu_memory_used_mb"] == 9000
    assert stats["energy_wh"] == 70.0  # GPU 0's mean 70 W over one hour; GPU 1 reported none


def test_gpu_stats_none_without_samples(tmp_path):
    assert gpu.gpu_stats(tmp_path / "missing.csv", 0, 1) is None
    empty = tmp_path / "e.csv"
    empty.write_text(gpu.SAMPLE_HEADER + "\n")
    assert gpu.gpu_stats(empty, 0, 1) is None


def test_gpu_run_is_a_no_op_without_a_gpu(log_dir, monkeypatch):
    monkeypatch.setattr(gpu, "gpu_names", lambda: [])
    with gpu.gpu_run("whisperx_diarization", video_id="v"):
        pass
    assert _rows(log_dir, "gpu_runs") == []


def test_gpu_run_skips_cpu_device_without_asking(log_dir, monkeypatch):
    monkeypatch.setattr(gpu, "gpu_names", lambda: pytest.fail("nvidia-smi must not be asked for a CPU step"))
    with gpu.gpu_run("whisperx_diarization", device="cpu"):
        pass


def test_gpu_run_writes_a_row_even_when_the_step_fails(log_dir, monkeypatch):
    monkeypatch.setattr(gpu, "gpu_names", lambda: ["Tesla T4", "Tesla T4"])
    monkeypatch.setattr(gpu, "start_gpu_sampler", lambda path, interval_ms=5000: None)
    monkeypatch.setattr(gpu, "stop_gpu_sampler", lambda sampler: None)
    with pytest.raises(RuntimeError):
        with gpu.gpu_run("whisperx_diarization", video_id="v", jurisdiction_id="j"):
            raise RuntimeError("out of memory")
    (row,) = _rows(log_dir, "gpu_runs")
    assert row["step_name"] == "whisperx_diarization" and row["video_id"] == "v"
    assert row["gpu_count"] == 2 and row["gpu_name"] == "Tesla T4"
    assert row["gpu_hours"] == pytest.approx(row["wall_seconds"] / 3600 * 2, abs=1e-4)
    assert row["avg_gpu_utilization_pct"] is None  # no samples: not guessed


# --------------------------------------------------------------------------- #
# Prices: a cost only from a sourced, dated price
# --------------------------------------------------------------------------- #
PRICED = {
    "models": {
        "gemini-2.5-flash": {
            "source": "https://example.test/pricing",
            "read_date": "2026-11-13",
            "interactive": {"input_usd_per_1m": 1.0, "cached_input_usd_per_1m": 0.1, "output_usd_per_1m": 10.0},
            "batch": {"input_usd_per_1m": 0.5, "cached_input_usd_per_1m": None, "output_usd_per_1m": 5.0},
        },
        "unsourced": {"source": None, "read_date": None, "interactive": {"input_usd_per_1m": 1.0, "output_usd_per_1m": 1.0}},
    },
    "gpus": {"T4": {"usd_per_gpu_hour": 0.5, "source": "https://example.test/t4", "read_date": "2026-11-04"},
             "L4": {"usd_per_gpu_hour": 0.8, "source": None, "read_date": None}},
}  # fmt: skip


def test_call_cost_uses_each_rate():
    row = {"model": "gemini-2.5-flash", "api_mode": "interactive", "input_token_count": 1_000_000,
           "cached_input_token_count": 400_000, "output_token_count": 100_000, "thinking_token_count": 200_000}  # fmt: skip
    # 600k uncached at $1 + 400k cached at $0.10 + 300k output and thinking at $10
    assert prices.call_cost_usd(row, PRICED) == pytest.approx(0.6 + 0.04 + 3.0)
    assert prices.call_cost_usd({**row, "api_mode": "batch", "cached_input_token_count": None}, PRICED) == pytest.approx(0.5 + 1.5)


def test_call_cost_is_none_without_a_usable_price():
    row = {"model": "gemini-2.5-flash", "api_mode": "interactive", "input_token_count": 10, "output_token_count": 5}
    assert prices.call_cost_usd({**row, "model": "unsourced"}, PRICED) is None
    assert prices.call_cost_usd({**row, "model": "never-heard-of-it"}, PRICED) is None
    assert prices.call_cost_usd({**row, "input_token_count": None}, PRICED) is None
    # cached tokens were used but the batch entry has no cached rate
    assert prices.call_cost_usd({**row, "api_mode": "batch", "cached_input_token_count": 3}, PRICED) is None


def test_model_variant_takes_the_longest_matching_entry():
    both = {"models": {**PRICED["models"], "gemini-2.5-flash-lite": {
        "source": "s", "read_date": "d", "interactive": {"input_usd_per_1m": 0.2, "output_usd_per_1m": 0.4}}}}  # fmt: skip
    assert prices.model_price("gemini-2.5-flash-lite-preview-09", "interactive", both)["input_usd_per_1m"] == 0.2
    assert prices.model_price("gemini-2.5-flash-preview-05-20", "interactive", both)["input_usd_per_1m"] == 1.0


def test_gpu_cost():
    assert prices.gpu_cost_usd({"gpu_name": "Tesla T4", "gpu_hours": 2.0}, PRICED) == 1.0
    assert prices.gpu_cost_usd({"gpu_name": "NVIDIA L4", "gpu_hours": 2.0}, PRICED) is None  # unsourced
    assert prices.gpu_cost_usd({"gpu_name": "NVIDIA H100", "gpu_hours": 2.0}, PRICED) is None


def test_shipped_prices_file_has_no_unsourced_price():
    shipped = prices.load_prices()
    assert shipped["models"] and shipped["gpus"]
    for name, entry in shipped["models"].items():
        rates = [v for mode in ("interactive", "batch") for v in (entry.get(mode) or {}).values()]
        if any(v is not None for v in rates):
            assert entry.get("source") and entry.get("read_date"), f"{name} has a price with no source or date"
    for name, entry in shipped["gpus"].items():
        if entry.get("usd_per_gpu_hour") is not None:
            assert entry.get("source") and entry.get("read_date"), f"{name} has a price with no source or date"


# --------------------------------------------------------------------------- #
# Report and loader
# --------------------------------------------------------------------------- #
def _call(day, model, **over):
    return {"llm_call_id": f"{day}-{model}-{len(over)}", "called_at": f"{day}T10:00:00+00:00", "model": model,
            "api_mode": "interactive", "is_ok": True, "attempt_count": 1, "input_token_count": 1_000_000,
            "cached_input_token_count": None, "output_token_count": 100_000, "thinking_token_count": None,
            "total_token_count": 1_100_000, "latency_seconds": 10.0, **over}  # fmt: skip


def test_summarize_calls_groups_and_prices():
    rows = [
        _call("2026-11-12", "gemini-2.5-flash"),
        _call("2026-11-12", "gemini-2.5-flash", latency_seconds=30.0, attempt_count=4),
        _call("2026-11-12", "gemini-2.5-flash", is_ok=False, input_token_count=None, output_token_count=None,
              total_token_count=None, error_type="GenAITransientGiveUp"),  # fmt: skip
        _call("2026-11-13", "unsourced"),
        _call("2026-11-01", "gemini-2.5-flash"),
    ]
    out = report.summarize_calls(rows, PRICED, since="2026-11-10")
    assert [(r["day"], r["model"]) for r in out] == [("2026-11-12", "gemini-2.5-flash"), ("2026-11-13", "unsourced")]
    flash, unsourced = out
    assert flash["call_count"] == 3 and flash["failed_call_count"] == 1 and flash["retried_call_count"] == 1
    assert flash["input_token_count"] == 2_000_000 and flash["thinking_token_count"] is None
    assert flash["avg_latency_seconds"] == pytest.approx(16.67) and flash["max_latency_seconds"] == 30.0
    assert flash["cost_usd"] == pytest.approx(2 * (1.0 + 1.0))
    assert unsourced["cost_usd"] is None


def test_summarize_calls_by_stage():
    rows = [_call("2026-11-12", "gemini-2.5-flash", stage="part1"), _call("2026-11-12", "gemini-2.5-flash", stage="part2")]
    out = report.summarize_calls(rows, PRICED, extra_keys=["stage"])
    assert [r["stage"] for r in out] == ["part1", "part2"]


def test_summarize_gpu_weights_utilization_by_time():
    rows = [
        {"started_at": "2026-11-12T01:00:00+00:00", "step_name": "whisperx_diarization", "gpu_name": "Tesla T4",
         "wall_seconds": 3000.0, "gpu_hours": 0.8333, "avg_gpu_utilization_pct": 90.0,
         "max_gpu_memory_used_mb": 9000.0, "energy_wh": 50.0},
        {"started_at": "2026-11-12T03:00:00+00:00", "step_name": "whisperx_diarization", "gpu_name": "Tesla T4",
         "wall_seconds": 1000.0, "gpu_hours": 0.2778, "avg_gpu_utilization_pct": 10.0,
         "max_gpu_memory_used_mb": 4000.0, "energy_wh": None},
    ]  # fmt: skip
    (out,) = report.summarize_gpu(rows, PRICED)
    assert out["run_count"] == 2 and out["gpu_hours"] == pytest.approx(1.1111)
    assert out["avg_gpu_utilization_pct"] == 70.0
    assert out["max_gpu_memory_used_mb"] == 9000.0 and out["energy_wh"] == 50.0
    assert out["estimated_cost_usd"] == pytest.approx(1.1111 * 0.5, abs=1e-3)


def test_format_table_shows_a_dash_for_missing():
    text = report.format_table([{"day": "2026-11-12", "cost_usd": None, "call_count": 12345}], ["day", "call_count", "cost_usd"])
    assert text.splitlines()[-1].split() == ["2026-11-12", "12,345", "-"]
    assert report.format_table([], ["day"]) == "(no rows)"


def test_loader_reads_rows_and_skips_bad_lines(log_dir):
    calls.record_llm_call(provider="gemini", model="m", usage=None, is_ok=True)
    path = next(log_dir.glob("llm_calls_*.jsonl"))
    with path.open("a") as fh:
        fh.write("not json\n\n" + json.dumps({"model": "row with no id"}) + "\n")
    counts = load_bronze.load(log_dir, dry_run=True)
    assert counts == {"llm_calls_read": 1, "gpu_runs_read": 0}


def test_loader_columns_match_the_migration():
    sql = (Path(__file__).resolve().parents[3] / "packages/hosting/scripts/neon/migrations" / load_bronze.MIGRATION).read_text().lower()
    for table, columns in load_bronze.TABLES.values():
        body = sql.split(f"create table if not exists {table} (", 1)[1].split(");", 1)[0]
        declared = [line.split()[0] for line in body.splitlines() if line.strip()]
        assert declared == list(columns)
    assert load_bronze.insert_sql("bronze.bronze_llm_call", ("llm_call_id", "model")) == (
        "INSERT INTO bronze.bronze_llm_call (llm_call_id, model) VALUES %s ON CONFLICT (llm_call_id) DO NOTHING RETURNING 1"
    )


def test_recorded_row_has_exactly_the_table_columns(log_dir, monkeypatch):
    calls.record_llm_call(provider="gemini", model="m", usage=None, is_ok=True)
    (row,) = _rows(log_dir, "llm_calls")
    assert set(row) == set(load_bronze.LLM_CALL_COLUMNS)
    monkeypatch.setattr(gpu, "gpu_names", lambda: ["Tesla T4"])
    monkeypatch.setattr(gpu, "start_gpu_sampler", lambda path, interval_ms=5000: None)
    monkeypatch.setattr(gpu, "stop_gpu_sampler", lambda sampler: None)
    with gpu.gpu_run("step"):
        pass
    (gpu_row,) = _rows(log_dir, "gpu_runs")
    assert set(gpu_row) == set(load_bronze.GPU_RUN_COLUMNS)
