"""has_transcript means the bronze row carries caption text (#470)."""
from __future__ import annotations

import json

from scrapers.youtube.has_transcript_flag import compute_has_transcript


def test_raw_text_sets_flag():
    assert compute_has_transcript("hello council", None) is True
    assert compute_has_transcript("  ", None) is False
    assert compute_has_transcript(None, None) is False


def test_segments_list_or_json_sets_flag():
    assert compute_has_transcript(None, [{"text": "a", "start": 0}]) is True
    assert compute_has_transcript(None, []) is False
    assert compute_has_transcript(None, json.dumps([{"text": "a"}])) is True
    assert compute_has_transcript(None, "[]") is False
    assert compute_has_transcript(None, "null") is False


def test_loader_persist_uses_compute_has_transcript():
    """Regression: loader must not set has_transcript from raw_text alone."""
    from pathlib import Path

    src = Path(
        "packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py"
    ).read_text(encoding="utf-8")
    assert "compute_has_transcript" in src
    assert 'bool(transcript_data.get("raw_text"))' not in src
