"""Colab Gemma policy analysis (#511): schema, prompt, repair, resume, usage, pilot, export and import.

No GPU, no network, no database: the model is a fake generator and storage is a temp folder.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from llm.gemini import compare_models as cm
from llm.gemini import part1_schema as ps
from llm.gpu import colab_io as io_
from llm.gpu import colab_policy_analyze as cpa
from llm.gpu import colab_policy_export as cpe
from llm.gpu import colab_policy_import as cpi

TRANSCRIPT = ("Good evening. The council will now take up the data center rezoning. "
              "We were promised two hundred jobs and that is a promise we will hold them to. "
              "All in favor? Motion carries five to two.")


def _analysis(quote: str = "two hundred jobs and that is a promise") -> dict:
    return {
        "meeting": {"body_name": "City Council", "meeting_date": "2026-07-01"},
        "people": [{"person_id": "P001", "full_name": "Dana Whitfield"}],
        "job_claims": [{"phase": "operations", "headcount_low": 200, "quote": quote}],
        "places": [{"place_id": "place_x", "raw_text": "the data center", "linked_decision_ids": ["D001", None]}],
        "uncontested_items": None,
        "decisions": [{
            "decision_id": "D001", "headline": "Data center rezoning approved", "outcome": "Approved",
            "vote_tally": {"yes": 5, "no": "2"}, "place_refs": None,
            "media_anchor": {"timestamp_start_seconds": 12.0, "timestamp_end_seconds": None},
        }],
    }


def _request(video_id: str = "vid00000001", user_message: str = "PROMPT HEAD\n\n<transcript>\nhello\n</transcript>"):
    return {
        "video": {"video_id": video_id, "video_url": f"https://youtu.be/{video_id}", "title": "Council 2026-07-01",
                  "last_updated": None, "event_date": "2026-07-01", "audio_file_path": None,
                  "jurisdiction_id": "jasper_18073", "state_code": "IN"},
        "model": "", "user_message": user_message, "prompt_path": "/x/prompts/policy_analysis_part_1.md",
        "transcript_block": "=== TRANSCRIPT ===\n" + TRANSCRIPT,
        "transcript_meta": {"video_id": video_id, "segment_count": 3,
                            "youtube": {"raw_text": TRANSCRIPT, "segments": [{"text": TRANSCRIPT, "start": 0.0}],
                                        "transcript_source": "database:bronze_event_youtube_transcript (segments)"}},
        "agenda_blocks": [], "state_code": "IN", "out_dir": "/x/data/cache/gemini_transcript_policy",
        "prompt_name": "policy_analysis_part_1", "prompt_sha256": "ab" * 32,
    }


class FakeGenerator:
    """Returns the scripted answers in order; records every conversation it was given."""

    def __init__(self, answers, *, context_tokens=262144, input_tokens=40000):
        self.answers = list(answers)
        self.calls: list[list[dict]] = []
        self.model_id = cpa.DEFAULT_MODEL
        self.quantization = "4bit"
        self.context_tokens = context_tokens
        self.max_new_tokens = 32768
        self.transformers_version = "5.5.1"
        self.input_tokens = input_tokens

    def count_tokens(self, messages):
        return self.input_tokens

    def generate(self, messages):
        self.calls.append(messages)
        if self.input_tokens + self.max_new_tokens > self.context_tokens:
            raise cpa.ContextTooLong("too long")
        text = self.answers.pop(0)
        return cpa.Generation(text=text, input_tokens=self.input_tokens, output_tokens=900, seconds=30.0,
                              hit_limit=False)


@pytest.fixture(autouse=True)
def _usage_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_USAGE_LOG_DIR", str(tmp_path / "llm_usage"))


# --------------------------------------------------------------------------------------------- schema
def test_schema_accepts_the_prompts_shape_and_tolerates_nulls():
    result = ps.validate_part1(_analysis())
    assert result.ok and result.item_count == 1 and result.data["decisions"][0]["decision_id"] == "D001"


@pytest.mark.parametrize("broken, needle", [
    ({"decisions": []}, "meeting"),
    ({"meeting": {}}, "decisions"),
    ({"meeting": {}, "decisions": [{"headline": "x"}]}, "decisions.0.decision_id"),
    ({"meeting": {}, "decisions": [], "job_claims": [{"phase": "operations"}]}, "job_claims.0.quote"),
    ({"meeting": {}, "decisions": [{"decision_id": "D1", "headline": "x", "vote_tally": "5-2"}]}, "vote_tally"),
])
def test_schema_rejects_missing_ids_and_wrong_types(broken, needle):
    result = ps.validate_part1(broken)
    assert not result.ok and any(needle in e for e in result.errors)


def test_parse_handles_fences_wrapping_and_prose():
    body = json.dumps(_analysis())
    assert ps.parse_and_validate(f"```json\n{body}\n```").ok
    assert ps.parse_and_validate(f"[{body}]").ok
    assert ps.parse_and_validate(f"Here is the analysis:\n{body}\nThanks").ok
    cut = ps.parse_and_validate(body[:200], hit_token_limit=True)
    assert not cut.ok and cut.truncated and "cut off" in cut.errors[0]


def test_zero_items_is_valid_but_counted():
    result = ps.validate_part1({"meeting": {}, "decisions": [], "uncontested_items": []})
    assert result.ok and result.item_count == 0


# --------------------------------------------------------------------------------------------- choices
def test_model_aliases_and_quantization():
    assert cpa.resolve_model(None) == "google/gemma-4-31B-it"
    assert cpa.resolve_model("gemma-4-26b-a4b-it") == "google/gemma-4-26B-A4B-it"
    assert cpa.choose_quantization("auto", 40.0) == "4bit"
    assert cpa.choose_quantization("auto", 22.5) == "4bit"
    assert cpa.choose_quantization("auto", 80.0) == "bf16"
    assert cpa.choose_quantization("auto", None) == "4bit"
    assert cpa.choose_quantization("none", 16.0) == "bf16"
    assert cpa.choose_quantization("4bit", 80.0) == "4bit"
    with pytest.raises(ValueError):
        cpa.choose_quantization("8bit", 40.0)


def test_arm_label_round_trips_through_compare_models():
    label = cpa.arm_label("google/gemma-4-31B-it", "4bit")
    arm = cm.parse_arm(label)
    assert arm.label == label and arm.slug == cpa.arm_slug(label)


# --------------------------------------------------------------------------------------- prompt assembly
def test_the_exported_message_is_sent_verbatim_as_the_user_turn():
    msg = "PROMPT HEAD\n\nMEDIA CONTEXT\n\n<transcript>\nline\n</transcript>"
    messages = cpa.build_messages(msg)
    assert messages == [{"role": "user", "content": [{"type": "text", "text": msg}]}]
    assert cpa.build_messages(msg, "be terse")[0]["role"] == "system"


def test_export_refuses_a_transcript_that_did_not_come_from_the_warehouse(monkeypatch):
    from llm.gemini import meeting_transcript_policy as mtp
    from llm.gemini import transcript_db

    monkeypatch.setattr(transcript_db, "fetch_db_transcript", lambda url, vid: {"segments": [1]})
    video = SimpleNamespace(video_id="v1")
    monkeypatch.setattr(mtp, "select_bronze_videos", lambda ns, jid: [video])
    monkeypatch.setattr(mtp, "load_speaker_context", lambda ns, jid: ("", []))
    req = SimpleNamespace(model="gemini", transcript_meta={"youtube": {"transcript_source": "youtube_captions (en)"}})
    monkeypatch.setattr(mtp, "prepare_part1_request", lambda *a, **k: req)
    request, why = cpe.build_request(cpe.Target("v1", "jasper_18073", "IN"), "postgresql://x", Path("/repo"))
    assert request is None and "did not come from the warehouse" in why

    req.transcript_meta["youtube"]["transcript_source"] = "database:bronze_event_youtube_transcript (segments)"
    request, why = cpe.build_request(cpe.Target("v1", "jasper_18073", "IN"), "postgresql://x", Path("/repo"))
    assert request is req and request.model == "" and why == ""


def test_export_never_uses_neon(monkeypatch):
    monkeypatch.delenv("OPEN_NAVIGATOR_DATABASE_URL", raising=False)
    monkeypatch.setenv("NEON_DATABASE_URL_DEV", "postgresql://neon.example/db")
    assert "localhost:5433" in cpe.resolve_database_url()
    assert cpe.database_label("postgresql://u:secret@localhost:5433/open_navigator") == "localhost:5433/open_navigator"
    assert cpe.read_video_ids("a\nb, c\n# note\na\n") == ["a", "b", "c"]


# ------------------------------------------------------------------------------------- validate + repair
def test_valid_first_answer_is_accepted():
    gen = FakeGenerator([json.dumps(_analysis())])
    out = cpa.analyze_request(_request(), gen)
    assert out.status == "ok" and len(out.attempts) == 1 and out.data["decisions"][0]["decision_id"] == "D001"
    assert gen.calls[0][0]["content"][0]["text"] == _request()["user_message"]


def test_one_repair_turn_then_accepted():
    bad = json.dumps({"meeting": {}, "decisions": [{"headline": "no id"}]})
    gen = FakeGenerator([bad, json.dumps(_analysis())])
    calls = []
    out = cpa.analyze_request(_request(), gen, record_call=lambda g, ok, err: calls.append((ok, err)))
    assert out.status == "ok" and len(out.attempts) == 2
    repair = gen.calls[1]
    assert [m["role"] for m in repair] == ["user", "assistant", "user"]
    assert repair[1]["content"][0]["text"] == bad
    assert "decisions.0.decision_id" in repair[2]["content"][0]["text"]
    assert calls == [(False, "SchemaInvalid"), (True, None)]


def test_still_invalid_after_repair_is_failed_with_no_result():
    gen = FakeGenerator(["not json", '{"decisions": []}'])
    out = cpa.analyze_request(_request(), gen)
    assert out.status == "failed" and out.data is None and out.text is None and len(out.attempts) == 2
    assert len(gen.calls) == 2   # exactly one repair


def test_a_prompt_over_the_context_fails_clearly():
    gen = FakeGenerator([], context_tokens=50000, input_tokens=40000)
    out = cpa.analyze_request(_request(), gen)
    assert out.status == "failed" and out.errors == ["too long"] and not out.attempts


# ------------------------------------------------------------------------------- batch, resume, usage
def _bundle(root: Path, ids, pilot_ids=()):
    b = root / "policy_export" / "2026-11-17"
    (b / "requests").mkdir(parents=True)
    for vid in [*ids, *pilot_ids]:
        (b / "requests" / f"{vid}.json").write_text(json.dumps(_request(vid)))
    (b / "videos.txt").write_text("".join(f"{v}\n" for v in ids))
    (b / "pilot_videos.txt").write_text("".join(f"{v}\n" for v in pilot_ids))
    (b / "references").mkdir()
    for vid in pilot_ids:
        (b / "references" / f"{vid}.json").write_text(json.dumps(_analysis()))
    (b / "manifest.json").write_text(json.dumps({"prompt_name": "policy_analysis_part_1",
                                                 "prompt_sha256": "ab" * 32,
                                                 "prompt_version": "policy_analysis_part_1@abababababab"}))
    return "policy_export/2026-11-17"


def test_run_batch_writes_pipeline_meta_and_resumes(tmp_path):
    store = io_.LocalStore(tmp_path)
    bundle = _bundle(tmp_path, ["vid00000001", "vid00000002"])
    gen = FakeGenerator([json.dumps(_analysis()), "garbage", "still garbage"])
    rows = cpa.run_batch(["vid00000001", "vid00000002"], store, bundle=bundle, out="policy_analysis",
                         run_date="2026-11-18", generator=gen, gpu="A100", use_gpu_run=False)
    run = tmp_path / "policy_analysis" / "2026-11-18"
    assert {r["run_status_code"] for r in rows} == {"ok", "failed"}
    meta = json.loads((run / "vid00000001.meta.json").read_text())
    assert meta["gemini_model"] == meta["model"] == "google/gemma-4-31B-it"
    assert meta["backend"] == "colab_hf" and meta["quantization"] == "4bit" and meta["gpu_name"] == "A100"
    assert meta["prompt_version"] == "policy_analysis_part_1@abababababab"
    assert meta["transformers_version"] == "5.5.1" and meta["decoding"]["do_sample"] is False
    assert meta["usage"]["input_token_count"] == 40000 and meta["usage"]["output_token_count"] == 900
    assert meta["seconds"] == 30.0 and "youtube" not in meta["transcript"]
    assert (run / "vid00000001.response.txt").is_file()
    assert not (run / "vid00000002.analysis.json").exists() and (run / "vid00000002.failed.json").is_file()

    usage = [json.loads(line) for line in (run / "usage.jsonl").read_text().splitlines()]
    assert [u["run_status_code"] for u in usage] == ["ok", "failed"]
    assert usage[0]["model"] == "google/gemma-4-31B-it" and usage[0]["backend"] == "colab_hf"
    assert usage[0]["compute_units"] == round(30 / 3600 * io_.COLAB_CU_PER_HOUR["A100"], 4)
    assert usage[0]["is_estimated"] is True
    calls = [json.loads(line) for p in (tmp_path / "llm_usage").glob("llm_calls_*.jsonl")
             for line in p.read_text().splitlines()]
    assert len(calls) == 3 and {c["provider"] for c in calls} == {"colab_hf"}
    assert {c["model"] for c in calls} == {"google/gemma-4-31B-it"} and calls[0]["video_id"] == "vid00000001"

    # resume: the done one is skipped, the failed one is tried again
    gen2 = FakeGenerator([json.dumps(_analysis())])
    rows = cpa.run_batch(["vid00000001", "vid00000002"], store, bundle=bundle, out="policy_analysis",
                         run_date="2026-11-18", generator=gen2, gpu="A100", use_gpu_run=False)
    assert [r["run_status_code"] for r in rows] == ["skipped", "ok"] and len(gen2.calls) == 1


def test_dry_run_loads_no_model(tmp_path):
    store = io_.LocalStore(tmp_path)
    bundle = _bundle(tmp_path, ["vid00000001"])

    def factory():
        raise AssertionError("model loaded on a dry run")

    rows = cpa.run_batch(["vid00000001", "nope"], store, bundle=bundle, out="policy_analysis",
                         run_date="2026-11-18", generator_factory=factory, dry_run=True)
    assert [r["run_status_code"] for r in rows] == ["planned", "missing_request"]


def test_no_items_is_saved_like_the_pipeline_does(tmp_path):
    store = io_.LocalStore(tmp_path)
    bundle = _bundle(tmp_path, ["vid00000001"])
    gen = FakeGenerator([json.dumps({"meeting": {}, "decisions": [], "uncontested_items": []})])
    cpa.run_batch(["vid00000001"], store, bundle=bundle, out="policy_analysis", run_date="2026-11-18",
                  generator=gen, gpu="L4", use_gpu_run=False)
    saved = json.loads((tmp_path / "policy_analysis/2026-11-18/vid00000001.analysis.json").read_text())
    assert saved["_error"] == cpa.NO_ITEMS_ERROR


def test_pilot_is_an_arm_compare_models_scores(tmp_path):
    store = io_.LocalStore(tmp_path)
    bundle = _bundle(tmp_path, [], pilot_ids=["vid00000009"])
    answer = _analysis(quote="we were promised three hundred jobs")   # not in the transcript
    gen = FakeGenerator([json.dumps(answer)])
    cpa.run_batch(["vid00000009"], store, bundle=bundle, out="policy_analysis", run_date="2026-11-18",
                  generator=gen, gpu="A100", pilot=True, use_gpu_run=False)
    comp = tmp_path / "policy_analysis/2026-11-18/comparison"
    run_json = json.loads((comp / "run.json").read_text())
    assert run_json["reference"] == "existing" and run_json["arms"] == ["google/gemma-4-31B-it@colab_hf-4bit"]
    arms = cm.parse_arms(",".join(run_json["arms"]))
    rows = cm.score_run(comp, arms, run_json["reference"])
    assert len(rows) == 1
    row = rows[0]
    assert row["item_recall"] == 1.0 and row["is_ok"] and row["latency_seconds"] == 30.0
    assert row["quote_count"] == 2 and row["quote_verbatim_rate"] == 0.5   # raw_text found, the job quote isn't
    assert row["reference_quote_verbatim_rate"] == 1.0
    assert row["quotes_not_found"] == ["we were promised three hundred jobs"]
    out = cm.write_outputs(comp, run_json, rows, arms)
    assert "quote not in transcript: we were promised three hundred jobs" in out.read_text()

    # the owner's measured CU is apportioned to the meeting and lands in the comparison record
    batch = cpa.record_measured_cu(store, "policy_analysis", "2026-11-18", 100.0, 99.5, "A100")
    assert batch["compute_units"] == 0.5 and batch["is_estimated"] is False
    rec = json.loads((comp / "vid00000009" / f"{cpa.arm_slug(run_json['arms'][0])}.call.json").read_text())
    assert rec["compute_units"] == 0.5 and "apportioned" in rec["compute_units_source"]
    usage = (tmp_path / "policy_analysis/2026-11-18/usage.jsonl").read_text()
    assert "meeting_apportioned_cu" in usage


def test_apportion_and_measured_cu():
    assert io_.apportion(3.0, {"a": 100, "b": 200, "c": 0}) == {"a": 1.0, "b": 2.0}
    assert io_.apportion(3.0, {}) == {}
    assert io_.measured_batch_cu(10, 12) is None and io_.measured_batch_cu(None, 1) is None
    assert io_.clean_rel("crawl/policy_export/x/videos.txt") == "policy_export/x/videos.txt"
    assert io_.clean_rel(f"{io_.DRIVE_ROOT}/policy_analysis") == "policy_analysis"
    with pytest.raises(ValueError):
        io_.clean_rel("../etc")
    assert io_.gpu_kind("NVIDIA A100-SXM4-40GB") == "A100" and io_.gpu_kind("NVIDIA L4") == "L4"


# -------------------------------------------------------------------------------------------- export
def test_export_bundle_writes_requests_pilot_and_manifest(tmp_path):
    repo = tmp_path / "repo"
    (repo / "prompts").mkdir(parents=True)
    (repo / "prompts" / "policy_analysis_part_1.md").write_text("PROMPT")
    built = []

    def build(target, url, root):
        built.append(target.video_id)
        if target.video_id == "bad":
            return None, "no usable row in bronze_event_youtube_transcript"
        req = SimpleNamespace(prompt_path=root / "prompts/policy_analysis_part_1.md",
                              to_json=lambda vid=target.video_id: _request(vid))
        return req, ""

    def reference(request):
        return _analysis(), {"gemini_model": "gemini-2.5-flash"}

    targets = [cpe.Target("v1", "jasper_18073", "IN"), cpe.Target("bad", "x_1", "IN")]
    pilots = [cpe.Target("p1", "jasper_18073", "IN")]
    bundle = tmp_path / "out" / "2026-11-17"
    result = cpe.export_bundle(targets, pilots, bundle_dir=bundle, database_url="postgresql://localhost:5433/x",
                               repo_root=repo, pilot=1, build=build, reference=reference)
    assert result.exported == ["v1"] and result.pilot == ["p1"] and "bad" in result.skipped
    assert (bundle / "videos.txt").read_text() == "v1\n" and (bundle / "pilot_videos.txt").read_text() == "p1\n"
    req = json.loads((bundle / "requests/v1.json").read_text())
    assert req["user_message"] and req["prompt_sha256"] == cpe.prompt_file_sha256(repo / "prompts/policy_analysis_part_1.md")
    assert json.loads((bundle / "references/p1.meta.json").read_text())["gemini_model"] == "gemini-2.5-flash"
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["video_count"] == 1 and manifest["prompt_version"].startswith("policy_analysis_part_1@")
    assert manifest["videos"]["v1"]["transcript_chars"] == len(TRANSCRIPT)
    assert "secret" not in json.dumps(manifest)

    # re-export: nothing already in requests/ is rebuilt
    built.clear()
    cpe.export_bundle(targets, pilots, bundle_dir=bundle, database_url="postgresql://localhost:5433/x",
                      repo_root=repo, pilot=1, build=build, reference=reference)
    assert built == ["bad"]


# -------------------------------------------------------------------------------------------- import
def _run_folder(tmp_path: Path, vid: str, **meta_over) -> Path:
    run = tmp_path / "run"
    run.mkdir(exist_ok=True)
    meta = {"model": "google/gemma-4-31B-it", "backend": "colab_hf", "status": "ok", "json_parsed": True,
            "pilot": False, "quantization": "4bit", "gpu_name": "A100", "usage": {"input_token_count": 1},
            "prompt_sha256": "ab" * 32, "files": {"x": "y"}, **meta_over}
    (run / f"{vid}.analysis.json").write_text(json.dumps(_analysis()))
    (run / f"{vid}.meta.json").write_text(json.dumps(meta))
    (run / f"{vid}.response.txt").write_text(json.dumps(_analysis()))
    return run


def test_import_plan_skips_pilot_and_invalid(tmp_path):
    run = _run_folder(tmp_path, "ok1")
    _run_folder(tmp_path, "pil", pilot=True)
    _run_folder(tmp_path, "bad", status="failed", json_parsed=False)
    todo, skipped = cpi.plan_imports(run)
    assert todo == ["ok1"] and set(skipped) == {"pil", "bad"}
    assert cpi.plan_imports(run, include_pilot=True)[0] == ["ok1", "pil"]


def test_import_saves_through_the_pipeline_with_the_gemma_model(tmp_path, monkeypatch):
    from llm.gemini import transcript_cache_paths as tcp

    run = _run_folder(tmp_path, "vid00000001")
    _run_folder(tmp_path, "vid00000002")
    bundle = tmp_path / "bundle"
    (bundle / "requests").mkdir(parents=True)
    for vid in ("vid00000001", "vid00000002"):
        (bundle / "requests" / f"{vid}.json").write_text(json.dumps(_request(vid)))
    monkeypatch.setattr(tcp, "resolve_analysis_path",
                        lambda *a, video_id="", **k: Path("x.json") if video_id == "vid00000002" else None)
    saved = []

    def save(request, text, ns, **kw):
        saved.append((request, text, ns, kw))

    out = cpi.import_run(run, bundle, output_dir=tmp_path / "cache", database_url="postgresql://localhost:5433/x",
                         repo_root=tmp_path, save=save)
    assert out["vid00000001"] == "imported" and out["vid00000002"].startswith("skipped: already analyzed")
    request, text, ns, kw = saved[0]
    assert request.model == "google/gemma-4-31B-it" and request.out_dir == tmp_path / "cache"
    assert request.prompt_path == tmp_path / "prompts/policy_analysis_part_1.md"
    assert kw["generation_source"] == "colab_hf" and kw["extra_meta"]["backend"] == "colab_hf"
    assert kw["extra_meta"]["prompt_sha256"] == "ab" * 32 and "files" not in kw["extra_meta"]
    assert json.loads(text)["decisions"][0]["decision_id"] == "D001"


@pytest.mark.parametrize("name,repo", [
    ("e4b", "google/gemma-4-E4B-it"),
    ("gemma-4-e4b-it", "google/gemma-4-E4B-it"),
    ("google/gemma-4-E2B-it", "google/gemma-4-E2B-it"),
    ("12B", "google/gemma-4-12B-it"),
    ("gemma-4-12b-it", "google/gemma-4-12B-it"),
    ("31b", "google/gemma-4-31B-it"),
])
def test_small_gemma_aliases_resolve_to_the_repo_ids(name, repo):
    assert cpa.resolve_model(name) == repo


def test_attention_flag_is_optional_and_validated():
    parser = cpa.build_parser()
    assert parser.parse_args(["--videos-file", "x"]).attn_implementation is None
    assert parser.parse_args(["--videos-file", "x", "--attn-implementation", "sdpa"]).attn_implementation == "sdpa"
    with pytest.raises(SystemExit):
        parser.parse_args(["--videos-file", "x", "--attn-implementation", "bogus"])
