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
    assert "meeting_type_subquery('ii', has_type)" in (root / "decision_browse.py").read_text()


# --- #840: the relation is not published to every schema the API reads -------------------------------------------


class _Conn:
    """Stands in for an asyncpg connection: answers the to_regclass check and counts the calls."""

    def __init__(self, found, fail=False):
        self.found, self.fail, self.calls = found, fail, 0

    async def fetchval(self, sql, *args):
        self.calls += 1
        assert "to_regclass" in sql and args == ("event_youtube_with_jurisdiction",)
        if self.fail:
            raise RuntimeError("connection lost")
        return self.found


@pytest.fixture()
def fresh():
    mt._available, mt._checked_at = None, 0.0
    yield
    mt._available, mt._checked_at = None, 0.0


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_unpublished_relation_selects_null_and_never_names_it():
    for sql in (mt.meeting_type_subquery("ii", False), mt.meeting_type_by_video_sql("m.video_id", False)):
        assert sql == "NULL::text AS meeting_type"


def test_by_video_sql_reads_the_relation_when_published():
    sql = mt.meeting_type_by_video_sql("event_meeting.video_id")
    assert "FROM event_youtube_with_jurisdiction y" in sql
    assert "y.video_id = event_meeting.video_id" in sql and sql.endswith("AS meeting_type")


def test_found_is_remembered_for_the_process(fresh):
    conn = _Conn(True)
    assert _run(mt.meeting_type_available(conn)) is True
    assert _run(mt.meeting_type_available(_Conn(False))) is True
    assert conn.calls == 1


def test_missing_is_rechecked_only_after_the_interval(fresh, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(mt.time, "monotonic", lambda: now[0])
    conn = _Conn(False)
    assert _run(mt.meeting_type_available(conn)) is False
    now[0] += mt._MISSING_RECHECK_SECONDS - 1
    assert _run(mt.meeting_type_available(conn)) is False
    assert conn.calls == 1
    now[0] += 2
    conn.found = True
    assert _run(mt.meeting_type_available(conn)) is True
    assert conn.calls == 2


def test_a_failed_check_counts_as_missing(fresh):
    assert _run(mt.meeting_type_available(_Conn(True, fail=True))) is False


def test_detail_queries_take_the_column_from_the_helper():
    root = Path(__file__).resolve().parents[1] / "api" / "routes"
    for name, expr in (("decisions.py", "m.video_id"), ("meetings.py", "event_meeting.video_id")):
        text = (root / name).read_text()
        assert "FROM event_youtube_with_jurisdiction" not in text
        assert text.count("__MEETING_TYPE__") == 2
        assert f'meeting_type_by_video_sql("{expr}", has_type)' in text
