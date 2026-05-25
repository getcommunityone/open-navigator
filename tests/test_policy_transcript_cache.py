"""Policy transcript cache layout and API bundle fields."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.datasources.youtube.policy_transcript_cache import (
    policy_transcript_sidecar_path,
    policy_transcript_sidecar_paths,
    resolve_policy_transcripts_dir,
    write_policy_transcript_cache,
)
from scripts.datasources.youtube.transcript_api_client import fetch_transcript_bundle


def test_policy_transcript_sidecar_path():
    main = Path("/tmp/AL/county/foo_01001/ch/01_transcripts/2026-01-01_meeting.json")
    raw_p = policy_transcript_sidecar_path(main)
    assert raw_p.name.endswith(".caption_raw_data.json")
    raw_p2, _ = policy_transcript_sidecar_paths(main)
    assert raw_p2 == raw_p


def test_resolve_policy_transcripts_dir(tmp_path: Path):
    folder = resolve_policy_transcripts_dir(
        tmp_path,
        "county_01001",
        state_code="AL",
        jurisdiction_type="county",
        channel_id="UCxxxxxxxxxxx",
        create=True,
    )
    assert folder.is_dir()
    assert folder.name == "01_transcripts"
    assert "UCxxxxxxxxxxx" in str(folder)


def test_write_policy_transcript_cache(tmp_path: Path):
    out = write_policy_transcript_cache(
        tmp_path,
        jurisdiction_id="county_01001",
        state_code="AL",
        row={
            "video_id": "abc123",
            "title": "Board Meeting",
            "event_date": "2026-01-15",
            "channel_id": "UCxxxxxxxxxxx",
            "video_url": "https://www.youtube.com/watch?v=abc123",
            "jurisdiction_id": "county_01001",
        },
        yt={"raw_text": "hello", "segments": [], "transcript_source": "youtube_transcript_api"},
        caption_raw_data=[{"text": "<i>hello</i>", "start": 0.0, "duration": 1.0}],
        jurisdiction_type="county",
    )
    assert "01_transcripts" in str(out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["caption_raw_data"][0]["text"] == "<i>hello</i>"
    assert payload["caption_preserve_formatting"] is True
    assert not policy_transcript_sidecar_path(out).is_file()
    assert not (out.parent / f"{out.stem}.caption_formatted.json").exists()


@patch("scripts.datasources.youtube.transcript_api_client.build_youtube_transcript_api")
def test_fetch_transcript_bundle_single_preserve_formatting_call(mock_build: MagicMock):
    snippet = MagicMock(text="<i>hi</i>", start=0.0, duration=1.0)
    fetched = MagicMock(
        snippets=[snippet],
        language_code="en",
        is_generated=False,
    )
    fetched.to_raw_data.return_value = [
        {"text": "<i>hi</i>", "start": 0.0, "duration": 1.0}
    ]
    api = MagicMock()
    api.fetch.return_value = fetched
    mock_build.return_value = api

    result = fetch_transcript_bundle(
        "vid1",
        cookies_file="/nonexistent/cookies.txt",
        retry_on_block=False,
    )
    api.fetch.assert_called_once()
    assert api.fetch.call_args.kwargs.get("preserve_formatting") is True
    assert result["caption_raw_data"] == fetched.to_raw_data.return_value
    assert result["caption_preserve_formatting"] is True
    assert "caption_formatted" not in result
