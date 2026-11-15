"""process_one_video after its split into prepare_part1_request / save_part1_response (#264). No network."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("google.genai")

from llm.gemini import meeting_transcript_policy as mtp
from llm.gemini.browser_policy_analysis import VideoRow
from llm.usage.calls import LLMCallUsage

VIDEO = VideoRow(video_id="aaaaaaaaaaa", video_url="https://www.youtube.com/watch?v=aaaaaaaaaaa", title="Council",
                 last_updated=None, event_date="2026-11-03", audio_file_path=None,
                 jurisdiction_id="municipality_0155200", state_code="AL")  # fmt: skip


@pytest.fixture()
def wired(tmp_path, monkeypatch):
    """prepare, the model call and save replaced by recorders."""
    seen = {"prepare": [], "call": [], "save": []}

    def prepare(video, args, *, speaker_hints, known, build_message=True):
        seen["prepare"].append(build_message)
        return mtp.Part1Request(video=video, model="gemini-2.5-flash", user_message="MSG" if build_message else "",
                                prompt_path=tmp_path / "p.md", transcript_block="[00:00:01] Mayor: order",
                                transcript_meta={"video_id": video.video_id}, agenda_blocks=[], state_code="AL",
                                out_dir=tmp_path)  # fmt: skip

    def call(**kwargs):
        seen["call"].append(kwargs)
        return SimpleNamespace(text='{"meeting": {}}', usage=LLMCallUsage(input_token_count=5, output_token_count=2))

    def save(request, text, args, *, usage=None):
        seen["save"].append((request.video.video_id, text, usage))
        return tmp_path / "analysis.json"

    monkeypatch.setattr(mtp, "prepare_part1_request", prepare)
    monkeypatch.setattr(mtp, "call_gemini_text", call)
    monkeypatch.setattr(mtp, "save_part1_response", save)
    monkeypatch.setenv("LLM_USAGE_LOG", "0")
    monkeypatch.delenv("GEMINI_THINKING_BUDGET", raising=False)
    return seen


def _args(tmp_path, *extra):
    args = mtp.build_parser().parse_args(["--video-id", "aaaaaaaaaaa", "--output-dir", str(tmp_path), *extra])
    args.run_part_2 = False
    return args


def test_analysis_path_calls_the_model_with_the_prepared_message_and_saves_its_usage(wired, tmp_path):
    out = mtp.process_one_video(VIDEO, _args(tmp_path), speaker_hints="", known=[], api_key="k")
    assert out == tmp_path / "analysis.json"
    assert wired["prepare"] == [True]
    (call,) = wired["call"]
    assert call["user_text"] == "MSG" and call["model"] == "gemini-2.5-flash"
    assert call["thinking_budget"] == 0 and call["json_mode"] is True
    assert wired["save"] == [("aaaaaaaaaaa", '{"meeting": {}}', LLMCallUsage(input_token_count=5, output_token_count=2).as_dict())]


def test_flags_reach_the_call(wired, tmp_path):
    mtp.process_one_video(VIDEO, _args(tmp_path, "--thinking-budget", "-1", "--no-json-mode"),
                          speaker_hints="", known=[], api_key="k")  # fmt: skip
    (call,) = wired["call"]
    assert call["thinking_budget"] is None and call["json_mode"] is False


def test_transcript_only_writes_the_transcript_and_calls_no_model(wired, tmp_path, monkeypatch):
    # The real cache-path helper memoizes folder names per jurisdiction; stub it so
    # this test leaves no module state behind for other tests.
    monkeypatch.setattr(mtp, "transcript_cache_path", lambda out_dir, jid, **kw: tmp_path / f"{kw['video_id']}.json")
    out = mtp.process_one_video(VIDEO, _args(tmp_path, "--transcript-only"), speaker_hints="", known=[], api_key="")
    assert wired["prepare"] == [False]  # the prompt is not even read
    assert wired["call"] == [] and wired["save"] == []
    payload = json.loads(out.read_text())
    assert payload["video_id"] == "aaaaaaaaaaa" and payload["formatted_transcript"] == "[00:00:01] Mayor: order"


def test_a_video_with_nothing_to_analyze_is_skipped(wired, tmp_path, monkeypatch):
    monkeypatch.setattr(mtp, "prepare_part1_request", lambda *a, **k: None)
    assert mtp.process_one_video(VIDEO, _args(tmp_path), speaker_hints="", known=[], api_key="k") is None
    assert wired["call"] == []
