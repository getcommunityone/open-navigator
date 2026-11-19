"""The Colab GPU step's plain parts (#297): batch, resume, output path, usage row, CU, no tokens in logs.

No GPU, no network and no Databricks: the WhisperX call is a stand-in and the volume is a temp folder.
"""

import io
import json
import math

import pytest
from loguru import logger

from llm.gpu import colab_diarize as cd
from llm.gpu import diarize_common as dc

RESULT = {
    "segments": [
        {"start": 0.0, "end": 30.0, "text": "x", "speaker": "SPEAKER_00"},
        {"start": 30.0, "end": 90.0, "text": "y", "speaker": "SPEAKER_01"},
        {"start": 90.0, "end": 120.0, "text": "z", "speaker": "SPEAKER_00"},
    ],
    "raw_text": "x y z",
    "engine": "whisperx",
}


@pytest.fixture(autouse=True)
def _no_usage_files(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_USAGE_LOG", "0")
    monkeypatch.setenv("LLM_USAGE_LOG_DIR", str(tmp_path / "llm_usage"))


@pytest.fixture
def volume(tmp_path):
    root = tmp_path / "crawl"
    (root / "audio").mkdir(parents=True)
    for name in ("a.opus", "b.opus", "c.opus", "d.opus"):
        (root / "audio" / name).write_bytes(b"fake audio")
    return cd.LocalStore(root)


def fake_diarize(calls):
    def run(audio, *, model_size, hf_token):
        calls.append((audio.name, model_size))
        return RESULT
    return run


def test_the_batch_is_capped_at_three_by_default_and_deduplicated():
    assert cd.DEFAULT_LIMIT == 3
    assert dc.plan_batch(["a", " a ", "b", "", "c", "d"]) == ["a", "b", "c"]


def test_volume_paths_are_read_relative_to_the_landing_volume():
    assert cd.volume_rel("crawl/audio/a.opus") == "audio/a.opus"
    assert cd.volume_rel("audio/a.opus") == "audio/a.opus"
    assert cd.volume_rel(cd.LANDING_VOLUME + "/audio/a.opus") == "audio/a.opus"
    for bad in ("../x.opus", "crawl/../../x", "/etc/passwd", "crawl/"):
        with pytest.raises(ValueError):
            cd.volume_rel(bad)


def test_the_output_goes_under_diarized_and_the_run_date():
    assert cd.output_rel("crawl/audio/2026-11-03 council.opus", "2026-11-17") == \
        "diarized/2026-11-17/audio_2026-11-03_council.diarized.json"
    assert cd.output_rel("https://example.org/m/516.mp4?sig=1", "2026-11-17") == "diarized/2026-11-17/m_516.diarized.json"
    assert cd.LANDING_VOLUME.endswith("/open_navigator/open_navigator_landing/crawl")
    with pytest.raises(ValueError):
        cd.output_rel("audio/a.opus", "17-11-2026")


def test_a_finished_item_is_skipped_on_resume(volume):
    calls = []
    first = cd.run_batch(["crawl/audio/a.opus"], volume, run_date="2026-11-17", diarize_fn=fake_diarize(calls))
    assert [r["run_status_code"] for r in first] == ["ok"]
    out = volume.root / "diarized" / "2026-11-17" / "audio_a.diarized.json"
    assert json.loads(out.read_text())["segments"][0]["speaker"] == "SPEAKER_00"

    # Colab disconnected; the same cell is run again with the whole batch
    again = cd.run_batch(["crawl/audio/a.opus", "crawl/audio/b.opus"], volume, run_date="2026-11-17",
                         diarize_fn=fake_diarize(calls))
    assert [(r["item_name"], r["run_status_code"]) for r in again] == [
        ("crawl/audio/a.opus", "skipped"), ("crawl/audio/b.opus", "ok")]
    assert [c[0] for c in calls] == ["a.opus", "b.opus"]


def test_a_new_run_date_runs_the_item_again(volume):
    calls = []
    cd.run_batch(["audio/a.opus"], volume, run_date="2026-11-17", diarize_fn=fake_diarize(calls))
    cd.run_batch(["audio/a.opus"], volume, run_date="2026-11-18", diarize_fn=fake_diarize(calls))
    assert len(calls) == 2


def test_split_done_uses_the_output_names_in_the_folder():
    todo, done = cd.split_done(["crawl/audio/a.opus", "audio/b.opus"], {"audio_a.diarized.json", "usage.jsonl"})
    assert todo == ["audio/b.opus"] and done == ["crawl/audio/a.opus"]


def test_the_limit_caps_the_run(volume):
    calls = []
    items = [f"audio/{n}.opus" for n in "abcd"]
    rows = cd.run_batch(items, volume, run_date="2026-11-17", limit=2, diarize_fn=fake_diarize(calls))
    assert len(rows) == 2 and len(calls) == 2


def test_a_dry_run_plans_without_running_or_writing(volume):
    calls = []
    rows = cd.run_batch(["audio/a.opus"], volume, run_date="2026-11-17", dry_run=True, diarize_fn=fake_diarize(calls))
    assert rows[0]["run_status_code"] == "planned" and not calls
    assert not (volume.root / "diarized").exists()


def test_each_item_appends_a_usage_row_with_cu_and_a_summary(volume):
    rows = cd.run_batch(["audio/a.opus", "audio/b.opus"], volume, run_date="2026-11-17", gpu="T4",
                        diarize_fn=fake_diarize([]))
    lines = (volume.root / "diarized" / "2026-11-17" / "usage.jsonl").read_text().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert row["platform_name"] == "colab" and row["step_name"] == "whisperx_diarization"
    assert row["gpu_name"] == "T4" and row["run_status_code"] == "ok" and row["is_estimated"] is True
    assert row["compute_units_source"].startswith("estimate")
    assert rows[0]["segments"] == 3 and rows[0]["speakers"] == 2 and rows[0]["speaking_minutes"] == 2.0


def test_the_usage_row_has_the_modal_fields_plus_compute_units():
    modal_keys = set(dc.base_usage_row("modal", "a", "T4", "t", 1.0, "ok", None))
    row = cd.usage_row("audio/a.opus", "t4", "2026-11-17T20:00:00+00:00", 3600.0, "ok")
    assert modal_keys <= set(row)
    assert math.isclose(row["gpu_hours"], 1.0)
    assert math.isclose(row["compute_units"], cd.COLAB_CU_PER_HOUR["T4"])
    assert math.isclose(row["estimated_cost_usd"], cd.COLAB_CU_PER_HOUR["T4"] * cd.COLAB_USD_PER_CU, rel_tol=1e-4)
    assert "documented T4 rate" in row["compute_units_source"] and "estimate" in row["compute_units_source"]


def test_a_rate_read_from_colab_replaces_the_documented_one():
    row = cd.usage_row("a", "T4", "t", 1800.0, "ok", cu_per_hour=2.0)
    assert math.isclose(row["compute_units"], 1.0) and row["cu_per_hour"] == 2.0
    assert "Resources panel" in row["compute_units_source"]


def test_a_gpu_with_no_rate_has_no_cu_rather_than_a_guess():
    row = cd.usage_row("a", "Z9", "t", 60.0, "ok")
    assert row["compute_units"] is None and row["estimated_cost_usd"] is None
    assert row["compute_units_source"].startswith("unknown")


def test_measured_cu_comes_from_the_balance_before_and_after(volume):
    assert cd.measured_batch_cu(100.0, 98.5) == 1.5
    assert cd.measured_batch_cu(None, 98.5) is None
    assert cd.measured_batch_cu(90.0, 100.0) is None   # a top-up in between
    row = cd.record_measured_cu(volume, "2026-11-17", 100.0, 98.5, "T4")
    assert row["is_estimated"] is False and row["compute_units"] == 1.5
    saved = (volume.root / "diarized" / "2026-11-17" / "usage.jsonl").read_text()
    assert json.loads(saved.splitlines()[-1])["row_kind"] == "batch_measured_cu"


def test_gpu_kind_reads_nvidia_smi_names():
    assert cd.gpu_kind("Tesla T4") == "T4"
    assert cd.gpu_kind("NVIDIA L4") == "L4"
    assert cd.gpu_kind("NVIDIA A100-SXM4-40GB") == "A100"
    assert cd.gpu_kind(None) == "NONE"


def test_a_failed_item_is_recorded_and_the_batch_goes_on_without_leaking_a_token(volume):
    token = "hf_SuperSecretValue123"
    messages = []
    sink = logger.add(messages.append, format="{message}")

    def boom(audio, *, model_size, hf_token):
        if audio.name == "a.opus":
            raise RuntimeError(f"401 for token {hf_token}")
        return RESULT

    try:
        rows = cd.run_batch(["audio/a.opus", "audio/b.opus"], volume, run_date="2026-11-17", hf_token=token,
                            secrets=[token], diarize_fn=boom)
    finally:
        logger.remove(sink)
    assert [r["run_status_code"] for r in rows] == ["failed", "ok"]
    assert "***" in rows[0]["error_text"]
    usage = (volume.root / "diarized" / "2026-11-17" / "usage.jsonl").read_text()
    assert token not in usage
    assert not any(token in str(m) for m in messages)
    assert dc.exit_code(rows) == 0


def test_main_never_prints_or_logs_the_tokens(volume, monkeypatch, capsys):
    secrets = {"DATABRICKS_TOKEN": "dapiSECRET0000", "HF_TOKEN": "hf_SECRET1111"}
    for k, v in secrets.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)   # no host: the Drive folder is used
    messages = []
    sink = logger.add(messages.append, format="{message}")
    try:
        code = cd.main(["--items", "crawl/audio/a.opus,audio/b.opus", "--drive-root", str(volume.root),
                        "--run-date", "2026-11-17", "--dry-run"])
    finally:
        logger.remove(sink)
    out = capsys.readouterr()
    text = out.out + out.err + "".join(str(m) for m in messages)
    assert code == 0 and "audio/b.opus" in text
    assert not any(v in text for v in secrets.values())


def test_secrets_come_from_colab_first_then_the_environment(monkeypatch):
    class Userdata:
        def get(self, name):
            if name == "HF_TOKEN":
                return "from-colab"
            raise KeyError(name)   # Colab raises SecretNotFoundError

    monkeypatch.setenv("HF_TOKEN", "from-env")
    monkeypatch.setenv("DATABRICKS_HOST", "https://example")
    assert cd.get_secret("HF_TOKEN", Userdata()) == "from-colab"
    assert cd.get_secret("DATABRICKS_HOST", Userdata()) == "https://example"
    monkeypatch.delenv("DATABRICKS_HOST")
    assert cd.get_secret("DATABRICKS_HOST", Userdata()) is None


def test_redact_hides_every_secret():
    assert cd.redact("a dapiXYZ1 b hf_abcd", ["dapiXYZ1", "hf_abcd", None]) == "a *** b ***"


def test_the_databricks_store_uses_the_files_api_and_resume_lists_the_folder():
    class Entry:
        def __init__(self, path):
            self.path, self.name = path, path.rsplit("/", 1)[-1]

    class NotFound(Exception):
        pass

    class Files:
        def __init__(self):
            self.saved = {}

        def list_directory_contents(self, path):
            names = [p for p in self.saved if p.startswith(path + "/")]
            if not names:
                raise NotFound(path)
            return [Entry(p) for p in names]

        def download(self, path):
            if path not in self.saved:
                raise NotFound(path)
            return type("R", (), {"contents": io.BytesIO(self.saved[path])})()

        def upload(self, path, contents, overwrite=False):
            self.saved[path] = contents.read()

    client = type("C", (), {"files": Files()})()
    store = cd.DatabricksVolumeStore(client)
    assert store.list_names("diarized/2026-11-17") == set()
    assert store.read_text("diarized/2026-11-17/usage.jsonl") is None
    store.write_bytes("diarized/2026-11-17/audio_a.diarized.json", b"{}")
    cd.append_usage(store, "2026-11-17", [{"x": 1}])
    cd.append_usage(store, "2026-11-17", [{"x": 2}])
    assert store.list_names("diarized/2026-11-17") == {"audio_a.diarized.json", "usage.jsonl"}
    usage = client.files.saved[cd.LANDING_VOLUME + "/diarized/2026-11-17/usage.jsonl"].decode()
    assert [json.loads(line)["x"] for line in usage.splitlines()] == [1, 2]


def test_colab_installs_the_same_whisperx_pins_as_modal():
    from llm.gpu import modal_diarize as md

    assert md.IMAGE_PACKAGES == dc.WHISPERX_PACKAGES
    assert "whisperx>=3.8,<4" in dc.WHISPERX_PACKAGES and "ctranslate2>=4.6,<5" in dc.WHISPERX_PACKAGES


def test_the_notebook_is_thin_valid_and_has_no_saved_outputs():
    from pathlib import Path

    nb = json.loads((Path(__file__).resolve().parents[1] / "notebooks" / "colab_gpu_diarize.ipynb").read_text())
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert code and all(c["outputs"] == [] and c["execution_count"] is None for c in code)
    source = "".join("".join(c["source"]) for c in code)
    assert "cd.main(" in source and "whisperx>=3.8,<4" in source and "ctranslate2>=4.6,<5" in source
    assert "owner_said_yes_to_this_run" in source and "usage before" in source and "usage after" in source
