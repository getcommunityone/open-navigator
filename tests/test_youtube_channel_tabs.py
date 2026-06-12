"""Tests for YouTube Videos + Streams tab merge helpers."""

from datetime import datetime

from scrapers.youtube.scrape_youtube_channels import dedupe_videos_by_id


def test_dedupe_videos_by_id_keeps_newest_and_caps():
    videos = [
        {"video_id": "aaa", "published_at": "2024-01-01T00:00:00", "title": "old"},
        {"video_id": "bbb", "published_at": "2026-01-01T00:00:00", "title": "new"},
        {"video_id": "aaa", "published_at": "2025-06-01T00:00:00", "title": "dup newer"},
    ]
    out = dedupe_videos_by_id(videos, max_results=10)
    assert [v["video_id"] for v in out] == ["bbb", "aaa"]
    assert out[1]["title"] == "dup newer"


def test_dedupe_videos_by_id_respects_max_results():
    videos = [
        {"video_id": f"id{i}", "published_at": datetime(2026, 1, i).isoformat()}
        for i in range(1, 6)
    ]
    out = dedupe_videos_by_id(videos, max_results=3)
    assert len(out) == 3
