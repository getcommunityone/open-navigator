"""Tests for scraped meeting PDF filename helpers."""

from datetime import date

from scripts.discovery.meeting_document_naming import (
    build_meeting_pdf_disk_filename,
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
