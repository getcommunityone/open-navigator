"""Discover ACTION_REQUIRED rollup (#710)."""

from __future__ import annotations

from pathlib import Path

from scrapers.youtube.discover_action_log import (
    DiscoverIssueStats,
    classify_reject_reason,
    format_uploads_fetch_failure,
)


def test_classify_quota_is_actionable():
    bucket, action = classify_reject_reason("uploads_fetch_failed:quotaExceeded")
    assert action is True
    assert "quota" in bucket.lower()


def test_classify_jev_exhausted_is_noise():
    bucket, action = classify_reject_reason(
        "jev_exhausted:7_videos best=0.1 [a:0.1]"
    )
    assert action is False
    assert "jev_exhausted" in bucket


def test_format_uploads_fetch_failure_reads_http_body():
    import urllib.error
    from io import BytesIO

    body = (
        b'{"error":{"errors":[{"reason":"quotaExceeded",'
        b'"domain":"youtube.quota"}]}}'
    )
    err = urllib.error.HTTPError(
        "https://www.googleapis.com/youtube/v3/playlistItems",
        403,
        "Forbidden",
        hdrs=None,
        fp=BytesIO(body),
    )
    assert format_uploads_fetch_failure(err) == (
        "uploads_fetch_failed:quotaExceeded"
    )


def test_write_action_required_markdown(tmp_path: Path):
    import json

    stats = DiscoverIssueStats()
    stats.note_state("VA")
    stats.record_accept("albemarle_51003", "jev_ok:0.740 video=x")
    stats.record_reject(
        "accomack_51001", "uploads_fetch_failed:quotaExceeded"
    )
    stats.record_reject(
        "amelia_51007", "uploads_fetch_failed:HTTP Error 403: Forbidden"
    )
    stats.record_reject(
        "augusta_51015", "jev_exhausted:7_videos best=0.01 [x]"
    )
    path = stats.write(out_dir=tmp_path, stamp="test")
    assert path == tmp_path / "ACTION_REQUIRED.md"
    text = path.read_text(encoding="utf-8")
    assert "Action required" in text
    assert "quotaExceeded" in text or "quota" in text.lower()
    assert "albemarle_51003" in text
    assert (tmp_path / "discover_action_required_test.md").is_file()
    assert stats.action_counts
    assert stats.noise_counts
    payload = json.loads((tmp_path / "action_required.json").read_text())
    assert payload["stamp"] == "test"
    assert payload["actions"]
    assert payload["actions"][0]["code"] == "youtube_api_quota"
    assert payload["actions"][0]["count"] == 2
    assert "fingerprint" in payload["actions"][0]
