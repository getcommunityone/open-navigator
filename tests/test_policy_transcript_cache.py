"""Policy transcript cache layout and API bundle fields."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from scrapers.youtube.policy_transcript_cache import (
    policy_transcript_sidecar_path,
    policy_transcript_sidecar_paths,
    resolve_policy_transcripts_dir,
    write_policy_transcript_cache,
)
from scrapers.youtube.transcript_api_client import fetch_transcript_bundle


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


@patch("scrapers.youtube.transcript_api_client.build_youtube_transcript_api")
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


def test_cleanup_policy_transcript_cache_tree_idempotent(tmp_path: Path):
    from llm.gemini.transcript_cache_paths import (
        DIR_ANALYSIS,
        DIR_REPORTS,
        DIR_RUNS,
        DIR_TRANSCRIPTS,
        cleanup_policy_transcript_cache_tree,
        ensure_jurisdiction_layout,
    )

    channel_root = (
        tmp_path / "AL" / "municipality" / "northport_0155200" / "UCxxxxxxxxxxx"
    )
    ensure_jurisdiction_layout(channel_root)

    long_title = (
        "City of Northport Regular Council Meeting and Public Hearing Session "
        "on Zoning Amendments 04.28.26"
    )
    old_stem = "2026-05-01_City_of_Northport_Regular_Council_Meeting"

    # 01_transcripts: upload-dated transcript + kept orphan sidecar (no embedded segments)
    transcript_with_embedded = channel_root / DIR_TRANSCRIPTS / f"{old_stem}.json"
    transcript_with_embedded.write_text(
        json.dumps(
            {
                "video_id": "vid_embedded",
                "title": long_title,
                "event_date": "2026-05-01",
                "caption_raw_data": [{"text": "call to order", "start": 0.0, "duration": 1.0}],
            }
        ),
        encoding="utf-8",
    )
    redundant_sidecar = (
        channel_root / DIR_TRANSCRIPTS / f"{old_stem}.caption_raw_data.json"
    )
    redundant_sidecar.write_text(json.dumps([{"text": "call to order"}]), encoding="utf-8")

    orphan_stem = "2026-05-02_Special_Work_Session_04.29.26"
    transcript_without_embedded = channel_root / DIR_TRANSCRIPTS / f"{orphan_stem}.json"
    transcript_without_embedded.write_text(
        json.dumps(
            {
                "video_id": "vid_orphan",
                "title": "Special Work Session 04.29.26",
                "event_date": "2026-05-02",
            }
        ),
        encoding="utf-8",
    )
    kept_sidecar = (
        channel_root / DIR_TRANSCRIPTS / f"{orphan_stem}.caption_raw_data.json"
    )
    kept_sidecar.write_text(json.dumps([{"text": "kept sidecar"}]), encoding="utf-8")

    # 02_analysis: uses meeting.meeting_date without top-level title
    analysis_file = channel_root / DIR_ANALYSIS / f"{old_stem}.json"
    analysis_file.write_text(
        json.dumps(
            {
                "video_id": "vid_embedded",
                "meeting": {
                    "body_name": "City Council",
                    "meeting_date": "2026-05-01",
                },
                "decisions": [],
            }
        ),
        encoding="utf-8",
    )

    # 03_reports: markdown report + mermaid-errors sidecar
    report_file = channel_root / DIR_REPORTS / f"{old_stem}.md"
    report_file.write_text("# Report\n", encoding="utf-8")
    mermaid_err_file = (
        channel_root / DIR_REPORTS / f"{old_stem}.md.mermaid-errors.json"
    )
    mermaid_err_file.write_text(json.dumps({"errors": []}), encoding="utf-8")

    # 04_runs: .meta.json without event_date + .diagrams.md + corrupted .diagrams.diagrams.md
    meta_file = channel_root / DIR_RUNS / f"{old_stem}.meta.json"
    meta_file.write_text(
        json.dumps({"video_id": "vid_embedded", "title": long_title}),
        encoding="utf-8",
    )
    diagrams_file = channel_root / DIR_RUNS / f"{old_stem}.diagrams.md"
    diagrams_file.write_text("```mermaid\ngraph TD\n```\n", encoding="utf-8")

    dateless_meta = channel_root / DIR_RUNS / "2026-04-14_Board_Work_Session.meta.json"
    dateless_meta.write_text(
        json.dumps({"video_id": "vid_board", "title": "Board Work Session"}),
        encoding="utf-8",
    )
    corrupted_diagrams = (
        channel_root
        / DIR_RUNS
        / "2026-04-14_Board_Work_Session.diagrams.diagrams.md"
    )
    corrupted_diagrams.write_text("```mermaid\ngraph LR\n```\n", encoding="utf-8")

    pass1 = cleanup_policy_transcript_cache_tree(tmp_path, dry_run=False)
    assert pass1.get("dates_moved", 0) > 0
    assert pass1.get("sidecars_removed_sidecar", 0) == 1
    assert pass1.get("sidecars_kept_orphan_sidecar", 0) == 1

    # Verify .diagrams.md did not compound to .diagrams.diagrams.md and corrupted file was repaired
    runs_names = sorted(p.name for p in (channel_root / DIR_RUNS).iterdir() if p.is_file())
    assert all(".diagrams.diagrams" not in name for name in runs_names)
    assert all(not name.startswith("unknown-date_") for name in runs_names)
    assert "2026-04-14_Board_Work_Session.meta.json" in runs_names
    assert "2026-04-14_Board_Work_Session.diagrams.md" in runs_names

    # Verify kept sidecar was moved alongside its transcript and retained its sidecar suffix
    transcript_names = sorted(
        p.name for p in (channel_root / DIR_TRANSCRIPTS).iterdir() if p.is_file()
    )
    assert "2026-04-29_Special_Work_Session.json" in transcript_names
    assert "2026-04-29_Special_Work_Session.caption_raw_data.json" in transcript_names

    # Pass 2 (and dry-run): must be completely idempotent with zero moves or duplicate removals
    pass2_dry = cleanup_policy_transcript_cache_tree(tmp_path, dry_run=True)
    assert pass2_dry.get("dates_would_move", 0) == 0
    assert pass2_dry.get("dates_would_remove_older_duplicate", 0) == 0
    assert pass2_dry.get("dates_would_move_sidecar", 0) == 0
    assert pass2_dry.get("dates_json_event_date_patched", 0) == 0
    assert pass2_dry.get("sidecars_would_remove_sidecar", 0) == 0

    pass2 = cleanup_policy_transcript_cache_tree(tmp_path, dry_run=False)
    assert pass2.get("dates_moved", 0) == 0
    assert pass2.get("dates_removed_older_duplicate", 0) == 0
    assert pass2.get("dates_moved_sidecar", 0) == 0
    assert pass2.get("dates_json_event_date_patched", 0) == 0
    assert pass2.get("sidecars_removed_sidecar", 0) == 0
    assert pass2.get("sidecars_kept_orphan_sidecar", 0) == 1
