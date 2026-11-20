"""Unit tests for #632 classification helpers (no warehouse)."""

from scrapers.discovery.data_center_agenda_scoreboard import _classify


def test_has_agenda_wins_over_blocked():
    cls, _ = _classify(
        agenda_docs=3,
        website_status="blocked",
        platforms={"civicplus_agenda_center"},
    )
    assert cls == "has_agenda"


def test_blocked_before_reader_needed():
    cls, notes = _classify(
        agenda_docs=0,
        website_status="blocked",
        platforms={"civicclerk"},
    )
    assert cls == "blocked"
    assert "reader_needed" in notes


def test_reader_needed_for_civicplus():
    cls, notes = _classify(
        agenda_docs=0,
        website_status="ok",
        platforms={"civicplus_agenda_center", "youtube"},
    )
    assert cls == "reader_needed"
    assert "civicplus_agenda_center" in notes


def test_no_document_platform_youtube_only():
    cls, _ = _classify(
        agenda_docs=0,
        website_status="ok",
        platforms={"youtube"},
    )
    assert cls == "no_document_platform"


def test_unreachable():
    cls, _ = _classify(agenda_docs=0, website_status="unreachable", platforms=set())
    assert cls == "unreachable"
