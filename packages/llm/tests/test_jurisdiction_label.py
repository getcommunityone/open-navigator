"""The Part 1 prompt names the meeting's own jurisdiction, never a hard-coded one (#265). No network."""

from __future__ import annotations

from pathlib import Path

import pytest
from llm.gemini.browser_policy_analysis import (
    DEFAULT_PROMPT_PART_1,
    VideoRow,
    build_user_message,
    jurisdiction_label,
)


def _video(**over) -> VideoRow:
    base = {
        "video_id": "aaaaaaaaaaa",
        "video_url": "https://www.youtube.com/watch?v=aaaaaaaaaaa",
        "title": "Council",
        "last_updated": None,
        "event_date": "2026-11-03",
        "audio_file_path": None,
        "jurisdiction_id": "municipality_0155200",
        "jurisdiction_name": "Northport",
        "jurisdiction_type": "municipality",
        "state_code": "AL",
        "state": "Alabama",
    }
    return VideoRow(**{**base, **over})


@pytest.mark.parametrize(
    ("over", "label"),
    [
        ({}, "Northport, Alabama (municipality)"),
        ({"state": None}, "Northport, AL (municipality)"),
        ({"jurisdiction_type": "school_district", "jurisdiction_name": "Hoover City Schools"},
         "Hoover City Schools, Alabama (school district)"),
        ({"jurisdiction_type": None}, "Northport, Alabama"),
        ({"jurisdiction_name": "Northport, Alabama"}, "Northport, Alabama (municipality)"),  # state not repeated
        ({"jurisdiction_name": None}, None),
        ({"jurisdiction_name": "  "}, None),
        ({"jurisdiction_name": "c-AL-12345"}, None),  # a placeholder code, not a name
    ],
)
def test_jurisdiction_label(over, label):
    assert jurisdiction_label(_video(**over)) == label


def test_message_names_the_videos_own_jurisdiction():
    msg = build_user_message("PROMPT", _video())
    assert "**Jurisdiction:** Northport, Alabama (municipality)." in msg
    assert "Tuscaloosa" not in msg


def test_unknown_jurisdiction_leaves_the_line_out():
    msg = build_user_message("PROMPT", _video(jurisdiction_name=None))
    assert "**Jurisdiction:**" not in msg and "Tuscaloosa" not in msg
    assert "**Jurisdiction:**" not in build_user_message("PROMPT", _video(), jurisdiction_label=None)
    assert "**Jurisdiction:** Somewhere." in build_user_message("PROMPT", _video(), jurisdiction_label="Somewhere")


def test_part1_prompt_names_no_real_city_in_its_address_examples():
    prompt = Path(DEFAULT_PROMPT_PART_1).read_text(encoding="utf-8")
    assert "Tuscaloosa" not in prompt


def test_batch_and_pipeline_message_carry_it(tmp_path):
    from llm.gemini.meeting_transcript_policy import (
        Part1Request,
        build_cacheable_part1_message,
    )

    msg = build_cacheable_part1_message("RULES\n<transcript>\nx\n</transcript>", "line", _video(), task_line="t")
    assert "**Jurisdiction:** Northport, Alabama (municipality)." in msg
    request = Part1Request(video=_video(), model="m", user_message=msg, prompt_path=tmp_path / "p.md",
                           transcript_block="line", transcript_meta={}, agenda_blocks=[], state_code="AL",
                           out_dir=tmp_path)  # fmt: skip
    assert Part1Request.from_json(request.to_json()).video.jurisdiction_name == "Northport"
    old_sidecar = request.to_json()
    for key in ("jurisdiction_name", "jurisdiction_type", "state_code", "state"):
        old_sidecar["video"].pop(key)
    assert Part1Request.from_json(old_sidecar).video.jurisdiction_name is None  # sidecars written before #265
