"""CivicPlus Gulf Shores mayor/council roster and bio detail extraction."""

from pathlib import Path

from scripts.discovery.contact_extract_from_html import (
    extract_civicplus_bio_detail_contacts_from_html,
    extract_civicplus_directory_detail_urls_from_html,
    extract_civicplus_mayor_council_roster_contacts_from_html,
    extract_structured_contacts_from_html,
)

_REPO = Path(__file__).resolve().parents[1]
_MAYOR_COUNCIL = (
    _REPO / "data/cache/scraped_meetings/AL/municipality/gulf_shores_0132272"
    / "_crawl_html/page__400_Mayor-Council.html"
)


def test_gulf_shores_mayor_council_roster_and_eid_links():
    html = _MAYOR_COUNCIL.read_text(encoding="utf-8", errors="replace")
    url = "https://gulfshoresal.gov/400/Mayor-Council"
    roster = extract_civicplus_mayor_council_roster_contacts_from_html(html, url)
    assert len(roster) == 6
    names = {r["person_name"] for r in roster}
    assert "Robert Craft" in names
    assert "Joe Garris" in names
    assert "Jennifer Guthrie" in names
    joe = next(r for r in roster if r["person_name"] == "Joe Garris")
    assert "directory.aspx" in (joe.get("profile_url") or "").lower()
    assert "eid=195" in (joe.get("profile_url") or "").lower()
    philip = next(r for r in roster if r["person_name"] == "Philip Harris")
    assert "Mayor Pro Tempore" in (philip.get("title_or_role") or "")
    assert philip.get("department") == "Place Three"

    eids = extract_civicplus_directory_detail_urls_from_html(html, url)
    assert len(eids) >= 4
    assert any("eid=195" in u.lower() for u in eids)


def test_gulf_shores_joe_garris_bio_detail():
    html = """
    <div id="CityDirectoryLeftMargin">
    <img src="/ImageRepository/Document?documentID=10130" alt="Joe Garris" />
    <div class='BioText'>
    <h1 class='BioName'>Joe Garris</h1>
    <div>Title: Councilmember - Place One<br>
    <script><!--
    var wsd="dottiejocharterservice";
    var xsd="yahoo.com";
    var ysd="dottiejocharterservice"+'@'+"yahoo.com";
    //--></script></div></div></div>
    """
    url = "https://www.gulfshoresal.gov/directory.aspx?eid=195"
    rows = extract_civicplus_bio_detail_contacts_from_html(html, url)
    assert len(rows) == 1
    assert rows[0]["person_name"] == "Joe Garris"
    assert rows[0]["email"] == "dottiejocharterservice@yahoo.com"
    assert "Councilmember" in (rows[0].get("title_or_role") or "")

    all_rows = extract_structured_contacts_from_html(html, url)
    assert len(all_rows) == 1
