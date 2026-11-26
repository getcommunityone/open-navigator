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
    item = groups[0]["reasons"][0]
    assert (item["reason"], item["count"], item["example"]) == ("weird #", 2, "weird 4040")  # raw text untouched
    assert item["reason_id"] == fr.reason_id("weird #") and item["example_video_id"] is None


def test_no_failures_gives_no_groups():
    assert fr.build_groups([]) == []


def test_supported_stages_are_videos_and_transcripts():
    assert fr.STAGES == ("videos", "transcripts")


# --- #802: grouping by the real cause, merged video ids, reason ids, retry ----------------------
OPEN = "Could not retrieve a transcript for the video https://www.youtube.com/watch?v={vid}! This is most likely caused by:"
TAIL = " If you are sure that the described cause is not responsible for this error and that a transcript should be retrievable"


def _msg(prefix, vid, cause):
    return f"{prefix}{OPEN.format(vid=vid)} {cause}{TAIL}"


@pytest.mark.parametrize(
    ("text", "group"),
    [
        (_msg("yt-dlp: VideoUnplayable: ", "kIZPPnZRG_0", "The video is unplayable for the following reason: This video has been removed by the uploader"), "unavailable"),
        (_msg("yt-dlp: TranscriptsDisabled: ", "p5F--AFBk_4", "Subtitles are disabled for this video"), "no_captions"),
        (_msg("VideoUnplayable: ", "40xFjuPAReQ", "The video is unplayable for the following reason: This live event will begin in 44 hours."), "not_yet_available"),
        (_msg("VideoUnplayable: ", "dkl4BRKrzd4", "The video is unplayable for the following reason: Premieres in 5 days"), "not_yet_available"),
        ("no transcript returned", "no_captions"),
        ("Sign in to confirm you're not a bot", "bot_block"),
        ("both sides agreed to the motion", "other"),  # "both" must not look like "bot"
        ("robotic voice reads the minutes", "other"),
    ],
)
def test_the_shared_opening_does_not_decide_the_group(text, group):
    assert fr.classify_reason(text) == group


def test_messages_that_differ_only_by_video_id_are_one_reason():
    a = _msg("yt-dlp: TranscriptsDisabled: ", "0WjbuIoQMSU", "Subtitles are disabled for this video")
    b = _msg("yt-dlp: TranscriptsDisabled: ", "-4D6m5hcUjQ", "Subtitles are disabled for this video")
    assert fr.normalize_reason(a) == fr.normalize_reason(b)
    assert "watch?v=#!" in fr.normalize_reason(a)


def test_an_ordinary_eleven_letter_word_is_not_taken_for_a_video_id():
    assert fr.normalize_reason("the video is unavailable here") == "the video is unavailable here"
    assert fr.normalize_reason("see youtu.be/abcDEF12345 now") == "see youtu.be/# now"


def test_reason_id_is_a_stable_32_char_hex_md5():
    rid = fr.reason_id("Subtitles are disabled")
    assert rid == fr.reason_id("Subtitles are disabled") and len(rid) == 32
    assert rid != fr.reason_id("Subtitles are enabled")
    import hashlib

    assert rid == hashlib.md5(b"Subtitles are disabled").hexdigest()  # same as md5() in Postgres


def test_groups_carry_the_example_video_and_whether_they_can_be_retried():
    rows = [
        ("Sign in to confirm you're not a bot", 40, "Sign in to confirm you're not a bot", "vidBOT00001"),
        ("HTTP Error #: Too Many Requests", 54, "HTTP Error 429: Too Many Requests", "vidRATE0001"),
        ("Subtitles are disabled", 605, "Subtitles are disabled for this video", "vidCAPS0001"),
    ]
    groups = {g["key"]: g for g in fr.build_groups(rows)}
    assert groups["rate_limit"]["retryable"] is True
    assert groups["bot_block"]["retryable"] is True
    assert groups["no_captions"]["retryable"] is False
    assert groups["rate_limit"]["reasons"][0]["example_video_id"] == "vidRATE0001"
    assert groups["rate_limit"]["reasons"][0]["reason_id"] == fr.reason_id("HTTP Error #: Too Many Requests")


def _groups():
    return fr.build_groups(
        [
            ("HTTP Error #: Too Many Requests", 54, "HTTP Error 429: Too Many Requests", "v1"),
            ("ProxyError: connection timed out", 7, "ProxyError: connection timed out", "v2"),
            ("Subtitles are disabled", 605, "Subtitles are disabled for this video", "v3"),
        ]
    )


def test_retry_picks_every_reason_in_a_retryable_group():
    ids = fr.pick_retry_reason_ids(_groups(), group="rate_limit")
    assert ids == [fr.reason_id("HTTP Error #: Too Many Requests")]


def test_retry_picks_one_reason_by_id():
    rid = fr.reason_id("ProxyError: connection timed out")
    assert fr.pick_retry_reason_ids(_groups(), reason_id=rid) == [rid]


@pytest.mark.parametrize("kwargs", [{"group": "no_captions"}, {"group": "unavailable"}])
def test_retry_refuses_groups_that_cannot_work(kwargs):
    with pytest.raises(ValueError, match="cannot be retried|no failed videos"):
        fr.pick_retry_reason_ids(_groups(), **kwargs)


def test_retry_refuses_a_reason_in_a_group_that_cannot_work():
    with pytest.raises(ValueError, match="cannot be retried"):
        fr.pick_retry_reason_ids(_groups(), reason_id=fr.reason_id("Subtitles are disabled"))


@pytest.mark.parametrize("kwargs", [{}, {"group": "rate_limit", "reason_id": "x" * 32}, {"group": "nope"}])
def test_retry_needs_exactly_one_selector_that_matches(kwargs):
    with pytest.raises(ValueError):
        fr.pick_retry_reason_ids(_groups(), **kwargs)
