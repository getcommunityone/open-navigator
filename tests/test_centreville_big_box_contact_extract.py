"""Centreville Tech (bibbal.com) big-box-profiles contact extraction."""

from scrapers.discovery.contact_extract_from_html import (
    extract_centreville_big_box_profile_contacts_from_html,
    extract_structured_contacts_from_html,
)


def test_bibb_county_commission_roster():
    html = """
    <div class="big-box-profiles">
        <div class="profile-picture" style="background-image: url(https://bibbal.com/wp-content/uploads/jeremy.jpg);"></div>
        <div class="upper">Jeremy Lightsey</div>
        <div class="lower">District 1 - Chairman</div>
        <a href="mailto:countycommission@bibbal.com?subject=Contact Commissioner Jeremy Lightsey" class="button">Email Jeremy</a>
    </div>
    <div class="big-box-profiles">
        <div class="profile-picture" style="background-image: url(https://bibbal.com/wp-content/uploads/charles.jpg);"></div>
        <div class="upper">Charles Caddell</div>
        <div class="lower">District 2</div>
        <a href="mailto:countycommission@bibbal.com?subject=Contact Commissioner Charles Caddell" class="button">Email Charles</a>
    </div>
    """
    rows = extract_centreville_big_box_profile_contacts_from_html(
        html, "https://bibbal.com/the-county-commission/"
    )
    assert len(rows) == 2
    chair = next(r for r in rows if r["person_name"] == "Jeremy Lightsey")
    assert chair["email"] == "countycommission@bibbal.com"
    assert "District 1" in (
        chair.get("department") or chair.get("title_or_role") or ""
    )
    assert "jeremy.jpg" in (chair.get("profile_image_url") or "")
    assert chair["extraction_method"] == "centreville_big_box_profile"

    all_rows = extract_structured_contacts_from_html(
        html, "https://bibbal.com/the-county-commission/"
    )
    assert len(all_rows) == 2
    assert not any(r.get("person_name") == "Email Jeremy" for r in all_rows)
