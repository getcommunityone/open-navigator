"""CivicPlus staff directory h-card contact extraction."""

from scripts.discovery.contact_extract_from_html import (
    extract_civicplus_staff_directory_hcard_contacts_from_html,
)


def test_northport_city_council_hcards():
    html = """
    <li class="widgetItem h-card">
      <img src="/ImageRepository/Document?documentID=1771" alt="Dale Phillips" class="u-photo" />
      <h4 class="widgetTitle field p-name">Dale Phillips</h4>
      <div class="field p-job-title">Mayor</div>
      <div class="field u-email"><a href="mailto:dphillips@northportal.gov">Email</a></div>
      <div class="field p-tel">Phone: <a href="tel:2053941476">205-394-1476</a></div>
      <div class="field p-link"><a href="/directory.aspx?eid=37">More Information</a></div>
    </li>
    <li class="widgetItem h-card">
      <h4 class="p-name">Turnley Smith</h4>
      <div class="p-job-title">Council Member - District 1</div>
      <div class="u-email"><a href="mailto:tsmith@northportal.gov">Email</a></div>
      <div class="p-link"><a href="/directory.aspx?eid=35">More Information</a></div>
    </li>
    """
    rows = extract_civicplus_staff_directory_hcard_contacts_from_html(
        html, "https://www.northportal.gov/220/City-Council"
    )
    assert len(rows) == 2
    mayor = next(r for r in rows if r.get("email") == "dphillips@northportal.gov")
    assert mayor["person_name"] == "Dale Phillips"
    assert mayor["title_or_role"] == "Mayor"
    assert mayor["phone"] == "(205) 394-1476"
    assert "directory.aspx?eid=37" in (mayor.get("profile_url") or "")
    d1 = next(r for r in rows if r.get("email") == "tsmith@northportal.gov")
    assert d1["department"] == "District 1"
    assert "Council Member" in (d1.get("title_or_role") or "")
