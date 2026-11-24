"""#792: failure reasons for the Videos/Transcripts stage rows."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "api" / "batch_jobs" / "failure_reasons.py"
_spec = importlib.util.spec_from_file_location("failure_reasons_under_test", _PATH)
fr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fr)  # pure module: no app imports at load time


@pytest.mark.parametrize(
    ("text", "group"),
    [
        ("Sign in to confirm you're not a bot", "bot_block"),
        ("ERROR: [youtube] abc: Sign in to confirm you're not a bot. Use --cookies", "bot_block"),
        ("HTTP Error 429: Too Many Requests", "rate_limit"),
        ("Subtitles are disabled for this video", "no_captions"),
        ("No transcripts were found for any of the requested language codes", "no_captions"),
        ("Video unavailable", "unavailable"),
        ("This video is private", "unavailable"),
        ("Private video. Sign in if you've been granted access", "unavailable"),
        ("ProxyError: connection timed out", "network"),
        ("", "unknown"),
        (None, "unknown"),
        ("   ", "unknown"),
        ("something never seen before", "other"),
    ],
)
def test_classify_reason(text, group):
    assert fr.classify_reason(text) == group


def test_bot_block_wins_over_rate_limit_wording():
    assert fr.classify_reason("429 Too Many Requests: Sign in to confirm you're not a bot") == "bot_block"


def test_normalize_merges_long_numbers_only():
    assert fr.normalize_reason("HTTP Error 429: Too Many") == "HTTP Error #: Too Many"
    assert fr.normalize_reason("code 12 stays") == "code 12 stays"
    assert fr.normalize_reason("  x 4040  ") == "x #"


def test_group_counts_sum_to_the_input_total():
    rows = [
        ("Sign in to confirm you're not a bot", 500, "Sign in to confirm you're not a bot"),
        ("Subtitles are disabled", 300, "Subtitles are disabled for this video"),
        ("weird #", 90, "weird 4040"),
        ("HTTP Error #: Too Many Requests", 24, "HTTP Error 429: Too Many Requests"),
    ]
    groups = fr.build_groups(rows)
    assert sum(g["count"] for g in groups) == sum(r[1] for r in rows) == 914
    assert [g["key"] for g in groups] == ["bot_block", "no_captions", "other", "rate_limit"]  # biggest first
    assert all(g["label"] and g["advice"] for g in groups)


def test_other_keeps_the_raw_text_unchanged():
    groups = fr.build_groups([("weird #", 2, "weird 4040")])
    assert groups[0]["key"] == "other"
    assert groups[0]["reasons"][0] == {"reason": "weird #", "count": 2, "example": "weird 4040"}


def test_no_failures_gives_no_groups():
    assert fr.build_groups([]) == []


def test_supported_stages_are_videos_and_transcripts():
    assert fr.STAGES == ("videos", "transcripts")
