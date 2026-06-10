"""CivicPlus Alabaster city council table roster extraction."""

from pathlib import Path

from scrapers.discovery.contact_extract_from_html import (
    extract_civicplus_bio_detail_contacts_from_html,
    extract_civicplus_council_table_roster_contacts_from_html,
    extract_civicplus_directory_detail_urls_from_html,
    extract_structured_contacts_from_html,
    is_city_council_person_row,
)

_REPO = Path(__file__).resolve().parents[1]
_COUNCIL = (
    _REPO
    / "data/cache/scraped_meetings/AL/municipality/alabaster_0100820"
    / "_crawl_html/page__161_City-Council.html"
)
_BIO_GREG = (
    _REPO
    / "data/cache/scraped_meetings/AL/municipality/alabaster_0100820"
    / "_crawl_html/page__Directory.aspx_eid_80.html"
)


def test_alabaster_city_council_table_roster():
    html = _COUNCIL.read_text(encoding="utf-8", errors="replace")
    url = "https://www.cityofalabaster.com/161/City-Council"
    rows = extract_civicplus_council_table_roster_contacts_from_html(html, url)
    assert len(rows) == 7
    names = {r["person_name"] for r in rows}
    assert "Greg Farrell" in names
    assert "Stacy Rakestraw" in names
    greg = next(r for r in rows if r["person_name"] == "Greg Farrell")
    assert "Ward 4" in (greg.get("title_or_role") or "")
    assert "eid=80" in (greg.get("profile_url") or "").lower()
    assert all(is_city_council_person_row(r) for r in rows)

    eids = extract_civicplus_directory_detail_urls_from_html(html, url)
    assert len(eids) == 7

    all_rows = extract_structured_contacts_from_html(html, url)
    assert len(all_rows) == 7


def test_alabaster_bio_detail_includes_biography():
    html = _BIO_GREG.read_text(encoding="utf-8", errors="replace")
    url = "https://www.cityofalabaster.com/directory.aspx?eid=80"
    rows = extract_civicplus_bio_detail_contacts_from_html(html, url)
    assert len(rows) == 1
    bio = rows[0].get("biography") or ""
    assert "elected to City Council" in bio
    assert "Fire Department" in bio
    assert rows[0].get("profile_image_url")
