"""The Gemini Batch API runner (#264). No network, no database."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("google.genai")

from llm.gemini import batch_backlog as bb
from llm.gemini import meeting_transcript_policy as mtp
from llm.gemini.browser_policy_analysis import VideoRow
from llm.usage import load_bronze

# A real result line: the one-request probe job of November 13, 2026.
PROBE_LINE = (
    '{"key":"k1","response":{"candidates":[{"content":{"parts":[{"text":"ok"}],"role":"model"},'
    '"finishReason":"STOP","index":0}],"usageMetadata":{"promptTokenCount":7,"candidatesTokenCount":1,'
    '"totalTokenCount":8,"promptTokensDetails":[{"modality":"TEXT","tokenCount":7}],'
    '"serviceTier":"SERVICE_TIER_STANDARD"},"modelVersion":"gemini-2.5-flash-lite","responseId":"x"}}'
)


def _request(video_id: str, out_dir: Path, model: str = "gemini-2.5-flash-lite") -> mtp.Part1Request:
    video = VideoRow(video_id=video_id, video_url=f"https://www.youtube.com/watch?v={video_id}", title="Council",
                     last_updated=datetime(2026, 11, 3, 18, 0, tzinfo=UTC), event_date="2026-11-03",
                     audio_file_path=None, jurisdiction_id="municipality_0177256", channel_id="UC1")  # fmt: skip
    return mtp.Part1Request(video=video, model=model, user_message=f"PROMPT for {video_id}",
                            prompt_path=Path("/repo/prompts/policy_analysis_part_1.md"),
                            transcript_block="[00:00:01] Mayor: order", transcript_meta={"video_id": video_id},
                            agenda_blocks=[{"start": 0}], state_code="AL", out_dir=out_dir)  # fmt: skip


def _submit_args(**over) -> argparse.Namespace:
    base = {"temperature": 0.1, "max_output_tokens": 65536, "thinking_budget": 0, "no_json_mode": False,
            "system_instruction": ""}  # fmt: skip
    return argparse.Namespace(**{**base, **over})


# --------------------------------------------------------------------------- #
# Request line
# --------------------------------------------------------------------------- #
def test_request_line_carries_the_interactive_settings():
    line = bb.build_request_line("vid", "hello", model="gemini-2.5-flash", temperature=0.1,
                                 max_output_tokens=65536, thinking_budget=0, json_mode=True)  # fmt: skip
    assert line["key"] == "vid"
    assert line["request"]["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert line["request"]["generation_config"] == {
        "temperature": 0.1,
        "max_output_tokens": 65536,
        "thinking_config": {"thinking_budget": 0},
        "response_mime_type": "application/json",
    }
    assert "system_instruction" not in line["request"]


def test_request_line_leaves_out_what_does_not_apply():
    line = bb.build_request_line("vid", "hello", model="gemini-3.1-flash-lite-preview", temperature=0.2,
                                 max_output_tokens=100, thinking_budget=0, json_mode=False,
                                 system_instruction=" Be brief. ")  # fmt: skip
    assert line["request"]["generation_config"] == {"temperature": 0.2, "max_output_tokens": 100}
    assert line["request"]["system_instruction"] == {"parts": [{"text": "Be brief."}]}


# --------------------------------------------------------------------------- #
# Result lines
# --------------------------------------------------------------------------- #
def test_parse_a_real_result_line():
    key, text, response, error = bb.parse_result_line(PROBE_LINE)
    assert (key, text, error) == ("k1", "ok", None)
    assert response["usageMetadata"]["promptTokenCount"] == 7


def test_thought_parts_are_left_out_of_the_text():
    line = json.dumps({"key": "v", "response": {"candidates": [{"content": {"parts": [
        {"text": "thinking...", "thought": True}, {"text": '{"a":'}, {"text": " 1}"}]}}]}})  # fmt: skip
    assert bb.parse_result_line(line)[1] == '{"a": 1}'


def test_error_and_empty_results_carry_a_reason():
    key, text, _, error = bb.parse_result_line(json.dumps({"key": "v", "error": {"code": 400, "message": "bad request"}}))
    assert (key, text, error) == ("v", None, "bad request")
    blocked = json.dumps({"key": "v", "response": {"candidates": [{"finishReason": "SAFETY", "content": {}}]}})
    assert bb.parse_result_line(blocked)[3] == "empty response (SAFETY)"
    assert bb.parse_result_line(json.dumps({"key": "v", "response": {}}))[3] == "empty response (no candidates)"


def test_junk_lines_are_skipped():
    for junk in ("", "   ", "not json", "[1, 2]", '{"no_key": 1}'):
        assert bb.parse_result_line(junk) is None


# --------------------------------------------------------------------------- #
# Which videos are spoken for
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("state", "collected_at", "in_flight"),
    [
        ("JOB_STATE_PENDING", None, True),
        ("JOB_STATE_RUNNING", None, True),
        ("JOB_STATE_SUCCEEDED", None, True),  # finished, results not saved yet
        ("JOB_STATE_SUCCEEDED", "2026-11-13T00:00:00+00:00", False),
        ("JOB_STATE_FAILED", None, False),
        ("JOB_STATE_CANCELLED", None, False),
        ("JOB_STATE_EXPIRED", None, False),
        (bb.DRY_RUN, None, False),
    ],
)
def test_is_in_flight(state, collected_at, in_flight):
    assert bb.is_in_flight({"state": state, "collected_at": collected_at}) is in_flight


def test_in_flight_video_ids_come_only_from_live_jobs():
    manifests = [
        {"state": "JOB_STATE_RUNNING", "collected_at": None, "video_ids": ["a", "b"]},
        {"state": "JOB_STATE_FAILED", "collected_at": None, "video_ids": ["c"]},
        {"state": "JOB_STATE_SUCCEEDED", "collected_at": "x", "video_ids": ["d"]},
    ]
    assert bb.in_flight_video_ids(manifests) == {"a", "b"}


# --------------------------------------------------------------------------- #
# Files
# --------------------------------------------------------------------------- #
def test_jobs_dir_is_beside_the_policy_cache(tmp_path):
    assert bb.default_jobs_dir(tmp_path / "gemini_transcript_policy") == tmp_path / "gemini_batch_jobs"


def test_job_id_and_chunks():
    assert bb.new_job_id(datetime(2026, 11, 13, 9, 5, 7, tzinfo=UTC), sequence=2) == "20261113T090507Z_002"
    assert [len(c) for c in bb.chunked(list(range(7)), 3)] == [3, 3, 1]


def test_manifest_round_trip_and_unreadable_ones_are_skipped(tmp_path):
    bb.write_manifest(tmp_path, {"job_id": "j2", "state": "JOB_STATE_RUNNING"})
    bb.write_manifest(tmp_path, {"job_id": "j1", "state": bb.DRY_RUN})
    (tmp_path / "j3").mkdir()
    (tmp_path / "j3" / "manifest.json").write_text("{broken")
    assert [m["job_id"] for m in bb.read_manifests(tmp_path)] == ["j1", "j2"]
    assert bb.read_manifests(tmp_path / "missing") == []


def test_part1_request_survives_json(tmp_path):
    request = _request("aaaaaaaaaaa", tmp_path)
    again = mtp.Part1Request.from_json(json.loads(json.dumps(request.to_json())))
    assert again == request
    assert again.video.last_updated == datetime(2026, 11, 3, 18, 0, tzinfo=UTC)


def test_write_job_files(tmp_path):
    requests = [_request("aaaaaaaaaaa", tmp_path), _request("bbbbbbbbbbb", tmp_path)]
    path = bb.write_job_files(tmp_path, "job1", requests, _submit_args())
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert [line["key"] for line in lines] == ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    assert lines[0]["request"]["contents"][0]["parts"][0]["text"] == "PROMPT for aaaaaaaaaaa"
    assert lines[0]["request"]["generation_config"]["thinking_config"] == {"thinking_budget": 0}
    sidecar = json.loads((tmp_path / "job1" / "requests" / "bbbbbbbbbbb.json").read_text())
    assert mtp.Part1Request.from_json(sidecar) == requests[1]


def test_negative_thinking_budget_means_the_model_default(tmp_path):
    path = bb.write_job_files(tmp_path, "job1", [_request("aaaaaaaaaaa", tmp_path, model="gemini-2.5-flash")],
                              _submit_args(thinking_budget=-1, no_json_mode=True))  # fmt: skip
    config = json.loads(path.read_text())["request"]["generation_config"]
    assert "thinking_config" not in config and "response_mime_type" not in config


# --------------------------------------------------------------------------- #
# collect
# --------------------------------------------------------------------------- #
IDS = ["aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc", "ddddddddddd"]
LINES = [
    PROBE_LINE.replace('"k1"', '"aaaaaaaaaaa"'),
    json.dumps({"key": "bbbbbbbbbbb", "error": {"message": "request too large"}}),
    PROBE_LINE.replace('"k1"', '"ccccccccccc"'),
    "not json",
]


@pytest.fixture()
def collect(tmp_path, monkeypatch):
    """Runs collect_results on a job of four videos whose results are: saved, failed,
    already analyzed, missing. Returns a function; each call collects again."""
    monkeypatch.setenv("LLM_USAGE_LOG_DIR", str(tmp_path / "usage"))
    monkeypatch.delenv("LLM_USAGE_LOG", raising=False)
    bb.write_job_files(tmp_path, "job1", [_request(v, tmp_path) for v in IDS], _submit_args())
    saved, stamped = [], []

    def fake_save(request, text, args, *, usage=None):
        saved.append((request.video.video_id, text, usage))
        return tmp_path / f"{request.video.video_id}.json"

    monkeypatch.setattr(mtp, "save_part1_response", fake_save)
    monkeypatch.setattr(mtp, "_record_policy_event_safe", lambda video_id, **kw: stamped.append((video_id, kw)))
    from llm.gemini import transcript_cache_paths

    monkeypatch.setattr(
        transcript_cache_paths,
        "resolve_analysis_path",
        lambda out_dir, jid, *, video_id, **kw: tmp_path / "existing.json" if video_id == "ccccccccccc" else None,
    )

    def run(manifest=None, save_args=None, on_outcome=None):
        manifest = manifest if manifest is not None else {"video_ids": IDS}
        outcomes = bb.collect_results(tmp_path / "job1", manifest, LINES,
                                      save_args or argparse.Namespace(database_url=""), on_outcome=on_outcome)  # fmt: skip
        usage_rows = list(load_bronze.read_rows(tmp_path / "usage", "llm_calls"))
        return outcomes, saved, stamped, usage_rows

    return run


@pytest.fixture()
def collected(collect):
    return collect()


def test_collect_outcomes(collected):
    outcomes, saved, stamped, _ = collected
    assert outcomes == {
        "aaaaaaaaaaa": "saved",
        "bbbbbbbbbbb": "failed: request too large",
        "ccccccccccc": "already saved",
        "ddddddddddd": "failed: no result line for this key",
    }
    assert [(v, text) for v, text, _ in saved] == [("aaaaaaaaaaa", "ok")]  # the existing analysis is not rewritten
    assert saved[0][2]["input_token_count"] == 7 and saved[0][2]["output_token_count"] == 1
    assert [(v, kw["ok"], kw["error"]) for v, kw in stamped] == [("bbbbbbbbbbb", False, "batch: request too large")]


def test_collect_records_usage_as_batch(collected):
    *_, usage_rows = collected
    by_video = {r["video_id"]: r for r in usage_rows}
    # the already-analyzed video's batch answer was billed too, so it is recorded
    assert set(by_video) == {"aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"}
    ok, failed, meanwhile = by_video["aaaaaaaaaaa"], by_video["bbbbbbbbbbb"], by_video["ccccccccccc"]
    assert ok["api_mode"] == "batch" and ok["stage"] == "part1" and ok["is_ok"] is True
    assert ok["input_token_count"] == 7 and ok["latency_seconds"] is None
    assert failed["is_ok"] is False and failed["error_type"] == "BatchRequestFailed"
    assert meanwhile["is_ok"] is True and meanwhile["input_token_count"] == 7


def test_collect_reports_progress_and_a_rerun_writes_nothing_twice(collect):
    progress = {}
    first, *_ = collect(on_outcome=lambda v, o: progress.__setitem__(v, o))
    assert progress == {k: v for k, v in first.items() if k != "ddddddddddd"}  # missing keys are added at the end
    # a collect that stopped after two videos: the manifest holds their outcomes
    partial = {"video_ids": IDS, "results": {"aaaaaaaaaaa": "saved", "bbbbbbbbbbb": "failed: request too large"}}
    _, saved, stamped, usage_rows = collect()  # baseline counts after one full run
    counts = (len(saved), len(stamped), len(usage_rows))
    outcomes, saved, stamped, usage_rows = collect(manifest=partial)
    assert outcomes["aaaaaaaaaaa"] == "saved" and outcomes["ccccccccccc"] == "already saved"
    new_videos = [r["video_id"] for r in usage_rows[counts[2]:]]
    assert new_videos == ["ccccccccccc"]  # a and b were not recorded again
    assert len(saved) == counts[0] and len(stamped) == counts[1]


def test_no_persist_bronze_skips_every_database_write(collect):
    save_args = bb._save_namespace(argparse.Namespace(no_persist_bronze=True, database_url=""))
    assert save_args.persist_bronze is False and save_args.no_db_events is True
    _, _, stamped, _ = collect(save_args=save_args)
    assert stamped == []


def test_partially_succeeded_jobs_have_results():
    assert "JOB_STATE_PARTIALLY_SUCCEEDED" in bb.ENDED_WITH_RESULTS
    assert bb.is_in_flight({"state": "JOB_STATE_PARTIALLY_SUCCEEDED", "collected_at": None})
    assert not bb.is_in_flight({"state": "JOB_STATE_PARTIALLY_SUCCEEDED", "collected_at": "x"})


def test_cli_parses_each_command():
    parser = bb.build_parser()
    submit = parser.parse_args(["submit", "--state", "AL", "--limit", "5", "--dry-run"])
    assert submit.func is bb.run_submit and submit.state == ["AL"] and submit.limit == 5 and submit.dry_run
    assert submit.max_requests_per_job == bb.DEFAULT_MAX_REQUESTS_PER_JOB
    assert parser.parse_args(["status"]).func is bb.run_status
    collect = parser.parse_args(["collect", "--wait", "--job", "j1"])
    assert collect.func is bb.run_collect and collect.wait and collect.job == "j1"
