"""Ordering for jurisdiction transcript backfill (untried-first)."""

from __future__ import annotations

from scrapers.youtube.backfill_jurisdiction_transcripts import (
    sort_backfill_rows,
)


def test_sort_backfill_rows_prefers_untried_then_newest():
    rows = [
        {"video_id": "old_fail", "transcript_download_attempts": 2, "published_at": "2026-05-20"},
        {"video_id": "new_fail", "transcript_download_attempts": 1, "published_at": "2026-05-25"},
        {"video_id": "fresh", "transcript_download_attempts": 0, "published_at": "2026-05-10"},
        {"video_id": "fresh_new", "transcript_download_attempts": 0, "published_at": "2026-05-24"},
    ]
    ordered = sort_backfill_rows(rows, "published_at", prefer_untried=True)
    assert [r["video_id"] for r in ordered] == [
        "fresh_new",
        "fresh",
        "new_fail",
        "old_fail",
    ]


def test_sort_backfill_rows_date_only_when_disabled():
    rows = [
        {"video_id": "a", "transcript_download_attempts": 0, "published_at": "2026-05-01"},
        {"video_id": "b", "transcript_download_attempts": 5, "published_at": "2026-05-30"},
    ]
    ordered = sort_backfill_rows(rows, "published_at", prefer_untried=False)
    assert [r["video_id"] for r in ordered] == ["b", "a"]
