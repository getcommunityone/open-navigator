"""Hostinger / Zyro GridTextBox elected-officials extraction (Abbeville)."""

from pathlib import Path

from scripts.discovery.contact_extract_from_html import (
    extract_hostinger_grid_textbox_officials_from_html,
    extract_structured_contacts_from_html,
)

_REPO = Path(__file__).resolve().parents[1]
_SNIPPET = _REPO / "tests/fixtures/contact_extract/abbeville_elected_officials_snippet.html"


def test_abbeville_elected_officials_grid():
    html = _SNIPPET.read_text(encoding="utf-8")
    url = "https://cityofabbeville.org/elected-officials"
    rows = extract_hostinger_grid_textbox_officials_from_html(html, url)
    assert len(rows) == 6
    names = {r["person_name"] for r in rows}
    assert names == {
        "Jimmy Money",
        "Dexter Glanton",
        "Brendt Murphy",
        "Javen Williams",
        "Jimmy Davis, Jr.",
        "Vincent Feggins",
    }
    mayor = next(r for r in rows if r["person_name"] == "Jimmy Money")
    assert mayor.get("title_or_role") == "Mayor"
    dexter = next(r for r in rows if r["person_name"] == "Dexter Glanton")
    assert dexter.get("department") == "District 1"
    jimmy_jr = next(r for r in rows if r["person_name"] == "Jimmy Davis, Jr.")
    assert jimmy_jr.get("department") == "District 5"

    all_rows = extract_structured_contacts_from_html(html, url)
    assert len(all_rows) == 6
