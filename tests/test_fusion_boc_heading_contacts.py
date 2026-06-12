"""Fusion / Avada board-of-commissioners h3 + p roster extraction."""

from scrapers.discovery.contact_extract_from_html import (
    extract_fusion_boc_heading_roster_contacts_from_html,
    extract_structured_contacts_from_html,
)

_ATKINSON_HTML = """
<h1>Atkinson County Board of Commissioners</h1>
<h3>Benjamin "Parker" Liles</h3>
<p>Chairman of the Board</p>
<h3>Donnis (Buddy) Willis</h3>
<p>District 1 Commissioner</p>
<h3>Gloria Farrell</h3>
<p>District 2 Commissioner</p>
<h3>Charlton Gillis</h3>
<p>District 3 Commissioner</p>
<h3>Johnny Durrance</h3>
<p>District 4 Commissioner</p>
<h3>James "Tom" Morris</h3>
<p>District 5 Commissioner</p>
<h3>Kayla Wise</h3>
<p>County Clerk</p>
<h3>Nina Lott</h3>
<p>Finance Officer/HR</p>
"""


def test_fusion_boc_heading_roster_atkinson():
    url = "https://atkinsoncounty.org/board-of-commissioners/"
    rows = extract_fusion_boc_heading_roster_contacts_from_html(_ATKINSON_HTML, url)
    assert len(rows) == 8
    names = {r["person_name"] for r in rows}
    assert 'Benjamin "Parker" Liles' in names
    assert "Kayla Wise" in names
    assert all(r["extraction_method"] == "fusion_boc_heading_roster" for r in rows)
    chairman = next(r for r in rows if "Parker" in (r["person_name"] or ""))
    assert "Chairman" in (chairman["title_or_role"] or "")


def test_structured_extract_includes_fusion_boc():
    rows = extract_structured_contacts_from_html(
        _ATKINSON_HTML, "https://atkinsoncounty.org/board-of-commissioners/"
    )
    assert len(rows) >= 8
    assert any(r.get("extraction_method") == "fusion_boc_heading_roster" for r in rows)
