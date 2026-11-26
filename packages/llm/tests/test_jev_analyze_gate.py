"""Jev skip flags on meeting_transcript_policy (#704)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm.gemini import meeting_transcript_policy as mtp


def test_iter_videos_skips_jev_gated_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "llm.gemini.policy_exclusions.is_policy_video_excluded",
        lambda *a, **k: False,
    )
    videos = [
        SimpleNamespace(video_id="keep1", title="A", event_date=None, channel_id=None),
        SimpleNamespace(video_id="skip1", title="B", event_date=None, channel_id=None),
    ]
    args = SimpleNamespace(
        skip_analyzed=False,
        ensure_local_from_bronze=False,
        _jev_skip_video_ids={"skip1"},
        output_dir=str(tmp_path),
        database_url="",
    )
    out = list(mtp.iter_videos_to_analyze(videos, args, "jid", "AL"))
    assert [v.video_id for v in out] == ["keep1"]


def test_build_parser_accepts_jev_flags():
    ns = mtp.build_parser().parse_args(
        ["--skip-jev-meeting-below", "0.6", "--skip-jev-below", "0.4"]
    )
    assert ns.skip_jev_meeting_below == pytest.approx(0.6)
    assert ns.skip_jev_below == pytest.approx(0.4)


@pytest.mark.parametrize(
    ("model", "part_2", "expected"),
    [
        ("deepseek-flash", "", True),
        ("deepseek-flash", "deepseek-flash", True),
        ("deepseek-flash", "gemini-2.5-flash-lite", False),
        ("gemini-2.5-flash-lite", "", False),
        ("", "", False),
        ("", "deepseek-flash", False),
    ],
)
def test_uses_only_deepseek_skips_gemini_key_probe(model, part_2, expected):
    """Light tier on DeepSeek must not probe a Gemini key (402 would abort the run) (#774)."""
    assert mtp.uses_only_deepseek(model, part_2) is expected


def test_light_launch_script_defaults_to_claude_haiku():
    """The light tier passes Claude Haiku model flags (#871); full tier does not."""
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "packages/scrapers/scripts/youtube_run_priority_states_last_n.sh"
    text = script.read_text(encoding="utf-8")
    assert 'LIGHT_MODEL-claude-haiku-5-5' in text
    assert 'LIGHT_MODEL-deepseek-flash' not in text
    assert '[[ "$tier" == "light" ]]' in text
    assert '--model "$light_model" --part-2-model "$light_model"' in text
