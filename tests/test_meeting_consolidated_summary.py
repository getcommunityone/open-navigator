"""Judge vs technical consolidated meeting summaries."""

from __future__ import annotations

from pathlib import Path

from llm.governance.meeting_consolidated_summary import (
    build_judge_summary_markdown,
    build_technical_manifest_markdown,
    resolve_meeting_identity,
)


def test_judge_summary_omits_pipeline_inventory():
    artifacts = {
        "meeting_dir": "AL/county/county_01125/meetings/2026_02_18/session",
        "meeting_path": Path("/tmp/session"),
        "agenda_pdfs": [Path("2026_02_18-Agenda.pdf")],
        "minutes_pdfs": [],
        "audio_video": [Path("2026_02_18.mp4")],
        "demo4_chunks": [{"path": Path("chunk_000.json"), "data": {"chunk_index": 0}}],
        "drift_json": None,
        "transcripts": [],
        "demo3": [
            {
                "label": "Agenda",
                "pdf": Path("a.pdf"),
                "analysis": {
                    "meeting": {
                        "body_name": "Tuscaloosa County Commission",
                        "meeting_date": "2026-02-18",
                        "meeting_title": "Regular Session",
                    },
                    "decisions": [
                        {
                            "decision_id": "D001",
                            "topic": "Budget",
                            "primary_theme": "Fiscal",
                            "primary_theme_cofog": "COFOG-01",
                        }
                    ],
                    "people": [],
                },
            }
        ],
    }
    body = build_judge_summary_markdown(
        artifacts, jurisdiction_label="AL/county/county_01125"
    )
    assert "Sources on disk" not in body
    assert "Tuscaloosa County Commission" in body
    # The judge summary omits the inline pipeline inventory but points readers to
    # the technical companion file for the detail. build_judge_summary_markdown
    # now references it by filename ("companion file `_meeting_summary_technical.md`")
    # rather than the old literal phrase "technical manifest".
    assert "_meeting_summary_technical.md" in body
    assert "Mobile County" not in body


def test_technical_manifest_includes_gaps():
    artifacts = {
        "meeting_dir": "x/session",
        "meeting_path": Path("/tmp/session"),
        "agenda_pdfs": [Path("agenda.pdf")],
        "minutes_pdfs": [],
        "audio_video": [],
        "demo3": [],
        "demo4_chunks": [],
        "transcripts": [],
    }
    body = build_technical_manifest_markdown(artifacts)
    assert "Sources on disk" in body
    assert "Gaps" in body


def test_identity_warns_audio_only():
    artifacts = {
        "meeting_path": Path("/tmp/meetings/2026_02_18/session"),
        "agenda_pdfs": [Path("agenda.pdf")],
        "minutes_pdfs": [],
        "demo3": [],
        "demo4_chunks": [{"path": Path("c.json"), "data": {}}],
    }
    ident = resolve_meeting_identity(artifacts, jurisdiction_label="AL/county/county_01125")
    assert ident["warnings"]
