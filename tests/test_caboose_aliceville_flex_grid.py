"""Caboose flex-grid council roster (City of Aliceville)."""

from pathlib import Path

from scripts.discovery.contact_extract_from_html import (
    extract_caboose_directory_contacts_from_html,
    extract_caboose_flex_grid_profile_jobs,
)
from scripts.discovery.contact_profile_images import contact_profile_image_stem_from_name

_REPO = Path(__file__).resolve().parents[1]
_COUNCIL = (
    _REPO
    / "data/cache/scraped_meetings/AL/municipality/aliceville_0101228"
    / "_crawl_html/page__about_mayor-city-council_city-councilman-and-districts.html"
)
_URL = "https://www.thecityofaliceville.com/about/mayor-city-council/city-councilman-and-districts"


def test_aliceville_flex_grid_council_contacts_and_image_stems():
    html = _COUNCIL.read_text(encoding="utf-8", errors="replace")
    rows = extract_caboose_directory_contacts_from_html(html, _URL)
    names = {r["person_name"] for r in rows}
    assert "Thomas F. Wilkins" in names
    assert "Jackie Jones" in names
    assert "Fred Woods" in names
    assert "Linda Spence Gosa" in names
    assert "Vacant" not in names

    jobs = extract_caboose_flex_grid_profile_jobs(html, _URL)
    stems = {
        contact_profile_image_stem_from_name(j["person_name"])
        for j in jobs
        if j.get("person_name")
    }
    assert "jackie_jones" in stems
    assert "thomas_f_wilkins" in stems
    assert "city_councilman_and_districts" not in stems
