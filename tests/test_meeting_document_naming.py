"""Tests for scraped meeting PDF filename helpers."""

from datetime import date

from scripts.discovery.meeting_document_naming import (
    build_meeting_pdf_disk_filename,
    dedupe_consecutive_slug_tokens,
    dedupe_meeting_disk_basename,
    pick_meeting_date,
    strip_redundant_date_slug_suffix,
    strip_redundant_meeting_date_from_title,
)


def test_strip_suiteone_date_with_zero_padded_day():
    d = date(2026, 1, 6)
    raw = "agenda 3:00 p.m. Finance Committee — Jan 06, 2026 | 03:00 PM"
    out = strip_redundant_meeting_date_from_title(raw, d)
    assert "2026" not in out.split()[-3:]
    assert "Jan" not in out
    assert "Finance Committee" in out


def test_build_filename_no_trailing_duplicate_date_slug():
    anchor = "3:00 p.m. Finance Committee — Jan 06, 2026 | 03:00 PM"
    name = build_meeting_pdf_disk_filename(
        "https://tuscaloosaal.suiteonemedia.com/event/GetAgendaFile/Agenda?aid=1",
        anchor,
        "agenda",
        year_fallback="2026",
    )
    assert name.startswith("2026-01-06_agenda_")
    assert "jan_06_2026" not in name


def test_strip_redundant_date_slug_suffix():
    d = date(2026, 1, 6)
    assert strip_redundant_date_slug_suffix(
        "3_00_p_m_finance_committee_jan_06_2026_03_00_pm", d
    ) == "3_00_p_m_finance_committee"


def test_pick_meeting_date_iso_in_anchor():
    anchor = "Agenda 2020-10-13 — City Council Meeting — City Council — 2020-10-13"
    url = "https://northportal.api.civicclerk.com/v1/Meetings/GetMeetingFile(fileId=1)"
    d, src = pick_meeting_date(url=url, anchor=anchor, doc_type="agenda")
    assert d == date(2020, 10, 13)
    assert src == "anchor_iso_date"


def test_build_filename_civicclerk_style_anchor():
    anchor = "Agenda — City Council Meeting — City Council"
    url = "https://northportal.api.civicclerk.com/v1/Meetings/GetMeetingFile(fileId=1)"
    name = build_meeting_pdf_disk_filename(
        url,
        anchor,
        "agenda",
        year_fallback="2020",
        meeting_date=date(2020, 10, 13),
    )
    assert name == "2020-10-13_agenda_city_council_meeting_city_council.pdf"


def test_build_filename_no_year_only_prefix_or_duplicate_iso_slug():
    anchor = (
        "Agenda 2020-12-17 — Zoning Board of Adjustment Meeting — "
        "Zoning Board of Adjustment — 2020-12-17"
    )
    url = "https://northportal.api.civicclerk.com/v1/Meetings/GetMeetingFile(fileId=1)"
    name = build_meeting_pdf_disk_filename(url, anchor, "agenda", year_fallback="2020")
    assert name.startswith("2020-12-17_agenda_")
    assert "2020_agenda_" not in name
    assert "2020_12_17" not in name
    assert "agenda_agenda" not in name


def test_dedupe_consecutive_slug_tokens():
    assert dedupe_consecutive_slug_tokens("agenda_agenda_finance") == "agenda_finance"
    assert dedupe_consecutive_slug_tokens("minutes_minutes") == "minutes"
    assert dedupe_meeting_disk_basename("2026_agenda_agenda_0c99e7a6.pdf") == "2026_agenda_0c99e7a6.pdf"


def test_build_filename_no_year_only_prefix_when_iso_in_anchor():
    """``2020_agenda_2020_12_17_…_2020_12_17`` style anchors → single ``2020-12-17`` prefix, no date in slug."""
    anchor = (
        "Agenda 2020-12-17 — Zoning Board of Adjustment Meeting — "
        "Zoning Board of Adjustment — 2020-12-17"
    )
    url = "https://northportal.api.civicclerk.com/v1/Meetings/GetMeetingFile(fileId=1)"
    name = build_meeting_pdf_disk_filename(url, anchor, "agenda", year_fallback="2020")
    assert name.startswith("2020-12-17_agenda_")
    assert "2020_12_17" not in name
    assert "2020_agenda_" not in name


def test_build_filename_manifest_anchor_with_leading_iso():
    anchor = (
        "2020-12-17 Agenda — Zoning Board of Adjustment Meeting — "
        "Zoning Board of Adjustment — 2020-12-17"
    )
    url = "https://northportal.api.civicclerk.com/v1/Meetings/GetMeetingFile(fileId=1397)"
    name = build_meeting_pdf_disk_filename(
        url, anchor, "agenda", meeting_date=date(2020, 12, 17)
    )
    assert name == (
        "2020-12-17_agenda_zoning_board_of_adjustment_meeting_zoning_board_of_adjustment.pdf"
    )
    assert "agenda_agenda" not in name
