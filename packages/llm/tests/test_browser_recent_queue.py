"""Recent-meeting drip queue for browser Gemini (#624)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from llm.gemini.browser_policy_analysis import (
    VideoRow,
    browser_analysis_exists,
    filter_videos_for_browser_queue,
)


def _video(
    video_id: str,
    *,
    event_date: str | None = None,
    published_at: datetime | None = None,
    title: str = "Meeting",
    jurisdiction_id: str = "tuscaloosa_0177256",
) -> VideoRow:
    return VideoRow(
        video_id=video_id,
        video_url=f"https://www.youtube.com/watch?v={video_id}",
        title=title,
        last_updated=None,
        event_date=event_date,
        audio_file_path=None,
        jurisdiction_id=jurisdiction_id,
        published_at=published_at,
    )


def test_filter_since_days_keeps_recent_by_event_date():
    today = date(2026, 11, 19)
    videos = [
        _video("old", event_date="2026-01-01"),
        _video("new", event_date="2026-11-01"),
        _video("edge", event_date="2026-08-21"),  # exactly 90 days before today
    ]
    kept = filter_videos_for_browser_queue(
        videos, since_days=90, today=today, skip_analyzed=False, output_dir=Path("/tmp")
    )
    assert [v.video_id for v in kept] == ["new", "edge"]


def test_filter_since_days_uses_published_at_when_event_date_missing():
    today = date(2026, 11, 19)
    videos = [
        _video(
            "pub",
            event_date=None,
            published_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        ),
        _video(
            "stale",
            event_date=None,
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        ),
    ]
    kept = filter_videos_for_browser_queue(
        videos, since_days=90, today=today, skip_analyzed=False, output_dir=Path("/tmp")
    )
    assert [v.video_id for v in kept] == ["pub"]


def test_skip_analyzed_drops_videos_with_browser_analysis(tmp_path: Path):
    jid = "tuscaloosa_0177256"
    folder = tmp_path / jid
    folder.mkdir()
    (folder / "20261101_done_analysis.json").write_text(
        '{"meeting": {}, "decisions": [], "video_id": "done"}\n',
        encoding="utf-8",
    )
    # Also accept meta that names the video_id
    (folder / "other_meta.json").write_text(
        '{"video_id": "via_meta", "json_parsed": true}\n',
        encoding="utf-8",
    )
    (folder / "broken_analysis.json").write_text(
        '{"_error": "parse failed", "video_id": "broken"}\n',
        encoding="utf-8",
    )

    assert browser_analysis_exists(tmp_path, jid, "done")
    assert browser_analysis_exists(tmp_path, jid, "via_meta")
    assert not browser_analysis_exists(tmp_path, jid, "broken")
    assert not browser_analysis_exists(tmp_path, jid, "missing")

    videos = [
        _video("done", event_date="2026-11-01"),
        _video("via_meta", event_date="2026-11-02"),
        _video("broken", event_date="2026-11-03"),
        _video("missing", event_date="2026-11-04"),
    ]
    kept = filter_videos_for_browser_queue(
        videos,
        since_days=90,
        today=date(2026, 11, 19),
        skip_analyzed=True,
        output_dir=tmp_path,
    )
    assert [v.video_id for v in kept] == ["broken", "missing"]


def test_limit_applies_after_filters():
    today = date(2026, 11, 19)
    videos = [_video(f"v{i}", event_date=f"2026-11-{i:02d}") for i in range(1, 10)]
    kept = filter_videos_for_browser_queue(
        videos,
        since_days=90,
        today=today,
        skip_analyzed=False,
        output_dir=Path("/tmp"),
        limit=3,
    )
    assert [v.video_id for v in kept] == ["v1", "v2", "v3"]
