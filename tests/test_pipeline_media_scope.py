"""Tests for PDF / audio / video pipeline modality scopes."""

from __future__ import annotations

import os
from pathlib import Path

from llm.governance.governance_meeting_llm import JurisdictionDir, MeetingInventory
from llm.governance.pipeline_media_scope import (
    apply_media_scope_to_environ,
    apply_media_scope_to_inventory,
    demo4_step_label,
    describe_demo4_file,
    filter_paths_for_media_scope,
    get_active_media_scope,
    normalize_media_scope_key,
    path_matches_media_scope,
    split_inventory_media,
)


def _jur() -> JurisdictionDir:
    root = Path("/tmp/raw/AL/county/county_01125")
    return JurisdictionDir(
        root=root,
        state_code="AL",
        scope="county",
        slug="county_01125",
        fips="01125",
    )


def _paths() -> tuple[list[Path], list[Path]]:
    pdfs = [Path("a.pdf"), Path("b.PDF")]
    audio = [
        Path("meet.mp3"),
        Path("meet.opus"),
        Path("meet.mp4"),
        Path("meet.webm"),
    ]
    return pdfs, audio


def test_normalize_media_scope_key() -> None:
    cases = [
        ("video", "video"),
        ("video_only", "video"),
        ("pdf_only", "pdf"),
        ("audio_only", "audio"),
        ("all", "all"),
        ("", "all"),
        ("bogus", "all"),
    ]
    for raw, expected in cases:
        assert normalize_media_scope_key(raw) == expected, raw


def test_split_inventory_all() -> None:
    pdfs, audio = _paths()
    scope = get_active_media_scope()
    os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = "all"
    out_pdfs, out_audio = split_inventory_media(pdfs, audio)
    assert len(out_pdfs) == 2
    assert len(out_audio) == 4


def test_split_inventory_pdf_only() -> None:
    pdfs, audio = _paths()
    os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = "pdf"
    out_pdfs, out_audio = split_inventory_media(pdfs, audio)
    assert len(out_pdfs) == 2
    assert out_audio == []


def test_split_inventory_audio_only() -> None:
    pdfs, audio = _paths()
    os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = "audio"
    out_pdfs, out_audio = split_inventory_media(pdfs, audio)
    assert out_pdfs == []
    assert {p.suffix for p in out_audio} == {".mp3", ".opus"}


def test_split_inventory_video_only() -> None:
    pdfs, audio = _paths()
    os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = "video"
    out_pdfs, out_audio = split_inventory_media(pdfs, audio)
    assert out_pdfs == []
    assert {p.suffix for p in out_audio} == {".mp4", ".webm"}


def test_apply_media_scope_to_inventory_mutates_lists() -> None:
    os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = "video"
    inv = MeetingInventory(jurisdiction=_jur(), pdfs=list(_paths()[0]), audio=list(_paths()[1]))
    apply_media_scope_to_inventory(inv)
    assert inv.pdfs == []
    assert all(p.suffix.lower() in {".mp4", ".webm"} for p in inv.audio)


def test_filter_paths_for_media_scope() -> None:
    paths = [
        Path("x.pdf"),
        Path("a.mp3"),
        Path("v.mp4"),
    ]
    os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = "video"
    scope = get_active_media_scope()
    assert filter_paths_for_media_scope(paths, scope) == [Path("v.mp4")]


def test_path_matches_media_scope() -> None:
    os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = "pdf"
    scope = get_active_media_scope()
    assert path_matches_media_scope(Path("doc.pdf"), scope)
    assert not path_matches_media_scope(Path("doc.mp4"), scope)


def test_apply_media_scope_to_environ_video() -> None:
    scope = apply_media_scope_to_environ("video_only")
    assert scope.key == "video"
    assert os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] == "video"
    assert os.environ["GOVERNANCE_GATEKEEPER_KINDS"] == "audio"
    assert os.environ["GOVERNANCE_DEMO4_VIDEO_CHUNKS"] == "1"


def test_apply_media_scope_to_environ_pdf() -> None:
    scope = apply_media_scope_to_environ("pdf")
    assert scope.run_demo4 is False
    assert os.environ["GOVERNANCE_GATEKEEPER_KINDS"] == "pdf"


def test_apply_media_scope_to_environ_audio() -> None:
    scope = apply_media_scope_to_environ("audio")
    assert scope.run_demo4 is True
    assert os.environ["GOVERNANCE_DEMO4_VIDEO_CHUNKS"] == "0"


def test_demo4_labels() -> None:
    os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = "video"
    assert "video" in demo4_step_label().lower()
    mp4 = describe_demo4_file(Path("2026_02_18.mp4"), demo4_model="gemma-4-31b-it")
    assert "MP4" in mp4 and "opus" in mp4.lower()
    gemini = describe_demo4_file(
        Path("2026_02_18.mp4"),
        demo4_model="gemini-2.0-flash",
    )
    assert "video/mp4" in gemini
