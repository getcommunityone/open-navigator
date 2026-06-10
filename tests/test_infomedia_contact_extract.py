"""Infomedia WordPress official paragraph extraction (Trussville)."""

from pathlib import Path

from scrapers.discovery.contact_extract_from_html import (
    extract_infomedia_official_paragraph_contacts_from_html,
    extract_structured_contacts_from_html,
)
from scripts.discovery.contact_profile_images import extract_profile_image_jobs

_REPO = Path(__file__).resolve().parents[1]
_COUNCIL = _REPO / "tests/fixtures/contact_extract/trussville_city_council_snippet.html"


def test_trussville_council_roster_snippet():
    html = """
    <p><strong><br /><img src="https://trussville.org/wp-content/uploads/2016/03/Jaime-Anderson26-240x300.jpg" alt="" /></strong></p>
    <p><strong>Jaime Anderson, Councilmember<br /></strong>Phone: (318) 294-5976<br />
    Email: <a href="mailto:janderson@trussville.org">janderson@trussville.org</a></p>
    <p><strong>Ben Horton, Councilmember<br /></strong>Phone: (732) 403-5628<br />
    Email: <a href="mailto:ben.horton@trussville.gov">ben.horton@trussville.gov</a></p>
    """
    url = "https://trussville.org/government/city-council/"
    rows = extract_infomedia_official_paragraph_contacts_from_html(html, url)
    assert len(rows) == 2
    jaime = next(r for r in rows if r["person_name"] == "Jaime Anderson")
    assert jaime["email"] == "janderson@trussville.org"
    assert jaime["title_or_role"] == "Councilmember"
    assert "Jaime-Anderson" in (jaime.get("profile_image_url") or "")

    all_rows = extract_structured_contacts_from_html(html, url)
    assert len(all_rows) == 2
    assert all(r.get("person_name") for r in all_rows)

    jobs = extract_profile_image_jobs(html, url)
    assert len(jobs) >= 1
    assert any(j["person_name"] == "Jaime Anderson" for j in jobs)


def test_trussville_mayor_signature_block():
    html = """
    <p><img src="https://trussville.org/wp-content/uploads/2025/12/Mayor-Short-scaled.jpeg" alt="Mayor Short Headshot" /></p>
    <p><strong>Ben Short</strong><br />Mayor, City of Trussville<br />bshort@trussville.org</p>
    """
    url = "https://trussville.org/government/mayors-office/"
    rows = extract_infomedia_official_paragraph_contacts_from_html(html, url)
    assert len(rows) == 1
    assert rows[0]["person_name"] == "Ben Short"
    assert rows[0]["email"] == "bshort@trussville.org"
    assert "Mayor" in (rows[0].get("title_or_role") or "")
