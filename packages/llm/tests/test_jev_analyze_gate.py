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
