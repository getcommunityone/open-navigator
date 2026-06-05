"""Unit tests for warehouse transcript normalization (no live DB)."""

from __future__ import annotations

from llm.gemini.transcript_db import (
    _norm_segments_jsonb,
    _parse_caption_text_timed,
    normalize_transcript_row,
)


def test_parse_caption_text_timed_hms():
    segs = _parse_caption_text_timed("{00:01:04} hello   world  {00:01:08} foo bar")
    assert segs == [
        {"text": "hello world", "start": 64.0},
        {"text": "foo bar", "start": 68.0},
    ]


def test_parse_caption_text_timed_mmss():
    assert _parse_caption_text_timed("{02:05} hi")[0]["start"] == 125.0


def test_parse_caption_text_timed_no_markers():
    assert _parse_caption_text_timed("just plain text") == []
    assert _parse_caption_text_timed("") == []


def test_norm_segments_jsonb_keeps_usable_rows():
    out = _norm_segments_jsonb(
        [{"text": "a", "start": 1.5, "duration": 2}, {"text": "  "}, "junk", {"start": 3}]
    )
    assert out == [{"text": "a", "start": 1.5, "duration": 2.0}]


def test_norm_segments_jsonb_non_list():
    assert _norm_segments_jsonb(None) == []
    assert _norm_segments_jsonb({"text": "x"}) == []


def test_normalize_prefers_segments_then_timed_then_raw():
    seg_row = {"video_id": "v", "segments": [{"text": "hi", "start": 0}]}
    assert normalize_transcript_row(seg_row)["transcript_source"].endswith("(segments)")

    timed_row = {"video_id": "v", "caption_text_timed": "{00:00:01} hi there"}
    assert normalize_transcript_row(timed_row)["transcript_source"].endswith("(caption_text_timed)")

    raw_row = {"video_id": "v", "raw_text": "only raw"}
    got = normalize_transcript_row(raw_row)
    assert got["transcript_source"].endswith("(raw_text)")
    assert got["segments"] == [{"text": "only raw", "start": 0.0}]


def test_normalize_returns_none_when_empty():
    assert normalize_transcript_row({"video_id": "v"}) is None
    assert (
        normalize_transcript_row(
            {"video_id": "v", "segments": [], "caption_text_timed": "", "raw_text": ""}
        )
        is None
    )


def test_normalize_yt_shape():
    yt = normalize_transcript_row(
        {"video_id": "v", "language": "en", "is_auto_generated": True, "raw_text": "x"}
    )
    assert set(yt) == {
        "video_id",
        "language",
        "is_auto_generated",
        "raw_text",
        "segments",
        "transcript_source",
    }
    assert yt["is_auto_generated"] is True
