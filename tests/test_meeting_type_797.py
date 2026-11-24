"""#797: the meeting type label shown next to the date on decision and meeting pages."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "api" / "meeting_type.py"
_spec = importlib.util.spec_from_file_location("meeting_type_under_test", _PATH)
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ("CITY_COUNCIL", "City Council"),
        ("city council", "City Council"),
        ("  Work   Session ", "Work Session"),
        ("board_of_education", "Board of Education"),
        ("PLANNING_COMMISSION", "Planning Commission"),
    ],
)
def test_known_types_are_only_recased_and_respaced(raw, label):
    assert mt.meeting_type_label(raw) == label


@pytest.mark.parametrize("raw", [None, "", "   ", "UNKNOWN", "unknown", "_"])
def test_blank_or_unknown_is_omitted(raw):
    assert mt.meeting_type_label(raw) is None


def test_subquery_reads_the_video_id_join_and_aliases_meeting_type():
    sql = mt.meeting_type_subquery("ii")
    assert "event_youtube_with_jurisdiction" in sql and "y.video_id = m.video_id" in sql
    assert "ii.event_decision_id" in sql and sql.rstrip().endswith("AS meeting_type")


def test_the_three_endpoints_expose_meeting_type():
    root = Path(__file__).resolve().parents[1] / "api" / "routes"
    assert "meeting_type: Optional[str]" in (root / "lenses.py").read_text()
    assert "meeting_type: Optional[str]" in (root / "decisions.py").read_text()
    assert "meeting_type: Optional[str]" in (root / "meetings.py").read_text()
    assert "meeting_type_subquery('ii')" in (root / "decision_browse.py").read_text()
