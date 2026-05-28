"""Tests for duplicate meeting upload selection."""

from scrapers.youtube.dedupe_meeting_videos import (
    cluster_duplicate_meetings,
    dedupe_meeting_rows,
    dedupe_video_id_map,
    duration_minutes_close,
    normalize_meeting_title,
    pick_preferred_upload,
)


def test_normalize_meeting_title_dates():
    assert normalize_meeting_title("District 1 Town Hall - 4/23/2026") == normalize_meeting_title(
        "district 1 town hall - 04/23/2026"
    )


def test_duration_minutes_close():
    assert duration_minutes_close(62, 60)
    assert not duration_minutes_close(30, 90)


def test_prefer_captioned_duplicate_town_hall():
    rows = [
        {
            "video_id": "mLiEsTJmmFQ",
            "title": "District 1 Town Hall - 4/23/2026",
            "duration_minutes": 62,
            "has_transcript": False,
        },
        {
            "video_id": "7idcoultVYo",
            "title": "District 1 Town Hall - 4/23/2026",
            "duration_minutes": 61,
            "has_transcript": True,
        },
        {
            "video_id": "-z4gj347FGI",
            "title": "District 1 Town Hall - 4/23/2026",
            "duration_minutes": 60,
            "has_transcript": False,
        },
    ]
    clusters = cluster_duplicate_meetings(rows)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3
    winner = pick_preferred_upload(clusters[0])
    assert winner["video_id"] == "7idcoultVYo"

    kept, result = dedupe_meeting_rows(rows)
    assert len(kept) == 1
    assert kept[0]["video_id"] == "7idcoultVYo"
    assert result.skipped["mLiEsTJmmFQ"] == "7idcoultVYo"
    assert result.skipped["-z4gj347FGI"] == "7idcoultVYo"


def test_dedupe_video_id_map():
    event_ids = {"mLiEsTJmmFQ": 1, "7idcoultVYo": 2, "-z4gj347FGI": 3}
    meta = [
        {"video_id": "mLiEsTJmmFQ", "title": "District 1 Town Hall - 4/23/2026", "duration_minutes": 62},
        {"video_id": "7idcoultVYo", "title": "District 1 Town Hall - 4/23/2026", "duration_minutes": 61, "has_transcript": True},
        {"video_id": "-z4gj347FGI", "title": "District 1 Town Hall - 4/23/2026", "duration_minutes": 60},
    ]
    filtered, result = dedupe_video_id_map(event_ids, meta)
    assert filtered == {"7idcoultVYo": 2}
    assert len(result.skipped) == 2
