"""Tests for the meeting comparison API route.

Covers the pure helpers (JSONB parsing, summary-text flattening, decision build)
and confirms both endpoints are registered at their expected /api paths. No DB and
no Gemini calls — the billed POST path is exercised only at the unit level.
"""

from __future__ import annotations

from datetime import date

from api.routes.meeting_comparison import (
    ComparisonDecision,
    _build_decisions,
    _meeting_iso_date,
    _parse_json,
    _summary_text,
)


def test_parse_json_decodes_text_and_tolerates_objects():
    assert _parse_json('{"yes": 5, "no": 2}') == {"yes": 5, "no": 2}
    # Already-parsed dict passes through unchanged.
    assert _parse_json({"yes": 5}) == {"yes": 5}
    # Non-JSON text is returned verbatim, not raised.
    assert _parse_json("not json") == "not json"
    assert _parse_json(None) is None


def test_meeting_iso_date():
    assert _meeting_iso_date(date(2026, 1, 15)) == "2026-01-15"
    assert _meeting_iso_date("2026-01-15") == "2026-01-15"
    assert _meeting_iso_date(None) is None


def test_build_decisions_parses_vote_tally():
    rows = [
        {
            "event_decision_id": "abc",
            "headline": "Approve budget",
            "outcome": "approved",
            "decision_statement": "The council approved the budget.",
            "vote_tally": '{"yes": 6, "no": 1}',
            "primary_theme": "finance",
        }
    ]
    decisions = _build_decisions(rows)
    assert len(decisions) == 1
    assert decisions[0].vote_tally == {"yes": 6, "no": 1}
    assert decisions[0].headline == "Approve budget"


def test_summary_text_flattens_summary_and_decisions():
    meeting = {
        "meeting_summary": "Council met and approved several items.",
        "agenda_summary": "Budget; zoning; appointments.",
    }
    decisions = [
        ComparisonDecision(
            event_decision_id="abc",
            headline="Approve budget",
            outcome="approved",
            decision_statement="The council approved the FY budget.",
        )
    ]
    text = _summary_text(meeting, decisions)
    assert "MEETING SUMMARY:" in text
    assert "AGENDA SUMMARY:" in text
    assert "DECISIONS:" in text
    assert "Approve budget — approved" in text
    assert "The council approved the FY budget." in text


def test_summary_text_omits_empty_sections():
    meeting = {"meeting_summary": "Only a summary.", "agenda_summary": None}
    text = _summary_text(meeting, [])
    assert "MEETING SUMMARY:" in text
    assert "AGENDA SUMMARY:" not in text
    assert "DECISIONS:" not in text


def test_routes_registered_at_api_paths():
    from api.main import app

    paths = {
        getattr(r, "path", None) or getattr(r, "path_format", None) for r in app.routes
    }
    assert "/api/meeting/{event_meeting_id}/comparison" in paths
    assert "/api/meeting/{event_meeting_id}/document-gaps" in paths
