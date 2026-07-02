"""Tests for YouTube Videos + Streams tab merge helpers."""

from datetime import datetime

from scrapers.youtube.scrape_youtube_channels import (
    _parse_published_at,
    dedupe_videos_by_id,
)


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


def test_parse_published_at_handles_iso_z_and_date_only():
    # ISO-Z format (standard from YouTube API)
    dt1 = _parse_published_at("2026-05-31T20:46:58Z")
    assert dt1 == datetime(2026, 5, 31, 20, 46, 58)

    # Date only format (YYYYMMDD) from yt-dlp upload_date
    dt2 = _parse_published_at("20260531")
    assert dt2 == datetime(2026, 5, 31)

    # Standard ISO format with offset
    dt3 = _parse_published_at("2026-05-31T20:46:58+00:00")
    assert dt3 == datetime(2026, 5, 31, 20, 46, 58)
    
    # Already a datetime object
    dt_obj = datetime(2026, 5, 31, 20, 46, 58)
    assert _parse_published_at(dt_obj) == dt_obj


def test_parse_published_at_rejects_garbage():
    assert _parse_published_at(None) is None
    assert _parse_published_at("") is None
    assert _parse_published_at("  ") is None
    assert _parse_published_at("garbage-date") is None
    # 8 chars but not a date
    assert _parse_published_at("abcdefgh") is None

